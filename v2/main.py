from dotenv import load_dotenv
from autogen import UserProxyAgent, AssistantAgent
from gnews import GNews
from twikit import Client
import os


# Load environment variables
load_dotenv()
KEYWORD = os.getenv("KEYWORD")
ARTICLE_COUNT = os.getenv("ARTICLE_COUNT")
KEYWORD_COUNT = os.getenv("KEYWORD_COUNT")
NEWS_COUNTRY = os.getenv("NEWS_COUNTRY")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_BASE = os.getenv("GROQ_API_BASE")
RELEASE = os.getenv("RELEASE")
AUTO_GENERATE_KEYWORDS = os.getenv("AUTO_GENERATE_KEYWORDS")
VERSION = os.getenv("VERSION")

if(RELEASE == "PROD"):
    USERNAME = os.getenv("XUSERNAME")
    EMAIL = os.getenv("XEMAIL")
    PASSWORD = os.getenv("XPASSWORD")
else:
    USERNAME = os.getenv("XUSERNAME_TEST")
    EMAIL = os.getenv("XEMAIL_TEST")
    PASSWORD = os.getenv("XPASSWORD_TEST")

#print all the above environment variables
# for key in ['KEYWORD', 'ARTICLE_COUNT', 'KEYWORD_COUNT', 'NEWS_COUNTRY', 'AUTO_GENERATE_KEYWORDS',
#             'GROQ_MODEL_NAME', 'GROQ_API_BASE', 'RELEASE', 'VERSION',]:
#     print(f"{key} = {os.environ[key]}")

# create cache directory
cache = '../.cache'
if not os.path.exists(cache):
    os.makedirs(cache)
topics_file = f'{cache}/topics.csv'
urls_file = f'{cache}/urls.csv'

#print current path and all the files
print("Current path: ", os.getcwd())
print("Files in the directory: ", os.listdir())

# Config dictionary
llm_config = {
    "cache_seed": 42,
    "config_list": [{
        "model": GROQ_MODEL_NAME,
        "api_key": GROQ_API_KEY,
        "base_url": GROQ_API_BASE
    }],
}

google_news = GNews()
google_news.period = '1h'  # News from last 7 days
google_news.max_results = int(ARTICLE_COUNT)  # number of responses across a keyword
google_news.country = 'United States'  # News from a specific country 
google_news.language = 'english'  # News in a specific language

# # Initialize client
if RELEASE != 'DEV' and 'x_client' not in globals():
    x_client = Client('en-US')

    x_client.login(
        auth_info_1=USERNAME,
        auth_info_2=EMAIL,
        password=PASSWORD
    )
    print("Client initialized")


"""Decode encoded Google News entry URLs."""
import base64
import functools
import re


_ENCODED_URL_PREFIX = "https://news.google.com/rss/articles/"
_ENCODED_URL_RE = re.compile(fr"^{re.escape(_ENCODED_URL_PREFIX)}(?P<encoded_url>[^?]+)")
_DECODED_URL_RE = re.compile(rb'^\x08\x13".+?(?P<primary_url>http[^\xd2]+)\xd2\x01')

@functools.lru_cache(2048)
def _decode_google_news_url(url: str) -> str:
    match = _ENCODED_URL_RE.match(url)
    encoded_text = match.groupdict()["encoded_url"]  # type: ignore
    encoded_text += "==="  # Fix incorrect padding. Ref: https://stackoverflow.com/a/49459036/
    decoded_text = base64.urlsafe_b64decode(encoded_text)

    match = _DECODED_URL_RE.match(decoded_text)
    primary_url = match.groupdict()["primary_url"]  # type: ignore
    primary_url = primary_url.decode()
    return primary_url


def decode_google_news_url(url: str) -> str:  # Not cached because not all Google News URLs are encoded.
    """Return Google News entry URLs after decoding their encoding as applicable."""
    return _decode_google_news_url(url) if url.startswith(_ENCODED_URL_PREFIX) else url


def deduplicate_news_list(urls, keywords):
    # deduplicate the urls and keywords based on urls
    urls_dict = {}
    for i in range(len(urls)):
        if urls[i] not in urls_dict:
            urls_dict[urls[i]] = keywords[i]
        else:
            urls_dict[urls[i]] = urls_dict[urls[i]] + ', ' + keywords[i]

    urls = list(urls_dict.keys())
    keywords = list(urls_dict.values())
    return urls, keywords


from pyshorteners import Shortener
from newspaper import Article
from typing import Annotated
import pandas as pd


def read_news_articles_tool(urls, keywords):
    if not os.path.isfile(urls_file):
        df_urls = pd.DataFrame(columns=['urls', 'status'])  # Define the variable with a default value
        df_urls.to_csv(urls_file)
        print("File created")
    else:
        df_urls = pd.read_csv(urls_file, index_col='Unnamed: 0')
        print("File loaded")
    
    urls = [url for url in urls if url not in df_urls['urls'].values]
    
    #deduplicate the urls and keywords based on urls
    urls, keywords = deduplicate_news_list(urls, keywords)

    if len(urls) == 0:
        return []

    article_list = []
    for i in range(len(urls)):
        try:
            
            article = Article(urls[i])
            article.download()
            article.parse()

            if article.text: # and len(article.text.strip().split('\n')) > 1:
                # Append the URL and status to the DataFrame
                df_urls = pd.concat([pd.DataFrame([[urls[i], 'success']], columns=df_urls.columns), df_urls], ignore_index=True)
                df_urls.to_csv(urls_file)
                article.keyword = keywords[i]
                article_list.append(article)
                continue
            else:
                df_urls = pd.concat([pd.DataFrame([[urls[i], 'empty']], columns=df_urls.columns), df_urls], ignore_index=True)
                df_urls.to_csv(urls_file)
                continue
        except Exception as e:
            df_urls = pd.concat([pd.DataFrame([[urls[i], 'error']], columns=df_urls.columns), df_urls], ignore_index=True)
            df_urls.to_csv(urls_file)
            print(f"Error reading article: {str(e)}")
            continue

    return article_list


def get_news_articles_tool(keyword_list: Annotated[list, "The list of keywords"], count: Annotated[int, "The number of news articles to collect from the internet"]) -> str:
    s = Shortener(timeout=5)
    
    urls, keywords = [], []
    for keyword in keyword_list:
        # keyword = keyword.replace(" ", "%20")
        print(f"FETCHING NEWS ON TOPIC: {keyword}")
        sources = google_news.get_news(keyword)
        # source.build(keyword = keyword, topic = 'TECHNOLOGY', top_news=False)
        for source in sources:
            decoded_url = decode_google_news_url(source['url'])
            urls = urls + [decoded_url]
        keywords = keywords + [keyword] * len(sources)
    print(f"URLS: {urls}")
        
    if len(urls) == 0:
        return None
    
    article_list = read_news_articles_tool(urls, keywords)
    print(f"Articles read: {len(article_list)}")

    result = ''
    if len(article_list) > 0:
        # Get the short urls
        for article in article_list:
            try:
                article.short_url = s.tinyurl.short(article.url)
            except Exception as e:
                print(f"Error shortening url: {str(e)}")
                article.short_url = article.url

        for i in range(len(article_list)):
            # do this until the result length is less than 30000
            if len(result) > 30000:
                break
            result += ("""NEWS {n} TOPIC: {keyword}
NEWS {n} TITLE: {title}
NEWS {n} CONTENT: {content}
NEWS {n} SOURCE: {url}

"""
        ).format(
            keyword = article_list[i].keyword,
            n = i+1,
            title=article_list[i].title,
            content=article_list[i].text.replace('\n\n', '\n')[:1000],
            url=article_list[i].short_url
        )

    return result[:4500]

# read and print urls_file
if os.path.isfile(urls_file):
    print("File found at: ", urls_file)
else:
    print("File not found")

import re
from datetime import datetime
import pytz


def merge_tweets(tweet_list: Annotated[list, "The list of tweets to merge"]) -> None:
    merged_tweets = []
    current_tweet = ""

    for tweet in tweet_list:
        if len(current_tweet) + len(tweet) <= 278:
            current_tweet += f'{tweet}\n\n'
        else:
            merged_tweets.append(current_tweet)
            current_tweet = tweet
    if current_tweet:
        merged_tweets.append(current_tweet)
    
    return merged_tweets

def add_source_urls(tweet_list: Annotated[list, "The list of tweets to post"], source_list: Annotated[list, "The list of 'https://tinyurl.com/' source URLs for each tweet"]) -> list:
    if len(tweet_list) == len(source_list):
        del_index = []
        for i in range(len(source_list)):
            if tweet_list[i] and source_list[i]:
                if not re.search(r'https://tinyurl\.com/[a-zA-Z0-9]{8}', tweet_list[i]): # if the tweet does not contain a source
                    if re.search(r'https://tinyurl\.com/[a-zA-Z0-9]{8}', source_list[i]): # if we have a source seperately
                        tweet_list[i] = tweet_list[i][:278-len(source_list[i])]
                        tweet_list[i] += f"\n{source_list[i]}"
        # uncomment below five lines to don't post a news if it doesn't have a source
                    else:
                        del_index.append(i)
        for i in sorted(del_index, reverse=True):
            del tweet_list[i]
            del source_list[i]
        
    return tweet_list

def get_intro_tweet() -> str:
    now = datetime.now(pytz.utc)
    eastern = pytz.timezone('America/New_York')
    now_eastern = now.astimezone(eastern)

    last_hour = now_eastern.replace(minute=0, second=0, microsecond=0)

    formatted_datetime = last_hour.strftime("%I:00%p EST, %B %d, %Y")

    return f"""These are the AI news within the last 1 hour:
{formatted_datetime}"""


import time


def write_tweet_tool(tweet_list: Annotated[list, "The list of tweets to post"], source_list: Annotated[list, "The list of 'https://tinyurl.com/' source URL for each tweet"]) -> str:
    tweet_list = add_source_urls(tweet_list, source_list)
    # tweet_list = merge_tweets(tweet_list)
    # tweet_list = [get_intro_tweet()] + tweet_list

    posts = ''
    # for tweet, source in zip(tweet_list, source_list):
    for i in range(len(tweet_list)):
    #     if 'https://tinyurl.com/' in tweet_list[i]:
    #         if len(tweet_list[i]) > 280:
    #             tweet_list[i] = tweet_list[i][:276-len(source)] + '...' + f"\n{source}"
    #     else:
    #         if len(tweet_list[i]) <= 279-len(source):
    #             tweet_list[i] += f"\n{source}"
    #         else:
    #             tweet_list[i] = tweet_list[i][:276-len(source)] + '...' + f"\n{source}"
        try:
            # final tweet length check for redundancy 
            if len(tweet_list[i]) > 280:
                tweet_list[i] = tweet_list[i][:276] + '...'

            if RELEASE != "DEV":
                if i==0:
                    last_tweet = x_client.create_tweet(
                        text=tweet_list[i],
                    )
                else:
                    last_tweet = x_client.create_tweet(
                        text=tweet_list[i],
                        reply_to=last_tweet.id
                    )
            
            posts += ("""
Tweet: {tweet}
Length: {length}
                      
                      """).format(tweet=tweet_list[i], length=len(tweet_list[i]))
            
            time.sleep(1)
        except Exception as e:
            error_message = f"Failed to post tweet: {str(e)}"
            print(error_message)
            continue

    if(posts == ''):
        posts = "No tweets posted"
        
    return posts


news_collector_agent = AssistantAgent(
    "news_collector_agent",
    llm_config=llm_config,
    system_message=f"""You are good at collecting recent news articles about a given keyword on the internet. 
    You should generate a list of {KEYWORD_COUNT} topics closely related to the given keyword. 
    Use the provided tool to collect news about the generated list of topics.""",
    max_consecutive_auto_reply=1
)

tweet_writer_agent = AssistantAgent(
    "tweet_writer_agent",
    llm_config=llm_config,
    system_message=f"""You are an autonomous twitter bot that's created to educate the people about {KEYWORD}. 
    You are good at posting a series of twitter posts on the given list of news by summarizing each news as one short tweet. 
    You MUST only strictly post news that is about the topic {KEYWORD} or the respective news topic given and ignore other news(double check this). 
    Always use simple words. 
    Use the provided tool to post all the tweets as a thread(list of tweets).""",
    max_consecutive_auto_reply=1
)


user_proxy_agent = UserProxyAgent(
    name="User",
    system_message="You are a helpful AI assistant. Return 'TERMINATE' when the task is done.",
    is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"],
    human_input_mode="NEVER",
    code_execution_config=False,
)


# # Register the tool signature with the assistant agent.
news_collector_agent.register_for_llm(name="get_news_articles_tool", description="Collect news articles about a list of topics on the internet.")(get_news_articles_tool)
tweet_writer_agent.register_for_llm(name="write_tweet_tool", description="Write a twitter thread.")(write_tweet_tool)

# Register the tool function with the user proxy agent.
user_proxy_agent.register_for_execution(name="get_news_articles_tool")(get_news_articles_tool)
user_proxy_agent.register_for_execution(name="write_tweet_tool")(write_tweet_tool)


import random


try:
    if AUTO_GENERATE_KEYWORDS=='True':
        user_proxy_agent.initiate_chats([
            {
                "recipient": news_collector_agent,
                "message": f"Collect {KEYWORD_COUNT} news articles about the topic '{KEYWORD}' from the internet.",
                "clear_history": True,
                "silent": False,
                "summary_method": "last_msg"
            },
            {
                "recipient": tweet_writer_agent,
                "message": "Write and post a twitter thread about the given list of news articles:\n",
                "clear_history": True,
                "silent": False,
                "summary_method": "last_msg"
            }
        ])
    else:
        topics_list = pd.read_csv('../topics.csv')
        topics_list = topics_list.values.tolist()
        topics_list = [item for sublist in topics_list for item in sublist]
        topics_list = [x for x in topics_list if str(x) != 'nan']
        random.shuffle(topics_list)
        # topics_list = topics_list[:5] # TESTING

        if len(topics_list)==0:
            raise Exception("No topics found")

        news_articles = get_news_articles_tool(keyword_list=topics_list, count=int(ARTICLE_COUNT))
        if news_articles:
            user_proxy_agent.initiate_chats([
                {
                    "recipient": tweet_writer_agent,
                    "message": f"Write and post a twitter thread about the given list of news articles:\n{news_articles}",
                    "clear_history": True,
                    "silent": False,
                    "summary_method": "last_msg"
                }
            ])
        else:
            raise Exception("No news articles found")
except Exception as e:
    print(f"Global Error: {str(e)}")
    #print trackback
    import traceback
    traceback.print_exc()
    raise e