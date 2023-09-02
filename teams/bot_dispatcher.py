import traceback
import subprocess
import config
import os
import datetime

from teams.bot_comms import send_to_user, send_to_bot, clear_queue, from_bot_to_dispatcher, from_dispatcher_to_bot_manager
from teams.user_manager import UserManager
from teams.bot_manager import BotManager
from teams.credential_manager import CredentialManager
import server_logging

from langchain.agents import initialize_agent, load_tools, Tool
from langchain.agents import AgentType
from langchain.chat_models import ChatOpenAI
#for testing the api
import openai

import langchain
langchain.debug = config.VERBOSE

class BotDispatcher:
    "this manager starts the bots"
    


    def __init__(self):
        self.logger = server_logging.logging.getLogger('BotDispatcher') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init BotDispatcher")
        self.botManager = BotManager()
        self.userManager = UserManager(config.DATA_DIR)

        clear_queue(config.DISPATCHER_CHANNEL_ID)
       
        
    def run(self, user_message: str, user_id: str, user_name, tenant_id: str, email_address: str):
        "all prompts are processed here by checking registration and then dispatching to a bot"
        registration_request = self.register_new_user(user_message, user_id, user_name, tenant_id, email_address)
        
        #if not issues
        if not registration_request:
            self.dispatcher(user_message, user_id)
        else:
            return registration_request

        
    
    def register_new_user(self, user_message: str, user_id: str, user_name: str, tenant_id: str, email_address: str) -> str:
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
                        user_data.credentialManager.add_credential("openai_api", user_message)
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
                #add known teams credentials
                new_user.credentialManager.add_credential("tenant_id", tenant_id)
                new_user.credentialManager.add_credential("user_name", user_name)
                new_user.credentialManager.add_credential("email_address", email_address)
                #and request first credential
                new_user.waiting_for_response_credential = "openai_api"
                return f"Welcome {user_name}, please enter your Open AI key to get started"

                    
        except Exception as e:
            self.logger.error(f"{e} \n {traceback.format_exc()}")    

    def process_bot_messages(self):
        datetime_str = str(datetime.datetime.now())
        message = from_bot_to_dispatcher(config.DISPATCHER_CHANNEL_ID)

        if message:
            
            bot_id = message.get('bot_id')
            user_id = message.get('user_id')
            prompt = message.get('prompt')
            command = message.get('command')

            

            if command:
                #The bot manager has started
                self.logger.info(f"{message}")
                if command == "register":
                    bot_data = message.get('data')
                    bot_description = bot_data.get('description')
                    bot_credentials = bot_data.get('required_credentials')
                    self.botManager.add_bot(bot_id, bot_description, bot_credentials)
                    from_dispatcher_to_bot_manager(bot_id,"registered", datetime_str)

                #The bot user instance has completed its work
                if command == "end":
                    user_id = message.get('data')
                    user_data = self.userManager.get_user(user_id)
                    user_data.active_bot = ""
                    
            if prompt:
                self.logger.info(f"{message}")
                user_data = self.userManager.get_user(user_id)
                #Bot has responded so update no_response to 0
                user_data.no_response = 0
                send_to_user(prompt, user_id)

            #bot manager is still alive
            self.botManager.update_bot_registration_time(bot_id)

        #cleanup dead bot managers
        self.botManager.remove_old_bots()
        
    def dispatcher(self, user_message: str, user_id):
        "check user already has a bot running, if not, determine which one to start"
        self.logger.info("user_message")

        user_data = self.userManager.get_user(user_id)

        if self.user_commands(user_message, user_id):
            #command was used, break
            return

        if int(user_data.no_response) > config.MAX_IGNORED_USER_MESSAGE:
            send_to_user("Assistant is busy or is unable to respond. Lets reconsider if this was the right assistant for the job...", user_id)

        if user_data.active_bot == "" or user_data.active_bot == "dispatcher" or int(user_data.no_response) > config.MAX_IGNORED_USER_MESSAGE:
            user_data.no_response = 0
            api_key = user_data.credentialManager.get_credential('openai_api')
            self.logger.debug(user_data.credentialManager.get_credential('openai_api'))
            #self.logger.debug(api_key)
            if not api_key:
                self.logger.debug("API key missing")
                user_data.waiting_for_response_credential = "openai_api"
                return "API key missing"

            response = self.model_response(user_message, api_key, user_data.default_model)
            self.logger.info(f"Model response: {response}")

            if response:
                #validate response
                self.logger.info(f"Searching for registered bots")
                for bot in self.botManager.bots:
                    
                    if response.lower() == bot.bot_id.lower():
                        user_data.active_bot = response
                        send_to_bot(user_data.active_bot, user_id, user_message, self.get_required_credentials(user_data.active_bot, user_id))
                        self.logger.info(f"Bot started {response}")
                        return True
                    if response.lower() == "default":
                        "use default bot"
                        send_to_user("I could not find an available assistant to help with your request", user_id)
                        self.logger.info(f"Bot started {response}")
                        return True
                send_to_user(response, user_id)
            return False

        else:
            #bot already assigned
            user_data.no_response = user_data.no_response + 1
            send_to_bot(user_data.active_bot, user_id, user_message, self.get_required_credentials(user_data.active_bot, user_id))
    
    def get_required_credentials(self, bot_id, user_id):
        "for the registered bots required credentials, create a prompt_package containing the name, value pairs"
        user_data = self.userManager.get_user(user_id)
        bot_data = self.botManager.get_bot(bot_id)

        credential_package = []
        for cred in bot_data.required_credentials:
            if user_data.credentialManager.get_credential(cred):
                #add the cred name and the value
                credential_package.append({cred: user_data.credentialManager.get_credential(cred)})
        return credential_package

    def model_response(self, user_message: str, api_key: str, openai_model: str) -> str:
        
        try:
            os.environ["OPENAI_API_KEY"] = api_key
            llm = ChatOpenAI(temperature=0, model_name=openai_model, verbose=config.VERBOSE)
            tools = load_tools(["human"], llm=llm)

            available_bots = "default, "
            for bot in self.botManager.bots:
                available_bots = f"'{bot.bot_id} description: {bot.bot_description}', {available_bots}" 
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

    def user_commands(self, user_message: str, user_id):
        
        if user_message:
            user_command = user_message.lower()
            if user_id == config.OWNER:
                keyword = user_command.split()[0]
                
                if keyword == "botman":
                    sub_command = user_command.split()[1]
                    response = "unknown command"
                    #ls
                    if sub_command == 'ls':
                        response = ""
                        for bot in self.botManager.bots:
                            response = str(bot) + "\n" + response
                        
                        send_to_user(response, user_id)
                    return True
                if keyword == "userman":
                    sub_command = user_command.split()[1]
                    response = "unknown command"
                    #ls
                    if sub_command == 'ls':
                        response = ""
                        for user in self.userManager.users:
                            response = str(user) + "\n" + response
                        
                        send_to_user(response, user_id)
                    return True
        return False



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



