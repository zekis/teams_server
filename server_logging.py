# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import config
import sys
import traceback
import uuid
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Get the current timestamp and format it
timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
log_filename = f"./logs/log_{timestamp}.log"

# Rotate log after reaching 5 MB, with a maximum of 5 backup log files
handler = RotatingFileHandler(log_filename, maxBytes=100*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO)
pika_logger = logging.getLogger('pika').setLevel(logging.WARN)

logger = logging.getLogger('TeamsBot')    
logger.addHandler(handler)