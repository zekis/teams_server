from dotenv import find_dotenv, load_dotenv
import os
import sys
import traceback
import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Dict


from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    TurnContext,
    UserState,
    ShowTypingMiddleware,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes, ConversationReference

from teams.data_models import TaskModuleResponseFactory, ConversationData
from teams.user_manager import UserProfile
from teams.teams_conversation import TeamsConversationBot
import config

# See https://aka.ms/about-bot-adapter to learn more about how bots work.
SETTINGS = BotFrameworkAdapterSettings(config.APP_ID, config.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# join the conversation and send messages.
CONVERSATION_REFERENCES: Dict[str, ConversationReference] = dict()


# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )
    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)

    # Clear out state
    await CONVERSATION_STATE.delete(context)

ADAPTER.on_turn_error = on_error
ADAPTER.use(ShowTypingMiddleware(delay=0.01, period=30.0))

APP_ID = SETTINGS.app_id

# Create MemoryStorage and state
MEMORY = MemoryStorage()
USER_STATE = UserState(MEMORY)
CONVERSATION_STATE = ConversationState(MEMORY)
CONVERSATION_REFERENCES: Dict[str, ConversationReference] = dict()
# Create the Bot
BOT = TeamsConversationBot(config.APP_ID, config.APP_PASSWORD, CONVERSATION_STATE, USER_STATE, CONVERSATION_REFERENCES)


# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=HTTPStatus.OK)


async def process_message():
    await BOT.process_message(ADAPTER)


