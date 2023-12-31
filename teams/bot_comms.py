import traceback
import pika
import json
import time 
import server_logging
from teams.bot_cards import create_settings_card, create_setting_card, create_enable_card

comms_logger = server_logging.logging.getLogger('BOT-COMMS')
comms_logger.addHandler(server_logging.file_handler)
"This module handles sending and recieving between server and bots"
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
notify_channel = connection.channel()
message_channel = connection.channel()

def encode_response(user_id, prompt: str, credentials: list) -> str:
    "encode a <prompt> into a dict and return a string to send via rabbitmq to a bot"
    
    response = {
        "user_id": user_id,
        "prompt": prompt,
        "credentials": credentials
    }
    comms_logger.debug(f"ENCODING: {response}")

    return json.dumps(response)

def encode_response_with_actions(bot_id, user_id, prompt: str, type=None, actions=None) -> str:
    "encode a <prompt> into a dict and return a string to send via rabbitmq to a bot"
    
    response = {
        "bot_id": bot_id,
        "user_id": user_id,
        "type": type,
        "prompt": prompt,
        "actions": actions
    }
    comms_logger.debug(f"ENCODING: {response}")

    return json.dumps(response)

def encode_command(bot_id, command: str, data: str) -> str:
    "encode a <prompt> into a dict and return a string to send via rabbitmq to a bot"
    
    response = {
        "bot_id": bot_id,
        "command": command,
        "data": data
    }
    comms_logger.debug(f"ENCODING: {response}")

    return json.dumps(response)

def decode_response(response: dict) -> str:
    "decode a dict <response> into a message and return the prompt as string"
    
    try:
        response = response.decode("utf-8")

        comms_logger.debug(f"DECODING: {response}")

        response_dict = json.loads(response)

        #prompt = response_dict.get('prompt')
        
        return response_dict
    except Exception as e:
        traceback.print_exc()
        return "prompt", f"error: {e}", None


def encode_message(user_id: str, type: str, prompt: str, actions=None) -> str:
    "encode a message <user_id>, <type>, <prompt> and <actions> and return a dict as string"
    
    message = {
        "user_id": user_id,
        "type": type,
        "prompt": prompt,
        "actions": actions
    }
    comms_logger.debug(f"ENCODING: {message}")

    return json.dumps(message)


def decode_message(message: str) -> str | str | str | str | str:
    "decode a string dict and return its components <user_id>, <type>, <prompt> and <actions> as strings"
    try:
        message = message.decode("utf-8")
        
        message_dict = json.loads(message)
        bot_id = message_dict.get('bot_id')
        user_id = message_dict.get('user_id')
        type = message_dict.get('type')
        prompt = message_dict.get('prompt')
        actions = message_dict.get('actions')
        
        return bot_id, user_id, type, prompt, actions
        
    except Exception as e:
        tb = traceback.format_exc()
        comms_logger.error(tb)
        
    

def send_to_user(message: str, user_id: str):
    "publish a server <message> to a specific teams user via the notify channel"

    comms_logger.debug(f"{message}")

    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    message = encode_message(user_id, 'prompt', message)

    # notify_channel = connection.channel()

    notify_channel.basic_publish(exchange='',
                      routing_key='notify',
                      body=message)

    # notify_channel.close()

def bot_to_user(message: str, user_id: str):
    "publish a server <message> to a specific teams user via the notify channel"

    comms_logger.debug(f"{message}")

    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    message = json.dumps(message)

    # notify_channel = connection.channel()

    notify_channel.basic_publish(exchange='',
                      routing_key='notify',
                      body=message)

    # notify_channel.close()



def from_bot_to_dispatcher(channel_id: str) -> str:
    'consume and decode a message from <channel_id> directed as a specific user'

    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    # message_channel = connection.channel()
    
    message_channel.queue_declare(queue=channel_id)

    method, properties, body = message_channel.basic_get(queue=channel_id, auto_ack=True)

    # message_channel.close()

    if body:
        response = decode_response(body)
        return response
    else:
        return None


def clear_queue(channel_id: str):
    "clear message queue (do this on start)"
    comms_logger.debug("Clearing message queue")

    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    # message_channel = connection.channel()

    message_channel.queue_purge(channel_id)

    message_channel.queue_declare(channel_id)

    

def from_dispatcher_to_bot_manager(bot_id: str, command: str, data: str):
    "encode and send a message to a bot manager using <channel_id>"

    comms_logger.debug(f"CHANNEL: {bot_id} - {command}")

    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    # message_channel = connection.channel()

    message_channel.queue_declare(queue=bot_id)

    message = encode_command(bot_id, command, data)

    message_channel.basic_publish(exchange='',routing_key=bot_id,body=message)




def send_to_bot(bot_id: str, user_id: str, message: str, credentials: list = None):
    "encode and send a message directly to a bot using <bot_id>"

    comms_logger.debug(f"CHANNEL: {bot_id} - {message}")

    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    # message_channel = connection.channel()

    message_channel.queue_declare(queue=bot_id)
    #message_and_history = f"*** {message}  *** Previous Request: {previous_request}, *** Previous Response: {previous_response}"

    message = encode_response(user_id, message, credentials)

    message_channel.basic_publish(exchange='',routing_key=bot_id,body=message)

def send_command_to_bot(bot_id: str, user_id: str, message: str, credentials: list = None):
    "encode and send a message directly to a bot using <bot_id>"

    comms_logger.debug(f"CHANNEL: {bot_id} - {message}")

    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    # message_channel = connection.channel()

    message_channel.queue_declare(queue=bot_id)

    message = encode_response(user_id, message, credentials)

    message_channel.basic_publish(exchange='',routing_key=bot_id,body=message)


def from_manager_to_user() -> str | str | str | str | str:
    "decode message from bots on the notify channel and return its components <bot_id>, <user_id>, <type>, <prompt> and <actions> as strings"
    # connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    # notify_channel = connection.channel()

    notify_channel.queue_declare(queue="notify")

    method, properties, body = notify_channel.basic_get(queue="notify",auto_ack=True)

    if body:
        bot_id, user_id, type, body, data = decode_message(body)
        return bot_id, user_id, type, body, data
    else:
        return None, None, None, None, None

def publish_settings_list(bot_id, user_id, message, strings_values, button_label="Change"):
    notify_channel.queue_declare(queue="notify")

    try:
        cards = create_settings_card(message, strings_values,button_label)
    except Exception as e:
        traceback.print_exc()
        cards = None
    
    message = encode_response_with_actions(bot_id, user_id, message, "cards", cards)
    notify_channel.basic_publish(exchange='', routing_key="notify", body=message)

def publish_setting_card(bot_id, user_id, message, setting_name, setting_desc, current_value):

    notify_channel.queue_declare(queue="notify")

    # convert string to dict (hopefully our AI has formatted it correctly)
    try:
        cards = create_setting_card(message, setting_name, setting_desc, current_value)
        # cards = create_list_card("Choose an option:", [("Option 1", "1"), ("Option 2", "2"), ("Option 3", "3")])
    except Exception as e:
        traceback.print_exc()
        cards = None
    
    message = encode_response_with_actions(bot_id, user_id, message, "cards", cards)

    notify_channel.basic_publish(exchange='', routing_key="notify", body=message)


def publish_bot_rego_card(user_id, bot_id, message):

    notify_channel.queue_declare(queue="notify")

    # convert string to dict (hopefully our AI has formatted it correctly)
    try:
        cards = create_enable_card(message, bot_id)
        # cards = create_list_card("Choose an option:", [("Option 1", "1"), ("Option 2", "2"), ("Option 3", "3")])
    except Exception as e:
        traceback.print_exc()
        cards = None
    
    message = encode_response_with_actions(bot_id, user_id, message, "cards", cards)

    notify_channel.basic_publish(exchange='', routing_key="notify", body=message)