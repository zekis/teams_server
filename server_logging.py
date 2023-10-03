# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
import traceback
import uuid
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime


# Get the current timestamp and format it
timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
current_path = os.getcwd() 
log_path = f"{current_path}/../logs/"
log_filename = f"{log_path}/server.log"


if not os.path.exists(log_path):
    os.mkdir(log_path)

# Rotate log after reaching 5 MB, with a maximum of 5 backup log files
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s(%(funcName)s) - %(message)s')
simple_formatter = logging.Formatter('%(levelname)s:%(name)s(%(funcName)s):%(message)s')

file_handler = RotatingFileHandler(log_filename, maxBytes=100*1024*1024, backupCount=5)
file_handler.doRollover()
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(simple_formatter)

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s(%(funcName)s):%(message)s')
pika_logger = logging.getLogger('pika').setLevel(logging.WARN)

# logger = logging.getLogger('TeamsBot')    
# logger.addHandler(file_handler)