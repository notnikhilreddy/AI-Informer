from dotenv import load_dotenv
from autogen import UserProxyAgent, AssistantAgent
from twikit import Client
import os


# Load environment variables
load_dotenv()
KEYWORD = os.getenv("KEYWORD")
ARTICLE_COUNT = int(os.getenv("ARTICLE_COUNT"))
KEYWORD_COUNT = int(os.getenv("KEYWORD_COUNT"))
NEWS_COUNTRY = os.getenv("NEWS_COUNTRY")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_BASE = os.getenv("GROQ_API_BASE")
RELEASE = os.getenv("RELEASE")
AUTO_GENERATE_KEYWORDS = os.getenv("AUTO_GENERATE_KEYWORDS")
VERSION = float(os.getenv("VERSION"))

if(RELEASE == "PROD"):
    USERNAME = os.getenv("XUSERNAME")
    EMAIL = os.getenv("XEMAIL")
    PASSWORD = os.getenv("XPASSWORD")
else:
    USERNAME = os.getenv("XUSERNAME_TEST")
    EMAIL = os.getenv("XEMAIL_TEST")
    PASSWORD = os.getenv("XPASSWORD_TEST")

#print all the above environment variables
for key in ['KEYWORD', 'ARTICLE_COUNT', 'KEYWORD_COUNT', 'NEWS_COUNTRY', 'AUTO_GENERATE_KEYWORDS',
            'GROQ_MODEL_NAME', 'GROQ_API_BASE', 'RELEASE', 'VERSION',]:
    print(f"{key} = {os.environ[key]}")

# create cache directory
cache = '../.cache'
if not os.path.exists(cache):
    os.makedirs(cache)
topics_file = f'{cache}/topics.csv'
urls_file = f'{cache}/urls.csv'

# Config dictionary
llm_config = {
    "cache_seed": 42,
    "config_list": [{
        "model": GROQ_MODEL_NAME,
        "api_key": GROQ_API_KEY,
        "base_url": GROQ_API_BASE
    }],
}

# # Initialize client
if RELEASE != 'DEV' and 'x_client' not in globals():
    x_client = Client('en-US')

    x_client.login(
        auth_info_1=USERNAME,
        auth_info_2=EMAIL,
        password=PASSWORD
    )
    print("Client initialized")


from gnews import GNews
from pyshorteners import Shortener
from newspaper import Article
from typing import Annotated
import pandas as pd


def read_news_articles_tool(news_list):
    if not os.path.isfile(urls_file):
        df_urls = pd.DataFrame(columns=['urls', 'status'])  # Define the variable with a default value
        df_urls.to_csv(urls_file)
    else:
        df_urls = pd.read_csv(urls_file, index_col='Unnamed: 0')
    
    news_list = [news for news in news_list if news['url'] not in df_urls['urls'].values]
    
    #deduplicate the news_list based on urls
    def deduplicate_news_list(news_list):
        seen_urls = set()
        unique_news_list = []
        for news_item in news_list:
            url = news_item.get('url')
            if url not in seen_urls:
                seen_urls.add(url)
                unique_news_list.append(news_item)
        return unique_news_list
    news_list = deduplicate_news_list(news_list)

    if len(news_list) == 0:
        return [], []

    article_list = []
    final_news_list = []
    for news in news_list:
        try:
            article = Article(news['url'])
            article.download()
            article.parse()

            if article.text and len(article.text.strip().split('\n')) > 1:
                # Append the URL and status to the DataFrame
                df_urls = pd.concat([pd.DataFrame([[news['url'], 'success']], columns=df_urls.columns), df_urls], ignore_index=True)
                df_urls.to_csv(urls_file)
                final_news_list.append(news)
                article_list.append(article)
                continue
            else:
                df_urls = pd.concat([pd.DataFrame([[news['url'], 'empty']], columns=df_urls.columns), df_urls], ignore_index=True)
                df_urls.to_csv(urls_file)
                continue
        except Exception as e:
            df_urls = pd.concat([pd.DataFrame([[news['url'], 'error']], columns=df_urls.columns), df_urls], ignore_index=True)
            df_urls.to_csv(urls_file)
            print(f"Error selecting article: {str(e)}")
            continue

    return final_news_list, article_list

def get_news_articles_tool(topics_list: Annotated[list, "The list of topics"], count: Annotated[int, "The number of news articles to collect from the internet"]) -> str:
    google_news = GNews()
    # google_news.max_results = int(floor(count/len(topics_list))) # number of responses for one topic
    google_news.max_results = count # number of responses for one topic
    google_news.language = 'english'  # News in a specific language
    google_news.country = NEWS_COUNTRY  # News from a specific country
    google_news.period = '1h'  # Adjust period in hours

    s = Shortener(timeout=5)
    
    raw_news_list = []
    for topic in topics_list:
        print(f"FETCHING NEWS ON TOPIC: {topic}")
        raw_news = google_news.get_news(topic)
        for news in raw_news:
            news['keyword'] = topic
        raw_news_list.extend(raw_news)
        
    if len(raw_news_list) == 0:
        return None
    
    news_list, article_list = read_news_articles_tool(raw_news_list)
    print(f"ARTICLE LIST len: {len(article_list)}")

    result = ''
    if len(news_list) > 0 and len(article_list) > 0:
        # get the news['url'] for each news
        news_url_list = [news['url'] for news in news_list]
        short_urls = [s.tinyurl.short(url) for url in news_url_list]
        article_text_list = [article.text for article in article_list]

        for i in range(len(news_list)):
            # do this until the result length is less than 30000
            if len(result) > 30000:
                break
            result += ("""NEWS {n} TOPIC: {keyword}
NEWS {n} TITLE: {title}
NEWS {n} CONTENT: {content}
NEWS {n} SOURCE: {url}

"""
        ).format(
            keyword = news_list[i]['keyword'],
            n = i+1,
            title=news_list[i]['title'],
            content=article_text_list[i].replace('\n\n', '\n')[:1000],
            url=short_urls[i]
        )

    return result[:4500]


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
            if not re.search(r'https://tinyurl\.com/[a-zA-Z0-9]{8}', tweet_list[i]): # if the tweet does not contain a source
                if re.search(r'https://tinyurl\.com/[a-zA-Z0-9]{8}', source_list[i]): # if we have a source seperately
                    tweet_list[i] = tweet_list[i][:278-len(source_list[i])]
                    tweet_list[i] += f"\n{source_list[i]}"
    # uncomment below five lines to don't post a news if it doesn't have a source
        #         else:
        #             del_index.append(i)
        # for i in sorted(del_index, reverse=True):
        #     del tweet_list[i]
        #     del source_list[i]
        
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
    # tweet_list = [get_intro_tweet()] + merge_tweets(add_source_urls(tweet_list, source_list))
    tweet_list = [get_intro_tweet()] + add_source_urls(tweet_list, source_list)

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
        topics_list = topics_list[:20] # TESTING

        if len(topics_list)==0:
            raise Exception("No topics found")

        news_articles = get_news_articles_tool(topics_list=topics_list, count=int(ARTICLE_COUNT))
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