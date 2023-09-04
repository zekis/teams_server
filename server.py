# Copyright (c) Tierney Morris
# Handle conversations between teams clients and the ai bots
# The bots monitor the bot channels for requests to start/stop
# This allows for one user to have multiple bots
import asyncio
import threading
import config
import sys
import traceback
import uuid
import server_logging


#from datetime import datetime
#from http import HTTPStatus
#https://github.com/microsoft/BotBuilder-Samples


from typing import Dict
from teams.teams_endpoint import messages, process_message


from aiohttp import web

from botbuilder.core.integration import aiohttp_error_middleware
from aiohttp_admin2 import setup_admin
import aiohttp_jinja2
import jinja2
from pathlib import Path


template_directory = Path(__file__).parent / 'templates'

async def message_queue():
    #logger.info("Start message processing")
    while True:
        await process_message()
        await asyncio.sleep(0.5)

async def run_api():

    asyncio.create_task(message_queue())



    APP = web.Application()
    
    # aiohttp_jinja2.setup(
    #     app=APP,
    #     loader=jinja2.FileSystemLoader(str(template_directory)),
    # )
    
    setup_admin(APP,middleware_list=[aiohttp_error_middleware])

    APP.router.add_post("/api/messages", messages)
    for routes in APP.router.routes():
        print(routes)

    #web.run_app(APP, port=config.PORT)
    #web.run_app(APP)
    runner = web.AppRunner(APP)
    #logger.info("Webserver Initiated")
    await runner.setup()
    await web.TCPSite(runner, host="localhost", port=config.PORT).start()
    #await site.start()

    #await process_message()

    await asyncio.Event().wait()

# async def main():
    
#     logger = server_logging.logging.getLogger('Server') 
#     logger.addHandler(server_logging.file_handler)
#     logger.info(f"Init Server")

    

#     tasks = []
#     tasks.append(asyncio.create_task(run_api()))
#     tasks.append(asyncio.create_task(message_queue()))
#     await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(run_api())
    #main()

