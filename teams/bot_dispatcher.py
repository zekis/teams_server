import traceback
import subprocess
import config
import os
import datetime

from teams.bot_comms import send_to_user, send_to_bot, clear_queue, from_bot_to_dispatcher, from_dispatcher_to_bot_manager, bot_to_user
from teams.user_manager import UserManager
from teams.bot_manager import BotManager
#from teams.credential_manager import CredentialManager
import server_logging

from langchain.agents import initialize_agent, load_tools, Tool
from langchain.agents import AgentType
from langchain.chat_models import ChatOpenAI
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)
from langchain.chains import ConversationChain
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
        self.userManager = UserManager(config.FRAPPE_ENDPOINT, config.FRAPPE_API_KEY, config.FRAPPE_API_SECRET)

        clear_queue(config.DISPATCHER_CHANNEL_ID)
       
        
    def run(self, user_message: str, user_id: str, user_name, tenant_id: str, email_address: str):
        "all prompts are processed here by checking registration and then dispatching to a bot"
        registration_request = self.register_new_user(user_message, user_id, user_name, tenant_id, email_address)
        
        #if not issues
        if not registration_request:
            response = self.dispatcher(user_message, user_id)
            if response:
                return response
        else:
            return registration_request

        
    
    def register_new_user(self, user_message: str, user_id: str, user_name: str, tenant_id: str, email_address: str) -> str:
        """Call this when we receive a message and check the user has all their settings,
        If not, request their details and save to credential manager
        we need their API key to trigger the other bots"""

        #for all the users in the DB, which one has just send us a message
        # try:
        user_data = self.userManager.get_user(user_id)
        #user must exist in DB
        if user_data:
        #are we waiting on a response
        
            if user_data.waiting_for_response_credential == "":
                if not self.userManager.get_credential(user_id, 'openai_api'):
                    self.logger.info(f"API key missing")
                    user_data.waiting_for_response_credential = "openai_api"
                    
                if not user_data.teams_user_default_model:
                    self.logger.info(f"Model missing")
                    user_data.waiting_for_response_credential = "model"
        
            if user_data.waiting_for_response_credential == "openai_api":

                #check the last message is our API key
                if self.is_api_key_valid(user_message):
                    self.userManager.add_credential(user_id, "openai_api", user_message)
                    self.userManager.add_credential(user_id, "tenant_id", tenant_id)
                    self.userManager.add_credential(user_id, "user_name", user_name)
                    self.userManager.add_credential(user_id, "email_address", email_address)
                    user_data.waiting_for_response_credential = ""
                    #add known teams credentials
                else:
                    user_data.waiting_for_response_credential = "openai_api"
                    return "API key invalid, please enter your Open AI API key again"
            
            # if user_data.waiting_for_response_credential == "model":

            #     #check the last message is our API key
            #     if self.is_valid_model(user_message):
            #         user_data.teams_user_default_model = user_message
            #         user_data.waiting_for_response_credential = ""
                    
            #         return "Model saved, How may I help you?"
            #     else:
            #         user_data.waiting_for_response_credential = "model"
            #         return "Model invalid, please enter a valid model (Valid models include gpt-4, gpt-3.5-turbo-16k, gpt-3.5-turbo)"


            #this function checks if the bot is waiting for the user to input a credential.
            #saves the credential and checks if another is pending. otherwise sends the original message on to the bot.
            if user_data.waiting_for_response_credential != "":
                bot_id = user_data.waiting_for_response_credential_bot_id
                self.userManager.add_credential(user_id, user_data.waiting_for_response_credential, user_message)
                user_data.waiting_for_response_credential = ""
                
                missing_credential = self.get_missing_credential(bot_id, user_id)
                #we have everything we need
                if not missing_credential:
                    send_to_bot(bot_id, user_id, user_data.last_request, self.get_required_credentials(bot_id, user_id))
                    user_data.waiting_for_response_credential_bot_id = ""
                    send_to_user(f"Got what I need, sending request to {bot_id} bot", user_id)
                    return False
                else:
                    user_data.waiting_for_response_credential = missing_credential
                    return f"Please provide {missing_credential} for the {bot_id} bot"

        
        #if the user doesnt exist or the user does exist but has no credentials    
        else:
            #user not in DB, better create one        
            self.logger.info(f"User not found in database. Adding new user {user_name} - {user_id}")
            user_created = self.userManager.add_user(user_id, user_name)
            new_user = self.userManager.get_user(user_id)
            #and request first credential
            new_user.waiting_for_response_credential = "openai_api"
            return f"Welcome {user_name}, please enter your Open AI key to get started"

                    
        # except Exception as e:
        #     self.logger.error(f"{e} \n {traceback.format_exc()}")    

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
                
                if command == "register":
                    self.logger.debug(f"command: {message}")
                    bot_data = message.get('data')
                    bot_description = bot_data.get('description')
                    bot_credentials = bot_data.get('required_credentials')
                    self.botManager.add_bot(bot_id, bot_description, bot_credentials)
                    from_dispatcher_to_bot_manager(bot_id,"registered", datetime_str)

                    
                    

                #The bot user instance has completed its work
                if command == "end":
                    user_id = message.get('data')
                    user_data = self.userManager.get_user(user_id)
                    #user_data.active_bot = ""
                    
            if prompt:
                self.logger.info(f"prompt: {message}")
                user_data = self.userManager.get_user(user_id)
                #Bot has responded so update no_response to 0
                user_data.no_response = 0
                #send the whole message and let teams deal with it
                bot_to_user(message, user_id)

            #bot manager is still alive
            self.botManager.update_bot_registration_time(bot_id)

        #cleanup dead bot managers
        self.botManager.remove_old_bots()
        
    def dispatcher(self, user_message: str, user_id):
        "check user already has a bot running, if not, determine which one to start"
        self.logger.info(user_message)

        user_data = self.userManager.get_user(user_id)

        if self.user_commands(user_message, user_id):
            #command was used, break
            return False

        # if int(user_data.no_response) > config.MAX_IGNORED_USER_MESSAGE:
        #     send_to_user("Assistant is busy or is unable to respond. Lets reconsider if this was the right assistant for the job...", user_id)

        # if user_data.active_bot == "" or user_data.active_bot == "dispatcher" or int(user_data.no_response) > config.MAX_IGNORED_USER_MESSAGE:
        #     user_data.no_response = 0
        #     send_to_user("You currently do not have active assistants", user_id)
        #     api_key = user_data.credentialManager.get_credential('openai_api')
        #     self.logger.debug(user_data.credentialManager.get_credential('openai_api'))
        #     #self.logger.debug(api_key)
        api_key = self.userManager.get_credential(user_id, 'openai_api')
        if not api_key:
            self.logger.debug("API key missing")
            send_to_user("It seems I dont have a copy of your open API key", user_id)
            user_data.waiting_for_response_credential = "openai_api"
            
            return "API key missing"

        response = self.model_response(user_message, api_key, user_data.teams_user_default_model)
        self.logger.info(f"Model response: {response}")

        if response:
            #validate response
            self.logger.info(f"Searching for registered bots")
            for bot in self.botManager.bots:
                
                if bot.bot_id.lower() in response.lower():
                    #user_data.active_bot = bot.bot_id
                    #if we have all the bots creds then 
                    missing_credential = self.get_missing_credential(bot.bot_id, user_id)
                    if not missing_credential:
                        user_data.last_request = user_message
                        send_to_bot(bot.bot_id, user_id, user_message, self.get_required_credentials(bot.bot_id, user_id))
                        send_to_user(f"I think the {response} assistant should be able to assist with your request", user_id)
                        self.logger.info(f"Bot started {response}")
                        return False
                    else:
                    #otherwise we need to request the next missing cred
                        user_data.waiting_for_response_credential = missing_credential
                        user_data.waiting_for_response_credential_bot_id = bot.bot_id
                        return f"Please provide {missing_credential} for the {bot.bot_id} bot"
                    

            #invalid response
            #self.logger.info(f"Model invalid response {response}")
            response = self.default_response(user_message, api_key, user_data.teams_user_default_model)
            return response
            #send_to_user("I could not find an available assistant to help with your request", user_id)
            #return True
            
        #no response
        self.logger.info(f"Model invalid response {response}")
        send_to_user("I could not find an available assistant to help with your request", user_id)
        return False
    
    def get_required_credentials(self, bot_id, user_id):
        "for the registered bots required credentials, create a prompt_package containing the name, value pairs"
        user_data = self.userManager.get_user(user_id)
        bot_data = self.botManager.get_bot(bot_id)

        credential_package = []
        for cred in bot_data.required_credentials:
            if self.userManager.get_credential(user_id, cred):
                #add the cred name and the value
                credential_package.append({cred: self.userManager.get_credential(user_id, cred)})
        return credential_package

    def get_missing_credential(self, bot_id, user_id):
        "for the registered bots required credentials, check that all cred names have value pairs"
        user_data = self.userManager.get_user(user_id)
        bot_data = self.botManager.get_bot(bot_id)

        for cred in bot_data.required_credentials:
            if not self.userManager.get_credential(user_id, cred):
                return cred
        return None

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
    
    def default_response(self, user_message: str, api_key: str, openai_model: str) -> str:
        
        try:
            os.environ["OPENAI_API_KEY"] = api_key
            chat = ChatOpenAI()
            conversation = ConversationChain(llm=chat)  
            response = conversation.run(user_message)
            # llm = ChatOpenAI(temperature=0, model_name=openai_model, verbose=config.VERBOSE)
            # tools = load_tools(["human"], llm=llm)

            # available_bots = "default, "
            # for bot in self.botManager.bots:
            #     available_bots = f"'{bot.bot_id} description: {bot.bot_description}', {available_bots}" 
            # prompt = f"""Given the following user request, identify which assistant should be able to assist. return only the assistant name
            
            # request: {user_message}

            # assistants: {available_bots}"""
            # self.logger.info(prompt)

            # agent_executor = initialize_agent(tools, llm, agent=AgentType.OPENAI_FUNCTIONS, verbose=True, agent_kwargs = {
            #         "input_variables": ["input", "agent_scratchpad"]
            #     })

            return response
        
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
                    
                    if sub_command:
                        bot_command = user_command.split()[2]
                        #forward to bot
                        creds = self.get_required_credentials(sub_command, user_id)
                        send_to_bot(sub_command, user_id, bot_command, creds)
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



