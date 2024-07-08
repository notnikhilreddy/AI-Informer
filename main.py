from dotenv import load_dotenv
from autogen import UserProxyAgent, AssistantAgent
from twikit import Client
import os

# Load environment variables from .env file
load_dotenv()

# Access the environment variables
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_BASE = os.getenv("GROQ_API_BASE")
USERNAME = os.getenv("XUSERNAME")
EMAIL = os.getenv("XEMAIL")
PASSWORD = os.getenv("XPASSWORD")
AUTOGEN_USE_DOCKER = os.getenv("AUTOGEN_USE_DOCKER")

keyword = "AI"
topic_count = 20

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

def select_random_article(news_list):
    while True:
        #remove any news from the news_list if it is already in the csv file
        with open('url.csv', 'r') as f:
            urls = f.readlines()
            urls = [url.strip() for url in urls]
            news_list = [news for news in news_list if news['url'] not in urls]
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
            # save the url in a csv file
            with open('url.csv', 'a') as f:
                f.write(news['url'] + '\n')
            article.download()
            article.parse()
            if article.text:
                return news, article
        except Exception as e:
            # Handle the error, if any
            # You can print the error message or log it for debugging purposes
            print(f"Error selecting article: {str(e)}")


from typing import Annotated
from gnews import GNews

def get_news_article_tool(topic: Annotated[str, "The topic to collect news on"], count: Annotated[int, "The number of news articles to collect from the internet"]) -> str:
    google_news = GNews()
    google_news.max_results = count  # number of responses across a keyword
    google_news.language = 'english'  # News in a specific language
    period_hours = 1
    
    while True:
        google_news.period = f'{period_hours}h'  # Adjust period in hours
        news_list = google_news.get_news(topic)
        news, article = select_random_article(news_list)

        if news and article:
            result = f'''TITLE: {news['title']}\nCONTENT: {article}\nSOURCE: "{news['url']}"'''
            return result
        period_hours += 1  # Increase the period by 1 hour and try again

# def get_news_articles_tool(topic: Annotated[str, "The topic to collect news on"], count: Annotated[int, "The number of news articles to collect from the internet"]) -> str:
#     api_key = "bca2837056064cf9b56163348105b235"
#     url = f"https://newsapi.org/v2/everything?q={topic}&pageSize={count}&language={'en'}&apiKey={api_key}"
#     response = requests.get(url)
    
#     if response.status_code == 200:
#         articles = response.json().get('articles', [])
#         return "\n\n".join([f"Title: {article['title']}\nDescription: {article['description']}\nSource: {article['url']}" for article in articles])
#     else:
#         return "Failed to fetch news articles"
    
def get_trending_tweets_tool(topic: Annotated[str, "The topic to retrieve tweets on"], count: Annotated[int, "The number of top tweets to collect"]) -> str:
    tweets = []
    tweets_batch = x_client.search_tweet(query=topic, product='Top', count=count)

    while len(tweets) < count:
        for tweet in tweets_batch:
            if tweet.lang == 'en' and 't.co/' in tweet.full_text:
                tweets.append(tweet.full_text)
                if len(tweets) >= count:
                    break
        else:
            tweets_batch = tweets_batch.next()

    return "\n\n".join(f'Tweet {i+1}: "{tweet}"' for i, tweet in enumerate(tweets))

def write_tweet_tool(tweet: Annotated[str, "The tweet to post"]) -> str:
    try:

        # x_client.create_tweet(
        #     text=tweet,
        # )
        
        return f'Tweet posted: "{tweet}"'
    except Exception as e:
        error_message = f"Failed to post tweet: {str(e)}"
        return error_message

topic_selector_agent = AssistantAgent(
    "topic_selector_agent",
    llm_config=llm_config,
    system_message=f"You are good at generating a list of topics closely related to a given input keyword. Use the provided tool to pick one random topic from the results.",
    max_consecutive_auto_reply=1
)

news_collector_agent = AssistantAgent(
    "news_collector_agent",
    llm_config=llm_config,
    system_message="You are good at collecting recent news articles about a given topic on the internet and returning one news from the list. Use the provided tool.",
    max_consecutive_auto_reply=1
)

# news_picker_agent = AssistantAgent(
#     "news_picker_agent",
#     llm_config=llm_config,
#     system_message="You are good at picking the most interesting news article from a list of given news articles AS IT IS. Always include the source URL link",
#     max_consecutive_auto_reply=1
# )

tweets_retriever_agent = AssistantAgent(
    "tweets_retriever_agent",
    llm_config=llm_config,
    system_message="You are good at retrieving recent tweets about a given topic on twitter. Always include source the URL link. Use the provided tool.",
    max_consecutive_auto_reply=1
)

# tweets_summarizer_agent = AssistantAgent(
#     "tweets_summarizer_agent",
#     llm_config=llm_config,
#     system_message="You are good at summarizing a list of tweets into one paragraph. You can pick a subset of tweets that are related to each other and omit others. DO NOT add any extra information.",
#     max_consecutive_auto_reply=1
# )

tweet_writer_agent = AssistantAgent(
    "tweet_writer_agent",
    llm_config=llm_config,
    system_message="You are good posting twitter posts about the picked topic. You will always link to the source for all tweets. You will give your opinion where relevant.",
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
# topic_selector_agent.register_for_llm(name="topic_selector_tool", description="Generate a list of topics related to the input topic and return a random topic.")(topic_selector_tool)
news_collector_agent.register_for_llm(name="get_news_article_tool", description="Collect news articles about a topic on the internet.")(get_news_article_tool)
tweets_retriever_agent.register_for_llm(name="get_trending_tweets_tool", description="Collect top trending tweets about a topic on twitter.")(get_trending_tweets_tool)
tweet_writer_agent.register_for_llm(name="write_tweet_tool", description="Write a twitter post.")(write_tweet_tool)

# Register the tool function with the user proxy agent.
# user_proxy_agent.register_for_execution(name="topic_selector_tool")(topic_selector_tool)
user_proxy_agent.register_for_execution(name="get_news_article_tool")(get_news_article_tool)
user_proxy_agent.register_for_execution(name="get_trending_tweets_tool")(get_trending_tweets_tool)
user_proxy_agent.register_for_execution(name="write_tweet_tool")(write_tweet_tool)

article_count = 5
topic_selected = ''

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
            "message": f"Collect {article_count} news articles about the topic '{topic_selected}' from the internet and return a random topic from the list",
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
        # {
        #     "recipient": tweets_summarizer_agent,
        #     "message": "Summarize the list of tweets:",
        #     "clear_history": True,
        #     "silent": False,
        #     "summary_method": "reflection_with_llm",
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
