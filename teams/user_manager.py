
import server_logging
import pickle
import json
import config
import traceback
import os
import requests




class UserProfile:
    def __init__(self, name: str = None):
        self.name = name




class UserState:

    def __init__(self, user_id: str, user_name: str):
        self.teams_user_name = user_name
        self.teams_user_default_model = "gpt-3.5-turbo-16k"
        self.waiting_for_response = False
        self.waiting_for_response_credential = ""
        self.waiting_for_response_credential_bot_id = ""
        self.previous_response = ""
        self.previous_request = ""
        self.previous_forward_bot = ""
        self.previous_assistant = ""
        self.last_request = ""
        self.no_response = 0

class Bot:

    def __init__(self, bot_id: str, bot_description: str):
        self.bot_id = bot_id
        self.bot_description = bot_description
        self.bot_register_datetime = datetime.datetime.now()
        self.required_credentials = []

class UserManager:
    
    def __init__(self, frappe_base_url, api_key, api_secret):
        self.logger = server_logging.logging.getLogger('SERVER-USER-MANAGER') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init userManager")
        self.frappe_base_url = frappe_base_url
        self.headers = {
            'Authorization': f'token {api_key}:{api_secret}',
            'Content-Type': 'application/json'
        }
        self.users = {}
        self.load_users()

    def _send_request(self, method, endpoint, data=None):
        url = f"{self.frappe_base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, json=data)
        return response.json()

    
    def add_user(self, user_id: str, user_name: str) -> bool:
        self.logger.debug(f"{user_id}")
        #always update local state first
        new_user = UserState(user_id, user_name)
        self.users[user_id] = new_user


        endpoint = '/resource/Teams%20User'
        data = {
            'teams_user_id': user_id,
            'teams_user_name': user_name
            
        }
        response = self._send_request('POST', endpoint, data)
        self.logger.debug(str(response))
        if response.get('message') == 'User created':
            return True
        return True

    def load_users(self):
        self.logger.debug(f"Fetching users")

        api_data = self.get_users_api()
        
        # Clear the local state
        self.users = {}
        # local_user = self.users.get(user_id)
        for user in api_data:
            user_name = user.get('name')
            self.get_user(user_name)

    def get_user(self, user_id: str):
        self.logger.debug(f"Fetching user with ID {user_id}")

        api_data = self.get_user_api(user_id)
        # 1. Get user from the local state
        local_user = self.users.get(user_id)
        
        if local_user:
            #update the local user with the API data
            if api_data:
                local_user.teams_user_default_model = api_data.get('teams_user_default_model')
            return local_user
        else:
            #user is in the DB but not in memory, lets create a new state
            if api_data:
                new_user = UserState(user_id, api_data.get('teams_user_name'))
                self.users[user_id] = new_user
                new_user.teams_user_default_model = api_data.get('teams_user_default_model')
                return new_user
            
            self.logger.warning(f"User not found in local state with ID {user_id}")
            return None

    def get_users_api(self):
        # 2. Fetch user from the API
        endpoint = f'/resource/Teams%20User'
        response = self._send_request('GET', endpoint)
        self.logger.debug(str(response))

        api_user_data = response.get('data', None) if response else None
        
        return response.get('data', None)

    def get_user_api(self, user_id: str):
        # 2. Fetch user from the API
        endpoint = f'/resource/Teams%20User/{user_id}'
        response = self._send_request('GET', endpoint)
        self.logger.debug(str(response))

        api_user_data = response.get('data', None) if response else None
        
        return response.get('data', None)

    
    def update_user(self, user_id: str, default_model: str) -> bool:
        self.logger.debug(f"Updating user with ID {user_id}")
        #update local state first
        self.users[user_id].teams_user_default_model = default_model

        # First, check if the user exists
        existing_user = self.get_user(user_id)
        if not existing_user:
            self.logger.error(f"User not found with ID {user_id}")
            return False

        endpoint = f'/resource/Teams%20User/{user_id}'
        
        # Update only the name (or any other attributes you want to update)
        data = {
            'teams_user_default_model': default_model
        }

        response = self._send_request('PUT', endpoint, data)
        self.logger.debug(str(response))

        if response.get('message') == 'User updated':
            
            return True
        
        return False


    # def delete_user(self, user_id: str) -> bool:
    #     self.logger.debug(f"{user_id}")
    #     # Assuming you have an endpoint '/user/<user_id>' to delete a user
    #     endpoint = f'/resource/Teams%20User/{user_id}'
    #     response = self._send_request('DELETE', endpoint)
    #     if response.get('message') == 'User deleted':
    #         return True
    #     return False
            
    def add_credential(self, user_id, name, value):
        self.logger.debug(f"{user_id}, {name}")
        # Assuming endpoint '/teams_user/<user_id>' fetches a teams_user
        endpoint = f'/resource/Teams%20User/{user_id}'
        user = self._send_request('GET', endpoint).get('data')
        
        if not user:
            self.logger.error(f"User not found with ID {user_id}")
            return False
        
        # Check if the credential exists and delete
        existing_credentials = user.get('teams_user_credentials', [])
        for cred in existing_credentials:
            if cred['credential_name'] == name:
                existing_credentials.remove(cred)
                break
        
        # Add new credential
        existing_credentials.append({'credential_name': name, 'credential_value': value})
        user['teams_user_credentials'] = existing_credentials
        
        # Update user with new credentials
        response = self._send_request('PUT', endpoint, user)
        if response.get('message') == 'User updated':
            self.logger.debug(f"Credential {name} added/updated for user {user_id}")
            return True
        
        return False

    def get_credential(self, user_id, name):
        endpoint = f'/resource/Teams%20User/{user_id}'
        user = self._send_request('GET', endpoint).get('data')
        
        if not user:
            self.logger.error(f"User not found with ID {user_id}")
            return None

        for cred in user.get('teams_user_credentials', []):
            if cred['credential_name'] == name:
                return cred['credential_value']

        return None
    

    def get_all_credentials(self, user_id):
        endpoint = f'/resource/Teams%20User/{user_id}'
        user = self._send_request('GET', endpoint).get('data')
        
        if not user:
            self.logger.error(f"User not found with ID {user_id}")
            return None

        #credentials = []
        return user.get('teams_user_credentials', [])
        # for cred in user.get('teams_user_credentials', []):
        #     credentials.append(f"<li><b>{cred['credential_name']}:</b> {cred['credential_value']}</li>")

        # return ''.join(credentials)

    def delete_credential(self, user_id, name):
        endpoint = f'/resource/Teams%20User/{user_id}'
        user = self._send_request('GET', endpoint).get('data')
        
        if not user:
            self.logger.error(f"User not found with ID {user_id}")
            return False
        
        # Find and delete the credential
        existing_credentials = user.get('teams_user_credentials', [])
        for cred in existing_credentials:
            if cred['credential_name'] == name:
                existing_credentials.remove(cred)
                user['teams_user_credentials'] = existing_credentials
                response = self._send_request('PUT', endpoint, user)
                if response.get('message') == 'User updated':
                    self.logger.debug(f"Credential {name} deleted for user {user_id}")
                    return True

        return False

    def get_registered_bots(self, user_id):
        endpoint = f'/resource/Teams%20User/{user_id}'
        user = self._send_request('GET', endpoint).get('data')
        
        if not user:
            self.logger.error(f"User not found with ID {user_id}")
            return None
            
        #credentials = []
        self.logger.debug(user.get('teams_user_bots'))
        return user.get('teams_user_bots', [])

    def get_available_bots(self):
        # 2. Fetch user from the API
        endpoint = f'/resource/Teams%20Bot?fields=["name", "description"]'
        response = self._send_request('GET', endpoint)
        # self.logger.debug(str(response))

        api_bots_data = response.get('data', None) if response else None
        
        return response.get('data', None)


    def get_user_bots_with_descriptions(self, user_id):
        # Get the list of bots registered to the user
        user_bots = self.get_registered_bots(user_id)
        if user_bots is None:
            self.logger.error("Could not retrieve user's bots.")
            return None
        
        # Get the list of all available bots
        available_bots = self.get_available_bots()
        if available_bots is None:
            self.logger.error("Could not retrieve available bots.")
            return None
        
        # Create a dictionary for quicker lookup of available bots by bot_id
        print(user_bots)
        print(available_bots)

        # available_bots_dict = {'bot_id': bot['name'], 'description': bot['description'] for bot in available_bots}
        # print(available_bots_dict)

        # # Match user bots against available bots and get descriptions
        merged_bots = []
        # Create a mapping from name to bot description for quick lookup.
        bot_description_map = {bot['name']: bot['description'] for bot in available_bots}

        # Go through each user bot and merge with available bot description.
        for user_bot in user_bots:
            bot_name = user_bot['bot_id']
            if bot_name in bot_description_map:
                # Create a new merged dictionary.
                merged_bot = {**user_bot, 'description': bot_description_map[bot_name]}
                merged_bots.append(merged_bot)
            else:
                # If no matching bot is found, still add the user bot.
                merged_bots.append(user_bot)

        return merged_bots
    


    def register_bot(self, user_id, bot_id):
        self.logger.debug(f"{user_id}, {bot_id}")
        # Assuming endpoint '/teams_user/<user_id>' fetches a teams_user
        endpoint = f'/resource/Teams%20User/{user_id}'
        user = self._send_request('GET', endpoint).get('data')
        
        if not user:
            self.logger.error(f"User not found with ID {user_id}")
            return False
        
        # Check if the bot exists and delete
        existing_bots = user.get('teams_user_bots', [])
        for bot in existing_bots:
            if bot['bot_id'] == bot_id:
                existing_bots.remove(bot)
                break
        
        # Add new credential
        existing_bots.append({'bot_id': bot_id, 'bot_enabled': '1'})
        user['teams_user_bots'] = existing_bots
        
        # Update user with new bot
        response = self._send_request('PUT', endpoint, user)
        if response.get('message') == 'User updated':
            self.logger.debug(f"Bot {bot_id} added/updated for user {user_id}")
            return True
        
        return False
    # def save_users(self):
    #     if self.users:
    #         file_path = f"{self.data_dir}/users.pkl"
    #         with open(file_path, 'wb') as f:
    #             pickle.dump(self.users, f)
    #             self.logger.debug(f"Saving complete")
    #             return True
    #     self.logger.warn(f"No users to save")
    #     return False

    # def load_users(self):
    #     file_path = f"{self.data_dir}/users.pkl"
    #     if os.path.exists(file_path):
    #         with open(file_path, 'rb') as f:
    #             self.users = pickle.load(f)
    #             self.logger.debug(f"{len(self.users)} users loaded")
    #             return True
    #     self.logger.warn(f"Could not find file {file_path}")
    #     return False