
import server_logging
import pickle
import json
import config
import traceback
import os
import datetime

#from teams.credential_manager import CredentialManager

class BotConfig:

    def __init__(self, bot_id: str, bot_description: str):
        self.bot_id = bot_id
        self.bot_description = bot_description
        self.bot_register_datetime = datetime.datetime.now()
        self.required_credentials = []
        
    def __str__(self):
        credentials = ""
        for cred in self.required_credentials:
            credentials = str(cred) + ", " + credentials
        return f"""**Bot ID:** {self.bot_id} <br>
        **Description:** {self.bot_description} <br>
        **Registration Date:** {self.bot_register_datetime} <br>
        **Required Credentials:** {credentials}"""

class BotManager:
    
    def __init__(self):
        self.logger = server_logging.logging.getLogger('BotManager') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init BotManager")

        self.bots = []        
        
    def add_bot(self, bot_id: str, bot_description: str, credentials: list) -> bool:
        for bot in self.bots:
            if bot.bot_id == bot_id:
                
                bot.bot_description = bot_description
                bot.required_credentials = []
                #add empty credentials. The manager will populate them as they become available
                for cred in credentials:
                    bot.required_credentials.append(cred)

                self.update_bot_registration_time(bot_id)
                return True
        
        #add empty credentials. The manager will populate them as they become available
        new_bot = BotConfig(bot_id, bot_description)
        for cred in credentials:
            new_bot.required_credentials.append(cred)
        self.bots.append(new_bot)

        self.logger.info(f"{bot_id}")
        return True

    # def is_ready(self, bot_id: str) -> bool:
    #     bot = self.get_bot(bot_id)
    #     for cred in bot.required_credentials:
    #         if cred.value == "":
    #             return False
    #     return True

    # def get_missing_credential(self, bot_id: str) -> str:
    #     bot = self.get_bot(bot_id)
    #     for cred in bot.required_credentials:
    #         if cred.value == "":
    #             return cred.name
    #     return None

    def get_bot(self, bot_id: str) -> BotConfig:
        self.logger.debug(f"{bot_id}")
        for bot in self.bots:
            if bot.bot_id == bot_id:
                self.logger.debug(f"found {bot.bot_id}")
                return bot
        self.logger.warn(f"Bot not found. bot_id {bot_id}")
        return None

    def get_bot_credential_description(self, bot_id: str, credential_name: str):
        self.logger.debug(f"{bot_id}")
        for bot in self.bots:
            if bot.bot_id == bot_id:
                self.logger.debug(f"found {bot.bot_id}")
                for name, desc in bot.required_credentials:
                    if name == credential_name:
                        return desc
                    
        self.logger.warn(f"Bot not found. bot_id {bot_id}")
        return None


    def delete_bot(self, bot_id: str) -> bool:
        for bot in self.bots:
            if bot.bot_id == bot_id:
                self.bots.remove(bot)
                self.logger.info(f"{bot_id}")
                return True
        return False
    """"""
    def update_bot_registration_time(self, bot_id: str) -> bool:
        for bot in self.bots:
            if bot.bot_id == bot_id:
                bot.bot_register_datetime = datetime.datetime.now()
                self.logger.debug(f"{str(bot.bot_register_datetime)} for bot with id {bot_id}")
                return True
        self.logger.warn(f"Bot not found. bot_id {bot_id}")
        return False


    def remove_old_bots(self):
        current_time = datetime.datetime.now()
        bots_to_remove = []

        for bot in self.bots:
            time_diff = current_time - bot.bot_register_datetime
            if time_diff.total_seconds() > 60:  # 300 seconds is 5 minutes
                bots_to_remove.append(bot.bot_id)

        for bot_id in bots_to_remove:
            self.delete_bot(bot_id)
            self.logger.info(f"Removed bot with id {bot_id} due to age.")

    def get_bot_config_str(self, bot_id: str) -> str:
        bot = self.get_bot(bot_id)
        if bot:
            return str(bot)
        else:
            return "Bot not found."
