import traceback
import subprocess
import config
import os
import datetime

from teams.bot_comms import send_to_user, send_to_bot, clear_queue, from_bot_to_dispatcher, from_dispatcher_to_bot_manager, bot_to_user, publish_settings_list, publish_setting_card, publish_bot_rego_card
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
    "This manager recieves messages from the users and forwards them to bots"
    "It handles user and bot registrations"
    
    

    def __init__(self):
        self.logger = server_logging.logging.getLogger('BotDispatcher') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init BotDispatcher")
        self.botManager = BotManager(config.FRAPPE_ENDPOINT, config.FRAPPE_API_KEY, config.FRAPPE_API_SECRET)
        self.userManager = UserManager(config.FRAPPE_ENDPOINT, config.FRAPPE_API_KEY, config.FRAPPE_API_SECRET)

        clear_queue(config.DISPATCHER_CHANNEL_ID)
       
        
    def run(self, user_message: str, user_id: str, user_name, tenant_id: str, email_address: str):
        "all prompts are processed here by checking registration and then dispatching to a bot"
        registration_request = self.register_new_user(user_message, user_id, user_name, tenant_id, email_address)
        
        #if not issues
        if not registration_request:
            self.logger.info(f"Register check passed for {user_name}")
            response = self.dispatcher(user_message, user_id)
            if response:
                self.logger.info(f"response: {response}")
                return response
        else:
            self.logger.info(f"Register check failed for {user_name}")
            return registration_request

        
    
    def register_new_user(self, user_message: str, user_id: str, user_name: str, tenant_id: str, email_address: str) -> str:
        """Call this when we receive a message and check the user has all their settings,
        If not, request their details and save to credential manager
        we need their API key to trigger the other bots"""
        self.logger.info(f"Register check for {user_name}")
        #for all the users in the DB, which one has just send us a message
        
        user_data = self.userManager.get_user(user_id)
        #Does the user exist in DB
        if user_data:
        #are we waiting on a response
        
            if user_data.waiting_for_response_credential == "":
                if not self.userManager.get_credential(user_id, 'openai_api'):
                    self.logger.info(f"API key missing")
                    user_data.waiting_for_response_credential = "openai_api"
        
            if user_data.waiting_for_response_credential == "openai_api":

                #check the last message is our API key and set all defaults
                if self.is_api_key_valid(user_message):
                    self.set_default_credentials(user_id, user_message, tenant_id, user_name, email_address)
                    user_data.waiting_for_response_credential = ""
                    # if not self.send_registered_bots(user_id):
                    return "API key accepted"

                else:
                    user_data.waiting_for_response_credential = "openai_api"
                    return "API key invalid, please enter your Open AI API key again"
            
            
            #this function checks if the bot is waiting for the user to input a credential.
            #saves the credential and checks if another is pending. otherwise sends the original message on to the bot.
            if user_data.waiting_for_response_credential != "":
                bot_id = user_data.waiting_for_response_credential_bot_id
                self.userManager.add_credential(user_id, user_data.waiting_for_response_credential, user_message)
                user_data.waiting_for_response_credential = ""
                
                missing_credential_name, missing_credential_description = self.get_missing_credential(bot_id, user_id)
                #we have everything we need
                if not missing_credential_name:
                    self.send_to_bot(bot_id, user_id, user_data.last_request)
                    user_data.waiting_for_response_credential_bot_id = ""
                    return f"Got what I need, sending request to {bot_id} bot"
                else:
                    user_data.waiting_for_response_credential = missing_credential_name
                    return f"Please provide {missing_credential_name} for the {bot_id} bot. {missing_credential_description}"

        
        #if the user doesnt exist or the user does exist but has no credentials    
        else:
            #user not in DB, better create one
            self.logger.info(f"User not found in database. Adding new user {user_name} - {user_id}")

            user_created = self.userManager.add_user(user_id, user_name)
            new_user = self.userManager.get_user(user_id)

            #and request first credential
            new_user.waiting_for_response_credential = "openai_api"
            return f"Welcome {user_name}, please enter your Open AI key to get started"

    def send_available_bots(self, user_id):
        #list available bots
        available_bots = self.botManager.get_bots_api()
        summary = []
        for bot in available_bots:
            summary.append((bot.get('name'), f'botman {bot.get("name")} register'))
                    
        publish_settings_list('Available bots', user_id, f'Select a bot to register', summary, "Register")
            

    def get_registered_bots(self, user_id):
        # check if the user has any registered bots
        registered_bots = self.userManager.get_registered_bots(user_id)
        if registered_bots:
            return registered_bots
        else:
            return False
                    
  
    def set_default_credentials(self, user_id, open_ai_key=None, tenant_id = None, user_name = None, email_address = None):
        if open_ai_key: 
            self.userManager.add_credential(user_id, "openai_api", open_ai_key)
        if tenant_id: 
            self.set_default_credential(user_id, "tenant_id", tenant_id)
        if user_name: 
            self.set_default_credential(user_id, "user_name", user_name)
        if email_address: 
            self.set_default_credential(user_id, "email_address", email_address)

        self.set_default_credential(user_id, "app_id", config.APP_ID)
        self.set_default_credential(user_id, "app_secret", config.APP_PASSWORD)

        self.set_default_credential(user_id, "folder_to_monitor", 'inbox')
        self.set_default_credential(user_id, "ignore_domains", ',')
        self.set_default_credential(user_id, "auto_draft_reply", 'No')
        self.set_default_credential(user_id, "time_zone", 'Australia/Perth')
        self.set_default_credential(user_id, 'bots_todo_folder', 'Bot_Tasks')
        self.set_default_credential(user_id, 'auto_read_emails', 'No')
    
        self.set_default_credential(user_id, 'google_api_key', config.GOOGLE_API_KEY)
        self.set_default_credential(user_id, 'google_cse_id', config.GOOGLE_CSE_ID)

    def set_default_credential(self, user_id, settings, value):
        if self.userManager.get_credential(user_id, settings) == "":
            self.userManager.add_credential(user_id, settings, value)

    def send_to_bot(self, bot_id: str, user_id: str, message: str):
        #check bot exists
        available_bots = self.botManager.get_bots_api()
        for available_bot in available_bots:

            available_bot_name = available_bot.get('name')
            if available_bot_name.lower() in bot_id.lower():
                self.logger.info(f"Bot Available {bot_id}")
                #check bot is registered
                registered_bots = self.userManager.get_registered_bots(user_id)

                #if user has no bots registered, send the whole list
                if registered_bots == None:
                    self.logger.info(f"No Registered Bots for {user_id}")
                    self.send_available_bots(user_id)
                    return True

                self.logger.info(f"Registered bots {registered_bots}")
                for bot in registered_bots:
                
                    user_bot_id = bot.get('bot_id')
                    user_bot_enabled = bot.get('bot_enabled')
                    #check user has bot enabled
                    if user_bot_id.lower() in bot_id.lower():
                        self.logger.info(f"Found Registered Bot {bot_id}")
                        if user_bot_enabled:
                            self.logger.info(f"Bot Enabled {bot_id}")
                            #check user has all the credentials
                            self.set_default_credentials(user_id)
                            missing_credential_name, missing_credential_description = self.get_missing_credential(user_bot_id, user_id)
                                        
                            # Send to bot
                            if not missing_credential_name:
                                self.logger.info(f"Send to bot {bot_id}")
                                send_to_bot(user_bot_id, user_id, message, self.get_required_credentials(user_bot_id, user_id)) 
                                return True
                            else:
                                #otherwise we need to request the next missing cred
                                self.logger.info(f"Bot Credential Missing {missing_credential_name}")
                                user_data.waiting_for_response_credential = missing_credential_name
                                user_data.waiting_for_response_credential_bot_id = bot_name
                                send_to_user(f"Please provide {missing_credential_name} for the {bot_name} bot. {missing_credential_description}", user_id)
                                return True
                        else:
                            #Not enabled
                            publish_bot_rego_card(user_id, bot_id, f"The {bot_id} bot is registered but not enabled for you. Would you like to enable it?")
                            return True
                    
                #Bot not registered with user
                publish_bot_rego_card(user_id, bot_id, f"A new {bot_id} bot is available. Would you like to enable it?")
                return True
        #bot doesnt exist
        return False
        


    def process_bot_messages(self):

        datetime_str = str(datetime.datetime.now())
        message = from_bot_to_dispatcher(config.DISPATCHER_CHANNEL_ID)

        if message:
            
            bot_id = message.get('bot_id')
            user_id = message.get('user_id')
            prompt = message.get('prompt')
            command = message.get('command')

            
                

            if command:
                # bot has registered itself. 
                if command == "register":
                    self.logger.debug(f"command: {message}")
                    bot_data = message.get('data')
                    bot_description = bot_data.get('description')
                    bot_credentials = bot_data.get('required_credentials')
                    self.logger.debug(f"Bot registered: {bot_id}")
                    # FYI User manager doesnt handle adding existing user but add_bot does
                    # Register occurs when dispatcher requests it from a bot
                    self.botManager.add_bot(bot_id, bot_description, bot_credentials)
                    # Add to Frappe
                    self.botManager.add_bot_api(bot_id, bot_description, bot_credentials)

                    from_dispatcher_to_bot_manager(bot_id,"registered", datetime_str)

                    self.botManager.update_bot_registration_time(bot_id)

                    # Lets auto start bots for our users using a command
                    # this will start automated scheduled tasks
                    for user in self.userManager.users:
                        self.logger.info(user)
                        self.send_to_bot(bot_id, user, 'start_scheduled_tasks')
                        # registered_bots = self.userManager.get_registered_bots(user)
                        # self.logger.info(registered_bots)
                        # # Check if bot enabled, if not just recommend enabling the bot
                        # for bot in registered_bots:
                        #     bot_name = bot.get('bot_id')
                        #     bot_enabled = bot.get('bot_enabled')

                        #     if bot_name.lower() == bot_id.lower():
                        #         if bot_enabled:
                        #             self.set_default_credentials(user)
                        #             missing_credential_name, missing_credential_description = self.get_missing_credential(bot_name, user)
                                    
                        #             # The user already has all the credentials, Lets start the bot
                        #             if not missing_credential_name:
                        #                 self.logger.debug(f"Starting Scheduled Tasks for {bot_name}")
                        #                 send_to_bot(bot_name, user, 'start_scheduled_tasks', self.get_required_credentials(bot_name, user))
                        #                 return
                                    
                        #         else:
                        #             return
                        # # Not registered or not enabled
                        # publish_bot_rego_card(user_id, bot_name, f"A new bot {bot_name} is now available. Would you like to enable it?")
                    return
                        
                                        
                

                if command == "forward":
                    self.logger.info(f"command: {message}")
                    bot_data = message.get('data')
                    bot_forward_user_id = bot_data.get('bot_user_id')
                    bot_forward_id = bot_data.get('bot_forward_id')
                    bot_prompt = bot_data.get('bot_prompt')
                    if bot_forward_id == "":
                        self.dispatcher(bot_prompt,bot_forward_user_id)
                    else:
                        #send_to_bot(bot_forward_id, bot_forward_user_id, bot_prompt, self.get_required_credentials(bot_forward_id, bot_forward_user_id))
                        self.send_to_bot(bot_forward_id, bot_forward_user_id, bot_prompt)
                    

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
            if not self.botManager.update_bot_registration_time(bot_id):
                # Bot unknown, request register
                from_dispatcher_to_bot_manager(bot_id,"unknown_bot_id", datetime_str)
                # Dont continue
                
        #cleanup dead bot managers
        self.botManager.remove_old_bots()
        
    def dispatcher(self, user_message: str, user_id):
        
        self.logger.info(user_message)
        
        # Return the users credentials and registered bots
        user_data = self.userManager.get_user(user_id)
        user_data.last_request = user_message

        # Run the message past our debug commands
        command_response = self.user_commands(user_message, user_id)
        if command_response:
            #command was used, break or wait (typing indicator)
            if command_response == 'wait':
                return command_response
            return False
        
        # No registered bots
        if not self.get_registered_bots(user_id):
            self.send_available_bots(user_id)
            return False

        # We cant determine which bot to use without openAI as a minimum
        # So we must get a key from the user
        api_key = self.userManager.get_credential(user_id, 'openai_api')
        if not api_key:
            self.logger.debug("API key missing")
            send_to_user("It seems I dont have a copy of your open API key", user_id)
            user_data.waiting_for_response_credential = "openai_api"
            return "API key missing"

        # Run the user request through an LLM
        # Do we allow the model to consider all bots, or just the ones enabled for the user?
        response = self.model_response(user_message, api_key, user_data.teams_user_default_model)
        
        self.logger.info(f"Model response: {response}")

        # Line it up with a bot
        if response:
            #validate response
            self.logger.info(f"Searching for registered bots")
            
            if self.send_to_bot(response, user_id, user_message):
                return 'wait'


            # registered_bots = self.userManager.get_registered_bots(user_id)
            # self.logger.info(registered_bots)
            # # Check if bot enabled, if not just recommend enabling the bot
            # for bot in registered_bots:
                
            #     if bot.get('bot_id').lower() in response.lower():
            #         # Todo: Check if the user has this bot enabled
            #         bot_name = bot.get('bot_id')
            #         bot_enabled = bot.get('bot_enabled')

            #         if bot_enabled:
            #             # if we have all the bots creds then 
            #             missing_credential_name, missing_credential_description = self.get_missing_credential(bot_name, user_id)
            #             if not missing_credential_name:
            #                 send_to_bot(bot_name, user_id, user_message, self.get_required_credentials(bot_name, user_id))
            #                 send_to_user(f"I think the {response} assistant should be able to assist with your request", user_id)
            #                 self.logger.info(f"Bot started {response}")
            #                 return False
            #             else:
            #             #otherwise we need to request the next missing cred
            #                 user_data.waiting_for_response_credential = missing_credential_name
            #                 user_data.waiting_for_response_credential_bot_id = bot_name
            #                 return f"Please provide {missing_credential_name} for the {bot_name} bot. {missing_credential_description}"
            #         else:
            #             #bot not enabled
            #             #Todo offer to enable
            #             publish_bot_rego_card(user_id, bot_name, f"I recommend using the {bot_name} bot for this task but it is not enabled. Would you like to enable it?")
            #             return False

            


            #invalid response or bot not registered.
            if 'default' in response.lower():
                response = self.default_response(user_message, api_key, user_data.teams_user_default_model)
                return response
            
            
        #no response
        self.logger.info(f"Model invalid response {response}")
        send_to_user("I could not find an available assistant to help with your request", user_id)
        return False

    

    def get_required_credentials(self, bot_id, user_id):
        "for the registered bots required credentials, create a prompt_package containing the name, value pairs"
        user_data = self.userManager.get_user(user_id)
        bot_data = self.botManager.get_bot(bot_id)

        credential_package = []
        for name, description in bot_data.required_credentials:
            if self.userManager.get_credential(user_id, name):
                #add the cred name and the value
                credential_package.append({name: self.userManager.get_credential(user_id, name)})
        return credential_package

    def get_missing_credential(self, bot_id, user_id):
        "for the registered bots required credentials, check that all cred names have value pairs"
        user_data = self.userManager.get_user(user_id)
        bot_data = self.botManager.get_bot(bot_id)

        for name, description in bot_data.required_credentials:
            if not self.userManager.get_credential(user_id, name):
                return name, description
        return None, None

    # The main dispatcher LLM response
    def model_response(self, user_message: str, api_key: str, openai_model: str) -> str:        
        try:
            os.environ["OPENAI_API_KEY"] = api_key
            llm = ChatOpenAI(temperature=0, model_name=openai_model, verbose=config.VERBOSE)
            tools = load_tools(["human"], llm=llm)

            # Add the users registered tools to the prompt
            available_bots = "default, "
            for bot in self.botManager.bots:
                available_bots = f"(Name: {bot.bot_id} - Description: {bot.bot_description}), {available_bots}" 

            prompt = f"""Given the following user request, identify which assistant should be able to assist. return only the assistant name
            
            request: {user_message}

            assistants: {available_bots}"""
            self.logger.info(prompt)

            # Send the prompt to OpenAI
            agent_executor = initialize_agent(tools, llm, agent=AgentType.OPENAI_FUNCTIONS, verbose=True, agent_kwargs = {
                    "input_variables": ["input", "agent_scratchpad"]
                })

            return agent_executor.run(input=prompt)
        
        except Exception as e:
            self.logger.error(f"{e} \n {traceback.format_exc()}")
    
    # If no tools where appropriate for the users request
    def default_response(self, user_message: str, api_key: str, openai_model: str) -> str:
        
        try:
            os.environ["OPENAI_API_KEY"] = api_key
            chat = ChatOpenAI()
            
            conversation = ConversationChain(llm=chat)  
            response = conversation.run(user_message)
            return response
        
        except Exception as e:
            self.logger.error(f"{e} \n {traceback.format_exc()}")     

    # Local Debug Commands
    def user_commands(self, user_message: str, user_id):
        
        if user_message:
            user_command = user_message.lower()
            #if user_id == config.OWNER:
            keyword = user_command.split()[0]
            
            if keyword == "botman":
                sub_command = user_command.split()[1]
                response = "unknown command"
                # ls
                if sub_command == 'ls':
                    response = ""
                    for bot in self.botManager.bots:
                        response = str(bot) + "\\" + response
                    
                    send_to_user(response, user_id)
                    return True

                if sub_command == 'report':
                    send_to_user(user_message, config.OWNER)
                    """log bug in ERP"""
                    return True
                

                if sub_command:
                    bot_command = user_command.split()[2]
                    
                    if bot_command == 'settings':
                        creds = self.get_required_credentials(sub_command, user_id)
                        summary = []
                        self.logger.info(creds)
                        summary = [(k, f'botman {sub_command} get setting {k}') for item in creds for k, v in item.items()]

                        # human_summary = [{'name': f'botman get setting {item["name"]}'} for item in creds]
                        # for cred in creds:
                        #     # title = creds.get('credential_name')
                        #     # setting = creds.get('credential_value')
                        #     setting = f"botman get setting {cred.name}"
                        #     human_summary.append((cred.name, setting))

                        publish_settings_list(sub_command, user_id, f'Settings for {sub_command}', summary)
                        return True

                    if bot_command == 'get':
                        bot_sub_command = user_command.split()[3]
                        if bot_sub_command == "setting":
                            setting_name = user_command.split()[4]
                            setting_desc = self.botManager.get_bot_credential_description(sub_command, setting_name)
                            setting_value = self.userManager.get_credential(user_id, setting_name)
                            publish_setting_card(sub_command, user_id, 'Change Setting', setting_name, setting_desc, setting_value)
                    
                        return True

                    if bot_command == 'register':
                        user_data = self.userManager.get_user(user_id)
                        self.userManager.register_bot(user_id, sub_command)
                        missing_credential_name, missing_credential_description = self.get_missing_credential(sub_command, user_id)
                        if missing_credential_name:
                            user_data.waiting_for_response_credential = missing_credential_name
                            user_data.waiting_for_response_credential_bot_id = sub_command
                            send_to_user(f"Please provide {missing_credential_name} for the {sub_command} bot. {missing_credential_description}")
                        else:
                            send_to_user(f'{sub_command} Enabled. Enjoy!', user_id)
                        return True

                    # forward to bot
                    creds = self.get_required_credentials(sub_command, user_id)
                    self.send_to_bot(sub_command, user_id, bot_command)
                    return 'wait'

                
            if keyword == "userman":
                sub_command = user_command.split()[1]
                response = "unknown command"
                #ls
                if sub_command == 'ls':
                    if user_id != config.OWNER: 
                        return
                    response = ""
                    for user in self.userManager.users:
                        response = str(user) + "\n" + response
                    
                    send_to_user(response, user_id)
                if sub_command == 'get':
                    get_object = user_command.split()[2]
                    if get_object == 'settings':

                        all_creds = self.userManager.get_all_credentials(user_id)
                        credentials = []
                        for cred in all_creds:
                            credentials.append(f"<li><b>{cred.get('credential_name')}:</b> {cred.get('credential_value')}</li>")

                        response = f"<h2>User Stored Settings</h2> <p>{''.join(credentials)}</p>"
                        send_to_user(response, user_id)
                        

                    if get_object == 'setting':
                        get_setting = user_command.split()[3]
                        response = f"<b>{get_setting}:</b> {self.userManager.get_credential(user_id, get_setting)}"
                        send_to_user(response, user_id)

                if sub_command == 'set':
                    set_object = user_command.split()[2]
                    if set_object == 'setting':
                        set_setting = user_command.split()[3]
                        set_value = user_command.split()[4].replace('"', '')
                        # delete not required
                        self.userManager.add_credential(user_id, set_setting, set_value)

                        self.send_to_all_bots('credential_update', user_id)
                        send_to_user(f"setting {set_setting} updated.", user_id)

                if sub_command == 'add':
                    set_object = user_command.split()[2]
                    if set_object == 'setting':
                        set_setting = user_command.split()[3]
                        set_value = user_command.split()[4].replace('"', '')
                        current_value = self.userManager.get_credential(user_id, set_setting)
                        new_value = current_value + ',' + set_value
                        self.userManager.add_credential(user_id, set_setting, new_value)

                        self.send_to_all_bots('credential_update', user_id)
                        send_to_user(f"setting {set_setting} updated.", user_id)
                return True

        return False

    # Nothing uses this right now
    def send_to_all_bots(self, command, user_id):
        all_creds = self.userManager.get_all_credentials(user_id)
        credentials = []
        for cred in all_creds:
            credentials.append({cred.get('credential_name'): cred.get('credential_value')})
        self.logger.info(credentials)
        for bot in self.botManager.bots:
            send_to_bot(bot.bot_id, user_id, command, credentials)


    # OpenAI API Key Verifier
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

    # Not Used
    def is_valid_model(self, model: str):
        if model == "gpt-3.5-turbo-16k":
            return True
        else:
            return False



