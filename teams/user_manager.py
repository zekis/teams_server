
import server_logging
import pickle
import json
import config
import traceback
import os

from teams.credential_manager import CredentialManager

class UserProfile:
    def __init__(self, name: str = None):
        self.name = name

class UserConfig:

    def __init__(self, data_dir:str , user_id: str, user_name: str):
        self.user_id = user_id
        self.user_name = user_name

        self.credentialManager = CredentialManager()
        self.waiting_for_response = False
        self.waiting_for_response_credential = ""
        self.active_bot = "dispatcher"
        self.default_model = "gpt-3.5-turbo-16k"
        self.no_response = 0
        

    def __setstate__(self, state):
        # Restore state from the older version
        self.__dict__.update(state)

        if 'default_param' not in state:
            self.default_model = "gpt-3.5-turbo-16k"  # Set the default value here

        if 'no_response' not in state:
            self.no_response = "0"  # Set the default value here

class UserManager:
    
    def __init__(self, data_dir):
        self.logger = server_logging.logging.getLogger('UserManager') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init userManager")

        self.users = []
        self.data_dir = data_dir
        
        if not os.path.exists(data_dir):
            self.logger.debug(f"creating folder")
            os.makedirs(data_dir)

        self.load_users()
                
        
    def add_user(self, user_id: str, user_name: str) -> bool:
        self.logger.info(f"{user_id}")
        for user in self.users:
            if user.user_id == user_id:
                return True
        self.users.append(UserConfig(self.data_dir, user_id, user_name))
        self.save_users()
        return True

    def get_user(self, user_id: str) -> UserConfig:
        self.logger.debug(f"{user_id}")
        
        for user in self.users:
            if user.user_id == user_id:
                self.logger.debug(f"found {user.user_name}")
                return user
        self.logger.warn(f"User not found. user_id {user_id}")
        return None

    def delete_user(self, user_id: str) -> bool:
        self.logger.info(f"{user_id}")
        for user in self.users:
            if user.user_id == user_id:
                self.user.remove(user)
                self.save_users()
                return True
        return False
            

    def save_users(self):
        if self.users:
            file_path = f"{self.data_dir}/users.pkl"
            with open(file_path, 'wb') as f:
                pickle.dump(self.users, f)
                self.logger.info(f"Saving complete")
                return True
        self.logger.warn(f"No users to save")
        return False

    def load_users(self):
        file_path = f"{self.data_dir}/users.pkl"
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                self.users = pickle.load(f)
                self.logger.info(f"{len(self.users)} users loaded")
                return True
        self.logger.warn(f"Could not find file {file_path}")
        return False