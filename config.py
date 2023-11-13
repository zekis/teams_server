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
VERBOSE = False

MAIN_AI = "gpt-4"
TOOL_AI = "gpt-4"
SMART_AI = "gpt-4"


MAX_IGNORED_USER_MESSAGE = 2
DISPATCHER_CHANNEL_ID = "botmanager"

OWNER = os.getenv("OWNER")
FRAPPE_ENDPOINT = os.getenv("FRAPPE_ENDPOINT")
FRAPPE_API_KEY = os.getenv("FRAPPE_API_KEY")
FRAPPE_API_SECRET = os.getenv("FRAPPE_API_SECRET")

GOOGLE_API_KEY = os.getenv("google_api_key")
GOOGLE_CSE_ID = os.getenv("google_cse_id")