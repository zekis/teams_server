import subprocess
from teams.bot_comms import send_to_user, send_to_bot, clear_queue
from teams.data_models import UserConfig
import openai
import server_logging

class BotManager:
    "this manager starts the bots"
    users = [UserConfig]


    def __init__(self):
        server_logging.logger.info("Bot manager initilised")
        self.user_processes = {}

        
    def run(self, user_message: str, user_id: str, user_name):
        "all prompts are processed here by checking registration and then dispatching to a bot"
        registration_request = self.register_new_user(user_message, user_id, user_name)
        
        #if not issues
        if not registration_request:
            self.dispatcher(user_message, user_id)
        else:
            return registration_request

        
    
    def register_new_user(self, user_message: str, user_id: str, user_name: str) -> str:
        """Call this when we receive a message and check the user has all their settings,
        If not, request their details and save to credential manager
        we need their API key to trigger the other bots"""

        #have we created a user DB
        if not self.users:
            server_logging.logger.info("Initilising user database")
            #no users yet, lets create one
            new_user = UserConfig(user_id, user_name)
            self.users.append(new_user)

        #for all the users in the DB, which one has just send us a message
        user_data = self.get_user_data(user_id)
        if user_data:
            #are we waiting on a response
            if waiting_for_response_credential == "openai_api":

                #check the last message is our API key
                if self.is_api_key_valid(user_message):
                    user_data.credentialManager.add_credential("openai_api", {"key", user_message})
                    user_data.credentialManager.save_credentials()
                    user_data.waiting_for_response_credential = ""
                    return "API key verified and saved"
                else:
                    user_data.waiting_for_response_credential = "openai_api"
                    return "API key invalid, please enter your Open AI API key again"
            else:
                #not waiting for keys but we should check them
                if not user_data.credentialManager.get_credential('openai_api'):
                    server_logging.logger.info(f"API key missing")
                    user_data.waiting_for_response_credential = "openai_api"
                    return "Please enter your Open AI API key"
                else:
                    #registered and good to go
                    return None
        else:
            #user not in DB, better create one        
            server_logging.logger.info(f"User not found in database. Adding new user {user_name} - {user_id}")
            new_user = UserConfig(user_id, user_name)
            
            #and request first credential
            new_user.waiting_for_response_credential = "openai_api"
            self.users.append(new_user)
            return f"Welcome {user_name}, please enter your Open AI key to get started"
        

    def bot_register(self):
        "bots register themselves via the bot_manager channel"

    def dispatcher(self, user_message: str, user_id):
        "check user already has a bot running, if not, determine which one to start"

        #model_response(user_message)

    def get_user_data(self, user_id) -> UserConfig:
        'search the DB for the user_id and return the user object'
        for user in self.users:
            if user.user_id == user_id:
                server_logging.logger.info(f"get_user_data: found user {user_id}")
                return user
        else:
            server_logging.logger.info(f"get_user_data: could not find user {user_id}")
            return None

    def is_api_key_valid(self, api_key: str):
        openai.api_key = api_key
        try:
            response = openai.Completion.create(
                engine="davinci",
                prompt="This is a test.",
                max_tokens=5
            )
        except:
            return False
        else:
            return True