from dotenv import load_dotenv
from autogen import UserProxyAgent, AssistantAgent
from twikit import Client
import os

keyword = "Artificial Intelligence"
article_count = 10
topic_count = 10
max_period_hours = 3
news_country = "US"

# Load environment variables
load_dotenv()
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_BASE = os.getenv("GROQ_API_BASE")
RELEASE = os.getenv("RELEASE")

if(RELEASE == "PROD"):
    USERNAME = os.getenv("XUSERNAME")
    EMAIL = os.getenv("XEMAIL")
    PASSWORD = os.getenv("XPASSWORD")
else:
    USERNAME = os.getenv("XUSERNAME_TEST")
    EMAIL = os.getenv("XEMAIL_TEST")
    PASSWORD = os.getenv("XPASSWORD_TEST")

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
if 'x_client' not in globals():
    x_client = Client('en-US')

    x_client.login(
        auth_info_1=USERNAME,
        auth_info_2=EMAIL,
        password=PASSWORD
    )
    print("Client initialized")


import random
from newspaper import Article
import pandas as pd
import os

urls_file = '.cache/urls.csv'

def select_random_article(news_list):
    if not os.path.isfile(urls_file):
        df_urls = pd.DataFrame(columns=['urls', 'status'])  # Define the variable with a default value
        df_urls.to_csv(urls_file)
    else:
        df_urls = pd.read_csv(urls_file, index_col='Unnamed: 0')
    news, article = None, None
    
    while True:
        print(f'NEWS LIST: {news_list}')
        #remove any news from the news_list if it is already in the csv file
        news_list = [news for news in news_list if news['url'] not in df_urls['urls'].values]
        print(f'FILTERED NEWS LIST: {news_list}')
        if not news_list:
            print("No more news to select")
            return None, None
        
        news = random.choice(news_list)
        try:
            # Code to check if the article is valid
            # For example, you can check if the URL is accessible or if the content is not empty
            # If the article is valid, return it
            # Otherwise, continue to the next iteration of the loop
            article = Article(news['url'])
            article.download()
            article.parse()

            if article.text and len(article.text.strip().split('\n')) > 1:
                # Append the URL and status to the DataFrame
                df_urls = pd.concat([pd.DataFrame([[news['url'], 'success']], columns=df_urls.columns), df_urls], ignore_index=True)
                df_urls.to_csv(urls_file)
                break
            else:
                df_urls = pd.concat([pd.DataFrame([[news['url'], 'empty']], columns=df_urls.columns), df_urls], ignore_index=True)
                df_urls.to_csv(urls_file)
                continue
        except Exception as e:
            # Append the URL and status to the DataFrame
            df_urls = pd.concat([pd.DataFrame([[news['url'], 'error']], columns=df_urls.columns), df_urls], ignore_index=True)
            df_urls.to_csv(urls_file)
            print(f"Error selecting article: {str(e)}")
            continue
    return news, article


from typing import Annotated
from gnews import GNews
from pyshorteners import Shortener

topics_file = '.cache/topics.csv'

#reset the topics
if os.path.isfile(topics_file):
    os.remove(topics_file)

def topic_selection_tool(topics_list: Annotated[list, "The list of topics"] = None) -> str:
    #set df_topics topic column from the topics_list and set status to pending if it's not already in the df_topics
    if os.path.isfile(topics_file):
        df_topics = pd.read_csv(topics_file, index_col='Unnamed: 0')
    else:
        df_topics = pd.DataFrame(columns=['topic', 'status'])  # Define the variable with a default value
    if topics_list:
        for topic in topics_list:
            if topic not in df_topics['topic'].values:
                df_topics = pd.concat([df_topics, pd.DataFrame([[topic, 'pending']], columns=df_topics.columns)], ignore_index=True)
    
    topics_list = df_topics[df_topics['status'] == 'pending']['topic'].values.tolist()
    if(len(topics_list) == 0):
        return "No more topics to select"
    
    topic_selected = random.choice(topics_list)
    df_topics.loc[df_topics['topic'] == topic_selected, 'status'] = 'selected'
    
    df_topics.to_csv(topics_file)
    return topic_selected

def get_news_article_tool(topic: Annotated[str, "The topic to collect news on"], count: Annotated[int, "The number of news articles to collect from the internet"]) -> str:
    google_news = GNews()
    google_news.max_results = count  # number of responses across a keyword
    google_news.language = 'english'  # News in a specific language
    google_news.country = news_country  # News from a specific country
    period_hours = 1
    
    while True:
        google_news.period = f'{period_hours}h'  # Adjust period in hours
        news_list = google_news.get_news(topic)
        news, article = select_random_article(news_list)

        if news and article:
            s = Shortener(timeout=5)
            short_url = s.tinyurl.short(news['url'])

            result = (
    """TITLE: {title}

CONTENT: {content}

SOURCE: {url}"""
            ).format(
                title=news['title'],
                content=article.text.replace('\n\n', '\n'),
                url=short_url
            )
            return result
        if period_hours >= max_period_hours:
            topic = topic_selection_tool(None)
            period_hours = 0
        period_hours += 1  # Increase the period by 1 hour and try again
    
# def get_trending_tweets_tool(topic: Annotated[str, "The topic to retrieve tweets on"], count: Annotated[int, "The number of top tweets to collect"]) -> str:
#     tweets = []
#     tweets_batch = x_client.search_tweet(query=topic, product='Top', count=count)

#     while len(tweets) < count:
#         for tweet in tweets_batch:
#             if tweet.lang == 'en' and 't.co/' in tweet.full_text:
#                 tweets.append(tweet.full_text)
#                 if len(tweets) >= count:
#                     break
#         else:
#             tweets_batch = tweets_batch.next()

#     return "\n\n".join(f'Tweet {i+1}: "{tweet}"' for i, tweet in enumerate(tweets))

def write_tweet_tool(tweet: Annotated[str, "The tweet to post"], source: Annotated[str, "The source URL of the news"]) -> str:
    if 'tinyurl.com' in tweet:
        if len(tweet) > 280:
            tweet = tweet[:276-len(source)] + '...' + f"\n{source}"
    else:
        if len(tweet) <= 279-len(source):
            tweet += f"\n{source}"
        else:
            tweet = tweet[:276-len(source)] + '...' + f"\n{source}"

    try:
        if RELEASE != "DEV":
            x_client.create_tweet(
                text=tweet,
            )
        
        return f'Tweet posted: "{tweet}"'
    except Exception as e:
        error_message = f"Failed to post tweet: {str(e)}"
        return error_message


topic_selector_agent = AssistantAgent(
    "topic_selector_agent",
    llm_config=llm_config,
    system_message=f"You are good at writing a list of closely related topics to the given topic(including the given topic) and then choose any one out of them. Use the provided tools for both topic selection and to collect new articles.",
    max_consecutive_auto_reply=1
)

news_collector_agent = AssistantAgent(
    "news_collector_agent",
    llm_config=llm_config,
    system_message=f"You are good at collecting recent news articles about a given topic on the internet. Use the provided tool to collect news about the chosen topic.",
    max_consecutive_auto_reply=1
)

# news_picker_agent = AssistantAgent(
#     "news_picker_agent",
#     llm_config=llm_config,
#     system_message="You are good at picking the most interesting news article from a list of given news articles AS IT IS. Always include the source URL link",
#     max_consecutive_auto_reply=1
# )

# tweets_retriever_agent = AssistantAgent(
#     "tweets_retriever_agent",
#     llm_config=llm_config,
#     system_message="You are good at retrieving recent tweets about a given topic on twitter. Always include source the URL link. Use the provided tool.",
#     max_consecutive_auto_reply=1
# )

tweet_writer_agent = AssistantAgent(
    "tweet_writer_agent",
    llm_config=llm_config,
    system_message="You are an autonomous twitter bot that's designed to post the latest news for everyone. You are good at posting twitter posts on the given news. Always use simple words. Use the provided tool to post a tweet.",
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
topic_selector_agent.register_for_llm(name="topic_selection_tool", description="Generate a list of topics related to the input topic and return a random topic.")(topic_selection_tool)
news_collector_agent.register_for_llm(name="get_news_article_tool", description="Collect news articles about a topic on the internet.")(get_news_article_tool)
# tweets_retriever_agent.register_for_llm(name="get_trending_tweets_tool", description="Collect top trending tweets about a topic on twitter.")(get_trending_tweets_tool)
tweet_writer_agent.register_for_llm(name="write_tweet_tool", description="Write a twitter post.")(write_tweet_tool)

# Register the tool function with the user proxy agent.
user_proxy_agent.register_for_execution(name="topic_selection_tool")(topic_selection_tool)
user_proxy_agent.register_for_execution(name="get_news_article_tool")(get_news_article_tool)
# user_proxy_agent.register_for_execution(name="get_trending_tweets_tool")(get_trending_tweets_tool)
user_proxy_agent.register_for_execution(name="write_tweet_tool")(write_tweet_tool)


try:
    user_proxy_agent.initiate_chats([
            {
                "recipient": topic_selector_agent,
                "message": f"Generate a list of {topic_count} topics related to the topic '{keyword}' and return a random topic from the list.",
                "clear_history": True,
                "silent": False,
                "summary_method": "last_msg"
            },
            {
                "recipient": news_collector_agent,
                "message": f"Collect {article_count} news articles about the given topic from the internet.",
                "clear_history": True,
                "silent": False,
                "summary_method": "last_msg"
            },
            # {
            #     "recipient": news_picker_agent,
            #     "message": "Pick the most interesting news article:",
            #     "clear_history": True,
            #     "silent": False,
            #     "summary_method": "reflection_with_llm",
            # },
            # {
            #     "recipient": tweets_retriever_agent,
            #     "message": f"Retrieve the top {count} trending tweets about the topic '{topic_selected}' from twitter:",
            #     "clear_history": True,
            #     "silent": False,
            #     "summary_method": "last_msg",
            # },
            {
                "recipient": tweet_writer_agent,
                "message": "Write and post a twitter post about the given news article and link to the source.",
                "clear_history": True,
                "silent": False,
                "summary_method": "last_msg"
            }
        ]
    )
except Exception as e:
    print(f"Global Error: {str(e)}")
