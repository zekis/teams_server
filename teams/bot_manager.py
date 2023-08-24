import traceback
import subprocess
import config
import os
from teams.bot_comms import send_to_user, send_to_bot, clear_queue, from_bot_to_dispatcher
from teams.user_manager import UserManager
from teams.credential_manager import CredentialManager
import server_logging

from langchain.agents import initialize_agent, load_tools, Tool
from langchain.agents import AgentType
from langchain.chat_models import ChatOpenAI
#for testing the api
import openai

import langchain
langchain.debug = config.VERBOSE

class BotManager:
    "this manager starts the bots"
    


    def __init__(self):
        self.logger = server_logging.logging.getLogger('BotManager') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init BotManager")
        self.registered_bots = []
        self.user_processes = {}
        self.userManager = UserManager(config.DATA_DIR)
        #testin
        self.bot_register()
        
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

        #for all the users in the DB, which one has just send us a message
        try:
            user_data = self.userManager.get_user(user_id)
            if user_data:
            #are we waiting on a response
            
                if user_data.waiting_for_response_credential == "":
                    if not user_data.credentialManager.get_credential('openai_api'):
                        self.logger.info(f"API key missing")
                        user_data.waiting_for_response_credential = "openai_api"
                        
                    if not user_data.default_model:
                        self.logger.info(f"Model missing")
                        user_data.waiting_for_response_credential = "model"
            
                if user_data.waiting_for_response_credential == "openai_api":

                    #check the last message is our API key
                    if self.is_api_key_valid(user_message):
                        user_data.credentialManager.add_credential("openai_api", {"key": user_message})
                        user_data.waiting_for_response_credential = ""
                        self.userManager.save_users()
                    else:
                        user_data.waiting_for_response_credential = "openai_api"
                        return "API key invalid, please enter your Open AI API key again"
                
                if user_data.waiting_for_response_credential == "model":

                    #check the last message is our API key
                    if self.is_valid_model(user_message):
                        user_data.default_model = user_message
                        user_data.waiting_for_response_credential = ""
                        self.userManager.save_users()
                        return "Model saved, How may I help you?"
                    else:
                        user_data.waiting_for_response_credential = "model"
                        return "Model invalid, please enter a valid model (Valid models include gpt-4, gpt-3.5-turbo-16k, gpt-3.5-turbo)"
                
            else:
                #user not in DB, better create one        
                self.logger.info(f"User not found in database. Adding new user {user_name} - {user_id}")
                user_created = self.userManager.add_user(user_id, user_name)
                
                new_user = self.userManager.get_user(user_id)
                
                #and request first credential
                new_user.waiting_for_response_credential = "openai_api"
                return f"Welcome {user_name}, please enter your Open AI key to get started"

                    
        except Exception as e:
            self.logger.error(f"{e} \n {traceback.format_exc()}")    

    def bot_register(self):
        "bots register themselves via the bot_manager channel"
        self.logger.info("Bot registered")
        self.registered_bots.append("email-task-calander")

    def process_bot_messages(self):
        
        message = from_bot_to_dispatcher(config.DISPATCHER_CHANNEL_ID)
        if message:
            self.logger.info("Message received")
            
            user_id = message.get('user_id')
            prompt = message.get('prompt')

            user_data = self.userManager.get_user(user_id)
            user_data.no_response = 0
            send_to_user(prompt, user_id)
        
    def dispatcher(self, user_message: str, user_id):
        "check user already has a bot running, if not, determine which one to start"
        self.logger.info("user_message")

        user_data = self.userManager.get_user(user_id)

        if user_data.active_bot == "" or user_data.active_bot == "dispatcher" or user_data.no_response > config.MAX_IGNORED_USER_MESSAGE:
            user_data.no_response = 0
            api_key = user_data.credentialManager.get_credential('openai_api').get('parameters', {}).get('key')
            self.logger.debug(user_data.credentialManager.get_credential('openai_api'))
            self.logger.debug(api_key)
            if not api_key:
                self.logger.debug("API key missing")
                user_data.waiting_for_response_credential = "openai_api"
                return "API key missing"

            response = self.model_response(user_message, api_key, user_data.default_model)
            self.logger.info(f"Model response: {response}")

            if response:
                #validate response
                self.logger.info(f"Searching for registered bots")
                for bot in self.registered_bots:
                    
                    if response.lower() == bot.lower():
                        user_data.active_bot = response
                        send_to_bot(config.DISPATCHER_CHANNEL_ID, user_id, user_data.active_bot, user_message)
                        self.logger.info(f"Bot started {response}")
                        return True
                    if response.lower() == "default":
                        "use default bot"
                        user_data.active_bot = response
                        send_to_bot(config.DISPATCHER_CHANNEL_ID, user_id, user_data.active_bot, user_message)
                        self.logger.info(f"Bot started {response}")
                        return True
                send_to_user(response, user_id)
            return False

        else:
            #bot already assigned
            user_data.no_response = user_data.no_response + 1
            send_to_bot(config.DISPATCHER_CHANNEL_ID, user_id, user_data.active_bot, user_message)
        

    def model_response(self, user_message: str, api_key: str, openai_model: str) -> str:
        
        try:
            os.environ["OPENAI_API_KEY"] = api_key
            llm = ChatOpenAI(temperature=0, model_name=openai_model, verbose=config.VERBOSE)
            tools = load_tools(["human"], llm=llm)

            available_bots = "default, "
            for bot in self.registered_bots:
                available_bots = f"'{bot}', {available_bots}" 
            prompt = f"""Given the following user request, identify which assistant should be able to assist. return only the assistant name
            
            request: {user_message}

            assistants: {available_bots}"""
            self.logger.info(prompt)

            agent_executor = initialize_agent(tools, llm, agent=AgentType.OPENAI_FUNCTIONS, verbose=True, agent_kwargs = {
                    "input_variables": ["input", "agent_scratchpad"]
                })

            return agent_executor.run(input=prompt)
        
        except Exception as e:
            self.logger.error(f"{e} \n {traceback.format_exc()}")     


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

    def is_valid_model(self, model: str):
        if model == "gpt-3.5-turbo-16k":
            return True
        else:
            return False