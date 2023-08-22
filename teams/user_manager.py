
import server_logging
import pickle
import json
import config
import traceback

class UserProfile:
    def __init__(self, name: str = None):
        self.name = name

class UserConfig:
    user_id: str = ""
    name: str = ""
    credentialManager: CredentialManager
    waiting_for_response: bool = False
    waiting_for_response_credential: str = ""
    active_bot: str = ""
        

    def __init__(self, user_id: str, user_name: str):
        self.name = user_name
        self.credentialManager = CredentialManager(config.DATA_DIR, user_id)
        self.credentialManager.load_credentials()
        self.waiting_for_response = False
        self.waiting_for_response_credential = ""
        self.active_bot = "dispatcher"

class UserManager:
    def __init__(self, data_dir):
        self.users = [UserConfig]
        self.data_dir = data_dir

        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def add_user(self, user_id: str, user_name: str) -> bool:
        for user in self.users:
            if user.user_id == user_id:

                return False
        self.users.append(UserConfig(user_id, user_name))
        return True

    def get_user(self, user_id) -> UserConfig:
        for user in self.users:
            if user.user_id == user_id:
                return user
        return None

    def delete_user(self, user_id: str) -> bool:
        for user in self.users:
            if user.user_id == user_id:
                self.user.remove(user)
                return True
        return False
            

    def save_users(self):
        file_path = f"{data_dir}/users.pkl"
        with open(file_path, 'wb') as f:
            pickle.dump(self.users, f)
            return True
        return False

    def load_users(self):
        file_path = f"{data_dir}/users.pkl"
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                self.users = pickle.load(f)
                return True
        return False
        #self.cleanup()
        

    def to_json(self, verbose=False):
        if not self.users:
            return "No users Loaded"
        else:
            if verbose:
                return json.dumps([users.to_dict_with_parameters() for user in self.users])
            else:
                return json.dumps([users.to_dict() for user in self.users])