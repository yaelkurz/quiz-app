import asyncio
import os
from typing import Tuple, Any, Optional
from fastapi import WebSocket
import logging
from app.cache.models import CacheManager, PubSubManager, QuizData
from app.db.models import DbManager, DbUser
from app.cache.schemas import QuizState
from app.api.schemas import WsConnectionType
from app.api.errors import Errors
from app.api.handlers import (
    handle_message,
    get_payload,
)

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))


class WebSocketManager:
    """Manages WebSocket connections and related tasks for quiz moderators."""

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        cache_manager: CacheManager,
        db_manager: DbManager,
        pubsub_manager: PubSubManager,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.cache_manager = cache_manager
        self.db_manager = db_manager
        self.pubsub_manager = pubsub_manager
        self.connection_type: Optional[WsConnectionType] = None
        self.quiz_data: Optional[QuizData] = None
        self.user = Optional[DbUser]

    async def validate_connection(self) -> bool:
        """Validate the WebSocket connection parameters."""
        try:
            user_id = self.websocket.headers.get("user_id")
            role = self.websocket.headers.get("role")

            self.connection_type = WsConnectionType(role)

            if user_id is None:
                raise Errors.MISSING_USER_ID_HEADER

            if self.connection_type == WsConnectionType.MODERATOR:
                db_session = self.db_manager.quiz_sessions.get_session(self.session_id)

                if db_session is None:
                    raise Errors.SESSION_NOT_FOUND

                if db_session.moderator_id != user_id:
                    raise Errors.USER_FORBIDDEN

                self.quiz_data = self.cache_manager.add_session_data_to_cache(
                    db_session
                )

            elif self.connection_type == WsConnectionType.PARTICIPANT:

                self.quiz_data = self.cache_manager.get_quiz_data(self.session_id)

                if self.quiz_data is None:
                    raise Errors.SESSION_NOT_FOUND

            if self.quiz_data.quiz_state != QuizState.WAITING:
                raise Errors.SESSION_CLOSED_FOR_NEW_PARTICIPANTS

            self.user = self.db_manager.users.get_user(user_id)

            return True
        except Exception as e:
            raise e

    async def listen_to_pubsub_channel(self) -> None:
        """Listen to pub/sub messages and handle them."""
        try:
            async for message in self.pubsub_manager.listen_to_channel(self.session_id):
                logger.debug(f"Received pub/sub message, session_id: {self.session_id}")

                self.quiz_data = self.cache_manager.get_quiz_data(self.session_id)

                if self.quiz_data is None:
                    logger.error(
                        f"Quiz data not found in cache for session: {self.session_id}"
                    )
                    return

                if message:
                    await self.dispatch_to_client(message)

        except Exception as e:
            logger.error(f"Error in listen_to_pubsub_channel: {e}")
            raise e

    async def listen_to_websocket(self) -> None:
        """
        Listen to WebSocket messages and handle them.
        """
        try:
            while True:

                if self.websocket.client_state.value != 1:
                    break

                message = await self.websocket.receive_json()

                self.quiz_data = handle_message(
                    message, self.quiz_data, self.connection_type
                )

                payload = get_payload(self.quiz_data)

                self.cache_manager.update_quiz_data(self.quiz_data)

                self.pubsub_manager.add_payload_to_publish_queue(
                    self.session_id, payload
                )

        except Exception as e:
            logger.info(f"error in listen_to_websocket: {e}")

    async def close_connection(self, error: Optional[Any] = None) -> None:
        """
        Close the WebSocket connection with optional error details.
        """
        if error:
            await self.websocket.close(**error.to_websocket_close())
        else:
            await self.websocket.close()

    async def heartbeat(self):
        """Send periodic pings to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.dispatch_to_client(payload={"type": "heartbeat"})
        except Exception as e:
            logger.error(f"Error in heartbeat: {e}")

    def manage_tasks(self) -> Tuple[asyncio.Task, asyncio.Task, asyncio.Task]:
        try:
            pubsub_task = asyncio.create_task(
                self.listen_to_pubsub_channel(),
                name=f"Pubsub Task for {self.session_id}",
            )
            ws_task = asyncio.create_task(
                self.listen_to_websocket(), name=f"WS Task for {self.session_id}"
            )

            heartbeat_task = asyncio.create_task(
                self.heartbeat(), name=f"Heartbeat Task for {self.session_id}"
            )
            return pubsub_task, ws_task, heartbeat_task
        except Exception as e:
            logger.error(f"Error in manage_tasks: {e}")
            raise e

    async def send_initial_payload(self) -> None:
        """
        After the WS is connected, the initial payload is sent to the client.
        """
        try:

            participant_event, moderator_event = None, None

            if self.connection_type == WsConnectionType.PARTICIPANT:
                participant_event = f"Participant {self.user.user_id} Joined Quiz"
                moderator_event = f"Participant {self.user.user_id} Joined Quiz"

            initial_payload = get_payload(
                self.quiz_data, moderator_event, participant_event
            )

            await self.dispatch_to_client(initial_payload)

            self.pubsub_manager.add_payload_to_publish_queue(
                self.session_id, initial_payload
            )

        except Exception as e:
            logger.error(f"Error in send_initial_payload: {e}")
            raise e

    async def dispatch_to_client(
        self,
        payload: dict,
    ) -> None:
        try:
            if payload.get("type") == "update":
                payload["quiz-state"] = self.quiz_data.client_model_dump_json()
            payload["timestamp"] = self.cache_manager.get_timestamp()
            await self.websocket.send_json(payload)
        except Exception as e:
            logger.error(f"Error dispatching data to client: {e}")
            raise e
