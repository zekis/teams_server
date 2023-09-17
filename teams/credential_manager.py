import traceback
import config
import server_logging
import json
import os
import re
import pickle
from typing import Optional


class Credential:
    def __init__(self, name, value):
        self.name = name
        self.value = value
 
    def __str__(self):
        return f"""- name: {self.name} = {self.value} <br>""" 

class CredentialManager:

    logger = server_logging.logging.getLogger('CredentialManager') 
    logger.addHandler(server_logging.file_handler)
    
    def __init__(self):
        self.credentials = []
    
    def add_credential(self, name, value):
        self.logger.info(f"{name}")
        for credential in self.credentials:
            if credential.name == name:
                self.delete_credential(name)
                self.logger.debug(f"Credential {name} deleted")
        self.credentials.append(Credential(name, value))
        self.logger.debug(f"Credential {name} added")
        return True

    def get_credential(self, name):
        self.logger.debug(f"{name}")
        for credential in self.credentials:
            if credential.name == name:
                self.logger.debug(credential.value)
                return credential.value
        return False

    def delete_credential(self, name):
        self.logger.debug(f"{name}")
        for credential in self.credentials:
            if credential.name == name:
                self.credentials.remove(credential)
                self.logger.debug(f"{name} deleted")
                return True
            