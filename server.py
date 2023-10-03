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
import os

#from datetime import datetime
#from http import HTTPStatus
#https://github.com/microsoft/BotBuilder-Samples


from typing import Dict
from teams.teams_endpoint import messages, process_message


from aiohttp import web

from botbuilder.core.integration import aiohttp_error_middleware
# from aiohttp_admin2 import setup_admin
# from aiohttp_admin2.views import DashboardView
# from aiohttp_admin2.views import Admin
# from aiohttp_admin2.views.aiohttp.views.template_view import TemplateView

# import aiohttp_jinja2
# import jinja2
from pathlib import Path

# # path to the your template directory
# templates_directory = Path(__file__).parent / 'templates'

# class CustomDashboard(DashboardView):
#     template_name = 'my_custom_dashboard.html'
#     async def get_context(self, req):
#             return {
#                 **await super().get_context(req=req),
#                 "content": "My custom content"
#             }


# class CustomAdmin(Admin):
#     dashboard_class = CustomDashboard


# class FirstCustomView(TemplateView):
#     name = 'Template view'

async def message_queue():
    #logger.info("Start message processing")
    while True:
        await process_message()
        await asyncio.sleep(0.5)

async def run_api():

    asyncio.create_task(message_queue())

    APP = web.Application(middlewares=[aiohttp_error_middleware])
    # setup jinja2
    # aiohttp_jinja2.setup(
    #     app=APP,
    #     loader=jinja2.FileSystemLoader(str(templates_directory)),
    # )

    #setup_admin(APP, admin_class=CustomAdmin, middleware_list=[aiohttp_error_middleware], views=[FirstCustomView,])

    APP.router.add_post("/api/messages", messages)
    # for routes in APP.router.routes():
    #     print(routes)

    runner = web.AppRunner(APP)

    await runner.setup()
    await web.TCPSite(runner, host="localhost", port=config.PORT).start()

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(run_api())
