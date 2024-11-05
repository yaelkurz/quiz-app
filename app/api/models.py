import asyncio
import os
from typing import Any, Dict, Optional, List
from fastapi import WebSocket
import logging

from pydantic import BaseModel
from app.cache.models import CacheManager, PubSubManager, QuizData
from app.db.models import DbManager, DbUser
from app.cache.schemas import QuizState
from app.api.schemas import WsConnectionType
from app.api.errors import Errors, QuizEndedException
from app.api.handlers import (
    handle_message,
    get_payload,
)
from app.db.schemas import DbQuiz

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "3"))


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

    async def validate_connection_and_initialize_cache(self) -> bool:
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

                quiz_questions = self.db_manager.questions.get_quiz_questions(
                    db_session.quiz_id
                )

                self.quiz_data = self.cache_manager.add_to_cache(
                    db_session, quiz_questions
                )

            elif self.connection_type == WsConnectionType.PARTICIPANT:

                self.quiz_data = self.cache_manager.get_quiz_data(self.session_id)

                if self.quiz_data is None:
                    raise Errors.SESSION_NOT_FOUND

            if self.quiz_data.quiz_state != QuizState.WAITING_TO_START:
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
                    message = handle_pubsub_msg(message, self.quiz_data)
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

                self.quiz_data = self.cache_manager.get_quiz_data(self.session_id)

                self.quiz_data, moderator_event, participant_event = handle_message(
                    message,
                    self.quiz_data,
                    self.connection_type,
                    self.user,
                    self.cache_manager.get_timestamp(),
                )

                if self.quiz_data is not None:
                    # Only when quiz_data is updated by moderator - send to all participants
                    self.cache_manager.update_quiz_data(self.quiz_data)

                    payload = get_payload(
                        self.quiz_data, moderator_event, participant_event
                    )

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

                self.quiz_data = self.cache_manager.get_quiz_data(self.session_id)

                payload = get_payload(self.quiz_data)

                await self.dispatch_to_client(payload=payload)
        except Exception as e:
            logger.error(f"Error in heartbeat: {e}")

    def manage_tasks(self) -> List[asyncio.Task]:
        try:
            tasks = []
            tasks.append(
                asyncio.create_task(
                    self.listen_to_pubsub_channel(),
                    name=f"Pubsub Task for {self.session_id}",
                )
            )
            tasks.append(
                asyncio.create_task(
                    self.listen_to_websocket(), name=f"WS Task for {self.session_id}"
                )
            )

            tasks.append(
                asyncio.create_task(
                    self.heartbeat(), name=f"Heartbeat Task for {self.session_id}"
                )
            )
            if self.connection_type == WsConnectionType.MODERATOR:
                tasks.append(
                    asyncio.create_task(
                        self.quiz_timer(),
                        name=f"Question Timeout Task for {self.session_id}",
                    )
                )

            return tasks
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

    async def quiz_timer(self) -> None:
        """
        This is for timing out questions.
        """
        try:
            while True:
                quiz_data = self.cache_manager.get_quiz_data(self.session_id)

                if quiz_data.quiz_state != QuizState.ACTIVE:
                    await asyncio.sleep(1)
                    continue

                current_timestamp = self.cache_manager.get_timestamp()

                end_timestamp = quiz_data.current_question_end_timestamp

                if current_timestamp >= end_timestamp:

                    self.quiz_data, _, _ = handle_message(
                        {"type": "timeout"},
                        self.quiz_data,
                        self.connection_type,
                        self.user,
                        current_timestamp,
                    )

                    self.cache_manager.update_quiz_data(self.quiz_data)

                    payload = get_payload(self.quiz_data)

                    self.pubsub_manager.add_payload_to_publish_queue(
                        self.session_id, payload
                    )

                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in question_clock: {e}")
            raise e


def handle_pubsub_msg(message: dict, quiz_data: QuizData) -> dict:
    """
    Handle the pub/sub message and update the quiz data.
    """
    try:
        type = message.get("type")
        if type == "end":
            raise QuizEndedException
        return message
    except Exception as e:
        if e != QuizEndedException:
            logger.error(f"Error in handle_pubsub_msg: {e}")
        raise e


class SignupRequest(BaseModel):
    username: str
    email: str


class NewSessionRequest(BaseModel):
    quiz_id: str
    user_id: str


class NewQuizRequestAnswer(BaseModel):
    answer: str
    correct_answer: bool


class NewQuizRequestQuestion(BaseModel):
    question: str
    question_type: str
    points: int
    seconds_to_answer: int
    answers: List[NewQuizRequestAnswer]


class NewQuizRequestQuiz(BaseModel):
    name: str
    description: str
    questions: List[NewQuizRequestQuestion]


class NewQuizRequest(BaseModel):
    quiz: NewQuizRequestQuiz
    user_id: str
