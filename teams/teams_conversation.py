
import traceback
from datetime import datetime
import os
from pathlib import Path
import json
import random
import requests
import subprocess
import config
import pickle
import server_logging
#from teams.elevenlabs import speech
#from common.card_factories import create_media_card
from typing import List

from teams.bot_dispatcher import BotDispatcher
from teams.bot_comms import from_manager_to_user, send_to_bot, send_to_user

from botbuilder.core import ActivityHandler, CardFactory, TurnContext, MessageFactory, ShowTypingMiddleware, ConversationState, UserState
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import Mention, ConversationParameters, Activity, ActivityTypes
from botbuilder.schema.teams import TeamInfo, TeamsChannelAccount
#from botbuilder.schema._connector_client_enums import ActionTypes
#from bots.model_openai import model_response
from botbuilder.core import BotFrameworkAdapter
import pika
#from bots.utils import encode_message, decode_message, encode_response, decode_response
#from common.rabbit_comms import publish, publish_action, consume, send_to_bot, receive_from_bot

from typing import Dict

from botbuilder.schema import ChannelAccount, ConversationReference, CardAction, ActionTypes, SuggestedActions
from botbuilder.schema import (
    ActionTypes,
    Attachment,
    HeroCard,
    CardImage,
    CardAction,
    AdaptiveCardInvokeResponse,
    AdaptiveCardInvokeValue,
    InvokeResponse
)

from teams.data_models import TaskModuleResponseFactory, ConversationData
from teams.user_manager import UserProfile

from botbuilder.schema.teams import (
    TaskModuleContinueResponse,
    TaskModuleRequest,
    TaskModuleMessageResponse,
    TaskModuleResponse,
    TaskModuleTaskInfo,
    MessagingExtensionResult
)

thinking_messages = [
    "Just a moment...",
    "Let me check on that...",
    "Hang on a sec...",
    "Give me a second...",
    "Thinking...",
    "One moment, please...",
    "Hold on...",
    "Let me see...",
    "Processing your request...",
    "Let me think for a bit...",
    "Let me get that for you...",
    "Bear with me...",
    "Almost there...",
    "Wait a moment...",
    "Checking...",
    "Calculating...",
    "Give me a moment to think...",
    "I'm on it...",
    "Searching for the answer...",
    "I need a second...",
]

class TeamsConversationBot(TeamsActivityHandler):
    "microsoft teams conversation library"
    

    def __init__(self, app_id: str, app_password: str, conversation_state: ConversationState, user_state: UserState, conversation_references: Dict[str, ConversationReference]):
        'start by initiating reference storage'
        self.logger = server_logging.logging.getLogger('TeamsConversationBot') 
        self.logger.addHandler(server_logging.file_handler)
        self.logger.info(f"Init TeamsConversationBot")


        self.conversation_references = conversation_references
        # Load conversation references if file exists
        self.filename = "conversation_references.pkl"
        if os.path.exists(self.filename):
            with open(self.filename, "rb") as file:
                self.conversation_references = pickle.load(file)

        self._app_id = app_id
        self._app_password = app_password
        #self.ADAPTER = ADAPTER
        self.__base_url = config.BASE_URL
        self.bot_dispatcher = BotDispatcher()

        if conversation_state is None:
            raise TypeError(
                "[StateManagementBot]: Missing parameter. conversation_state is required but None was given"
            )
        if user_state is None:
            raise TypeError(
                "[StateManagementBot]: Missing parameter. user_state is required but None was given"
            )

        self.conversation_state = conversation_state
        self.user_state = user_state

        self.conversation_data_accessor = self.conversation_state.create_property("ConversationData")
        self.user_profile_accessor = self.user_state.create_property("UserProfile")


   
    async def on_turn(self, turn_context: TurnContext):
        'message or command received from user as <turn_contect>'
        await super().on_turn(turn_context)

        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    async def on_members_added_activity(
        self, members_added: [ChannelAccount], turn_context: TurnContext
    ):
        #When a member sends activity, if they are not recipient, send welcome
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Welcome. Type anything to get started."
                )
    
    async def get_member(
        self, turn_context: TurnContext
    ):
        # TeamsInfo.get_member: Gets the member of a team scoped conversation.
        member = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        return member

        
    async def on_message_activity(self, turn_context: TurnContext):
        'All teams messages come through here as a <turn_context>'

        user_profile = await self.user_profile_accessor.get(turn_context, UserProfile)
        conversation_data = await self.conversation_data_accessor.get(turn_context, ConversationData)

        #register activity
        self._add_conversation_reference(turn_context.activity)

        value = turn_context.activity.value
        text = turn_context.activity.text
        
        conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)
        user_id = conversation_reference.user.id
        member = await self.get_member(turn_context)
        self.logger.info(f"member: {member.email}")
    
        #get the users details
        user_name = conversation_reference.user.name
        tenant_id = conversation_reference.conversation.tenant_id
        email_address = member.email

        server_logging.logging.info(f"Message - User ID: {user_id}, TenantID: {tenant_id}")
        
        #user used a activity (button etc)
        if value:
            self.logger.info(f"Got Activity: {turn_context.activity}")
            # Get the input value. This will be in turn_context.activity.value['acDecision'].
            selected_value = turn_context.activity.value.get('acDecision', None)
            suggestions_value = turn_context.activity.value.get('suggestions', None)
            config_value = turn_context.activity.value.get('config_value', None)
            
            # You can then use the selected value to trigger the imBack event.
            if selected_value:
                
                if suggestions_value:
                    self.logger.info(selected_value)
                    self.logger.info(suggestions_value)
                    feedback = f"user_improvements: {suggestions_value}, {selected_value}"
                    send_to_bot(user_id, feedback)
                else:
                    self.logger.info(selected_value)
                    feedback = f"{selected_value}"
                    send_to_bot(user_id, feedback)

                return await turn_context.send_activities([
                            Activity(
                                type=ActivityTypes.typing
                            )])
            
            if config_value:
                feedback = f"{config_value}"
                send_to_bot(user_id, feedback)

                return await turn_context.send_activities([
                            Activity(
                                type=ActivityTypes.typing
                            )])
            
        if text:
            if text.lower() == "ping":
                #Channel Test
                await turn_context.send_activities([
                    Activity(
                        type=ActivityTypes.typing
                    ),
                    Activity(
                        type="delay",
                        value=3000
                    )])
                send_to_user(f"pong", user_id)

            else:
                message = random.choice(thinking_messages)
                
                #this will check the user has setup their app
                response = self.bot_dispatcher.run(text, user_id, user_name, tenant_id, email_address)
                if response:
                    send_to_user(response, user_id)
                else:
                    return await turn_context.send_activities([
                            Activity(
                                type=ActivityTypes.typing
                            )])

    def _add_conversation_reference(self, activity: Activity):
        conversation_reference = TurnContext.get_conversation_reference(activity)
        self.conversation_references[conversation_reference.user.id] = conversation_reference
        # Save conversation references to disk
        with open(self.filename, "wb") as file:
            pickle.dump(self.conversation_references, file)        

    async def process_message(self, ADAPTER):

        self.bot_dispatcher.process_bot_messages()
        "process messages in the notify queue and send to users based on conversation reference"
        bot_id, user_id, type, body, data = from_manager_to_user()

        if body:

            self.logger.debug(f"SERVER: user_id: {user_id}, type: {type}, body: {body}")

            conversation_reference = self.conversation_references.get(user_id, None)

            if conversation_reference is None:
                # Handle the case when the conversation reference is not found
                self.logger.info(f"Conversation reference not found for user ID: {user_id}")
                return
            
            if type == "prompt":
                await ADAPTER.continue_conversation(
                    conversation_reference,
                    lambda turn_context: turn_context.send_activity(MessageFactory.text(body)),
                    self._app_id,
                )
            elif type == "action":
                actions = [CardAction(**action) for action in data] if data else []
                message = Activity(
                    type=ActivityTypes.message,
                    attachments=[self.create_hero_card(body, actions)]
                    
                )
                await ADAPTER.continue_conversation(
                    conversation_reference,
                    lambda turn_context: turn_context.send_activity(message),
                    self._app_id,
                )
            elif type == "cards":
                if data:
                    card_data = json.loads(data)
                    message = Activity(
                        type=ActivityTypes.message,
                        attachments=[CardFactory.adaptive_card(card_data)]
                        
                    )
                    await ADAPTER.continue_conversation(
                        conversation_reference,
                        lambda turn_context: turn_context.send_activity(message),
                        self._app_id,
                    )
    