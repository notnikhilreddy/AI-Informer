import os
import subprocess
from dotenv import load_dotenv

load_dotenv()
VERSION = os.getenv('VERSION')

script_to_run = f'main_v{VERSION}.py'

# Run the selected script
subprocess.run(['python', script_to_run])