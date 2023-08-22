import traceback
import pika
import json
import time 
import server_logging

"This module handles sending and recieving between server and bots"

def encode_response(prompt: str) -> str:
    "encode a <prompt> into a dict and return a string to send via rabbitmq to a bot"
    
    response = {
        "prompt": prompt
    }
    server_logging.logger.debug(f"ENCODING: {response}")

    return json.dumps(response)


def decode_response(response: dict) -> str:
    "decode a dict <response> into a message and return the prompt as string"
    
    try:
        response = response.decode("utf-8")

        server_logging.logger.debug(f"DECODING: {response}")

        response_dict = json.loads(response)

        prompt = response_dict.get('prompt')
        
        return prompt
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
    server_logging.logger.debug(f"ENCODING: {message}")

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
        server_logging.logger.error(tb)
        
    

def send_to_user(message: str, user_id: str):
    "publish a server <message> to a specific teams user via the notify channel"

    server_logging.logger.info(f"send_to_user: {message}")

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    message = encode_message(user_id, 'prompt', message)

    notify_channel = connection.channel()

    notify_channel.basic_publish(exchange='',
                      routing_key='notify',
                      body=message)

    notify_channel.close()



def consume(channel_id: str) -> str:
    'consume and decode a message from <channel_id> directed as a specific user'

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    message_channel = connection.channel()
    
    message_channel.queue_declare(queue=channel_id)

    method, properties, body = message_channel.basic_get(queue=channel_id, auto_ack=True)

    message_channel.close()

    if body:
        response = decode_response(body)
        return response
    else:
        return None


def clear_queue(channel_id: str):
    "clear message queue (do this on start)"
    server_logging.logger.info("Clearing message queue")

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    message_channel = connection.channel()

    message_channel.queue_delete(channel_id)

    message_channel.queue_declare(channel_id)


def send_to_bot(channel_id: str, bot_id: str, message: str):
    "encode and send a message directly to a bot using <channel_id>"

    server_logging.logger.info(f"send_to_bot: {message}")

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    message_channel = connection.channel()

    message_channel.queue_declare(queue=channel_id)

    message = encode_response(message)

    message_channel.basic_publish(exchange='',routing_key=channel_id,body=message)


def receive_from_bots() -> str | str | str | str | str:
    "decode message from bots on the notify channel and return its components <bot_id>, <user_id>, <type>, <prompt> and <actions> as strings"
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

    notify_channel = connection.channel()

    method, properties, body = notify_channel.basic_get(queue="notify",auto_ack=True)

    if body:
        bot_id, user_id, type, body, data = decode_message(body)
        return bot_id, user_id, type, body, data
    else:
        return None, None, None, None, None



