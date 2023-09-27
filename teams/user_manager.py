
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


# class Credential:
#     def __init__(self, name, value):
#         self.name = name
#         self.value = value
 
#     def __str__(self):
#         return f"""- name: {self.name} = {self.value} <br>""" 

# class CredentialManager:
    
#     def __init__(self, frappe_base_url, api_key, api_secret):
#         self.logger = server_logging.logging.getLogger('CredentialManager') 
#         self.logger.addHandler(server_logging.file_handler)
#         self.frappe_base_url = frappe_base_url
#         self.headers = {
#             'Authorization': f'token {api_key}:{api_secret}',
#             'Content-Type': 'application/json'
#         }

#     def _send_request(self, method, endpoint, data=None):
#         url = f"{self.frappe_base_url}{endpoint}"
#         response = requests.request(method, url, headers=self.headers, json=data)
#         return response.json()

#     def add_credential(self, user_id, name, value):
#         # Assuming endpoint '/teams_user/<user_id>' fetches a teams_user
#         endpoint = f'/teams_user/{user_id}'
#         user = self._send_request('GET', endpoint).get('data')
        
#         if not user:
#             self.logger.error(f"User not found with ID {user_id}")
#             return False
        
#         # Check if the credential exists and delete
#         existing_credentials = user.get('credentials', [])
#         for cred in existing_credentials:
#             if cred['name'] == name:
#                 existing_credentials.remove(cred)
#                 break
        
#         # Add new credential
#         existing_credentials.append({'name': name, 'value': value})
#         user['credentials'] = existing_credentials
        
#         # Update user with new credentials
#         response = self._send_request('PUT', endpoint, user)
#         if response.get('message') == 'User updated':
#             self.logger.debug(f"Credential {name} added/updated for user {user_id}")
#             return True
        
#         return False

#     def get_credential(self, user_id, name):
#         endpoint = f'/teams_user/{user_id}'
#         user = self._send_request('GET', endpoint).get('data')
        
#         if not user:
#             self.logger.error(f"User not found with ID {user_id}")
#             return None

#         for cred in user.get('credentials', []):
#             if cred['name'] == name:
#                 return cred['value']

#         return None

#     def delete_credential(self, user_id, name):
#         endpoint = f'/teams_user/{user_id}'
#         user = self._send_request('GET', endpoint).get('data')
        
#         if not user:
#             self.logger.error(f"User not found with ID {user_id}")
#             return False
        
#         # Find and delete the credential
#         existing_credentials = user.get('credentials', [])
#         for cred in existing_credentials:
#             if cred['name'] == name:
#                 existing_credentials.remove(cred)
#                 user['credentials'] = existing_credentials
#                 response = self._send_request('PUT', endpoint, user)
#                 if response.get('message') == 'User updated':
#                     self.logger.debug(f"Credential {name} deleted for user {user_id}")
#                     return True

#         return False


class UserState:

    def __init__(self, user_id: str, user_name: str):
        self.teams_user_name = user_name
        self.teams_user_default_model = "gpt-3.5-turbo-16k"
        self.waiting_for_response = False
        self.waiting_for_response_credential = ""
        self.waiting_for_response_credential_bot_id = ""
        self.last_request = ""
        self.no_response = 0
        

#     # def __setstate__(self, state):
#     #     # Restore state from the older version
#     #     self.__dict__.update(state)

#     #     if 'default_param' not in state:
#     #         self.default_model = "gpt-3.5-turbo-16k"  # Set the default value here

#     #     if 'no_response' not in state:
#     #         self.no_response = "0"  # Set the default value here

#     def __str__(self):
#         return (f"**User Name:** {self.user_name} <br>"
#                 f"**Active Bot:** {self.active_bot} <br>"
#                 f"**Default Model:** {self.default_model} <br>"
#                 f"**Waiting for Response:** {self.waiting_for_response} <br>"
#                 f"**Waiting for Response Credential:** {self.waiting_for_response_credential} <br>"
#                 f"**No Response Count:** {self.no_response} <br>"
#                 f"**User ID:** {self.user_id} <br>")

class UserManager:
    
    def __init__(self, frappe_base_url, api_key, api_secret):
        self.logger = server_logging.logging.getLogger('UserManager') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init userManager")
        self.frappe_base_url = frappe_base_url
        self.headers = {
            'Authorization': f'token {api_key}:{api_secret}',
            'Content-Type': 'application/json'
        }
        self.users = {}

    def _send_request(self, method, endpoint, data=None):
        url = f"{self.frappe_base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, json=data)
        return response.json()

    
    def add_user(self, user_id: str, user_name: str) -> bool:
        self.logger.info(f"{user_id}")
        #always update local state first
        new_user = UserState(user_id, user_name)
        self.users[user_id] = new_user


        endpoint = '/resource/Teams%20User'
        data = {
            'teams_user_id': user_id,
            'teams_user_name': user_name
            
        }
        response = self._send_request('POST', endpoint, data)
        self.logger.info(str(response))
        if response.get('message') == 'User created':
            return True
        return True

    def get_user(self, user_id: str):
        self.logger.info(f"Fetching user with ID {user_id}")

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

    def get_user_api(self, user_id: str):
        # 2. Fetch user from the API
        endpoint = f'/resource/Teams%20User/{user_id}'
        response = self._send_request('GET', endpoint)
        self.logger.info(str(response))

        api_user_data = response.get('data', None) if response else None
        
        return response.get('data', None)

    
    def update_user(self, user_id: str, default_model: str) -> bool:
        self.logger.info(f"Updating user with ID {user_id}")
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
        self.logger.info(str(response))

        if response.get('message') == 'User updated':
            
            return True
        
        return False


    # def delete_user(self, user_id: str) -> bool:
    #     self.logger.info(f"{user_id}")
    #     # Assuming you have an endpoint '/user/<user_id>' to delete a user
    #     endpoint = f'/resource/Teams%20User/{user_id}'
    #     response = self._send_request('DELETE', endpoint)
    #     if response.get('message') == 'User deleted':
    #         return True
    #     return False
            
    def add_credential(self, user_id, name, value):
        self.logger.info(f"{user_id}, {name}")
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
    # def save_users(self):
    #     if self.users:
    #         file_path = f"{self.data_dir}/users.pkl"
    #         with open(file_path, 'wb') as f:
    #             pickle.dump(self.users, f)
    #             self.logger.info(f"Saving complete")
    #             return True
    #     self.logger.warn(f"No users to save")
    #     return False

    # def load_users(self):
    #     file_path = f"{self.data_dir}/users.pkl"
    #     if os.path.exists(file_path):
    #         with open(file_path, 'rb') as f:
    #             self.users = pickle.load(f)
    #             self.logger.info(f"{len(self.users)} users loaded")
    #             return True
    #     self.logger.warn(f"Could not find file {file_path}")
    #     return False