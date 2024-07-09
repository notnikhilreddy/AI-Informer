# AI Informer

AI Informer is a project that aims to create a Twitter bot capable of providing informative and interesting content to its followers.

## Features

- **Web Scraping and Summarization**: The bot scrapes the web for the latest news about AI through Google News and automatically summarizes it as a Twitter post.
- **Scheduled Posting**: The bot is programmed to post tweets once an hour throughout the day, ensuring a consistent flow of content.

## Installation

To install and run the AI Informer bot locally, follow these steps:

1. Clone the repository:

    ```bash
    git clone https://github.com/notnikhilreddy/AI-Informer.git
    ```

2. Install the required dependencies:

    ```bash
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

3. Configure the bot:

# Configure the bot:
Create a new file named `.env` in the root directory of the project and add the following environment variables:

GROQ_API_BASE
GROQ_MODEL_NAME
GROQ_API_KEY

RELEASE='PROD'

XUSERNAME
XEMAIL
XPASSWORD

4. Start the bot:

    ```bash
    python main.py
    ```

Contributions are welcome!

## Contact

If you have any questions or suggestions, feel free to reach out to us at ai.informer00@gmail.com

Happy tweeting!