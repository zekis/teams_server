import traceback
import config
import server_logging
import json
import os
import re
import pickle
from typing import Optional


class Credential:
    def __init__(self, name, parameters):
        self.name = name
        self.parameters = parameters
        
    def to_dict_with_parameters(self):
        return {
            'name': self.name,
            'parameters': self.parameters
        }

    def to_dict(self):
        return {
            'name': self.name
        }

class CredentialManager:
    def __init__(self, data_dir, user_dir):
        self.credentials = []
        self.data_dir = data_dir
        self.user_dir = user_dir

        folder_path = f"{data_dir}/{user_dir}"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
    
    def add_credential(self, name, parameters):
        for credential in self.credentials:
            if credential.name == name:
                return f"A credential with the name '{name}' already exists."
        self.credentials.append(Credential(name, parameters))
        return f"Credential Added"

    def get_credential(self, name):
        for credential in self.credentials:
            if credential.name == name:
                return json.dumps(credential.to_dict_with_parameters())
        return False

    def delete_credential(self, name):
        for credential in self.credentials:
            if credential.name == name:
                self.credentials.remove(credential)
                return "Credential Deleted"
            

    def save_credentials(self):
        file_path = f"{self.data_dir}/{self.user_dir}/credential_registry.pkl"
        with open(file_path, 'wb') as f:
            pickle.dump(self.credentials, f)

    def load_credentials(self):
        file_path = f"{self.data_dir}/{self.user_dir}/credential_registry.pkl"
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                self.credentials = pickle.load(f)
        #self.cleanup()
        

    def to_json(self, verbose=False):
        if not self.credentials:
            return "No credentials Loaded, Use the ADD_CREDENTIAL tool to commission a new credential"
        else:
            if verbose:
                return json.dumps([credential.to_dict_with_parameters() for credential in self.credentials])
            else:
                return json.dumps([credential.to_dict() for credential in self.credentials])