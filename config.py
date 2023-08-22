from dotenv import load_dotenv
import os

# Load the environment variables from the .env file
load_dotenv()

# Access the environment variables in your code
PORT = 3978
APP_ID = os.getenv("MicrosoftAppId")
APP_PASSWORD = os.getenv("MicrosoftAppPassword")
BASE_URL = os.getenv("BASE_URL")
DATA_DIR = "data"
RESET_CONFIG = False
VERBOSE = True
