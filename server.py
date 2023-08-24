# Copyright (c) Tierney Morris
# Handle conversations between teams clients and the ai bots
# The bots monitor the bot channels for requests to start/stop
# This allows for one user to have multiple bots

import config
import sys
import traceback
import uuid
import server_logging


from datetime import datetime
from http import HTTPStatus
#https://github.com/microsoft/BotBuilder-Samples


from typing import Dict
from teams.teams_endpoint import messages, process_message

import asyncio
import threading
from aiohttp import web
from botbuilder.core.integration import aiohttp_error_middleware

async def message_queue():
    #logger.info("Start message processing")
    while True:
        await process_message()
        await asyncio.sleep(0.5)

async def run_server():
    APP = web.Application(middlewares=[aiohttp_error_middleware])
    APP.router.add_post("/api/messages", messages)
    
    
    runner = web.AppRunner(APP)
    #logger.info("Webserver Initiated")
    await runner.setup()
    await web.TCPSite(runner, host="localhost", port=config.PORT).start()
    await asyncio.Event().wait()

async def main():
    
    logger = server_logging.logging.getLogger('Server') 
    logger.addHandler(server_logging.file_handler)
    logger.info(f"Init Server")

    tasks = []
    tasks.append(asyncio.create_task(run_server()))
    tasks.append(asyncio.create_task(message_queue()))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

