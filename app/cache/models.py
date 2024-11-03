import asyncio
import logging
import json
from app.db.models import DbManager
from app.cache.schemas import QuizState
from app.db.schemas import DbSession, DbQuestion
from app.api.errors import Errors
from pydantic import BaseModel, field_validator
from typing import Optional, AsyncGenerator, Dict
import os
import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

db_manager = DbManager()


class CacheManager:
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
        )
        self.verify_connection()

    def verify_connection(self):
        try:
            self.client.ping()
            logger.info("Connected to Redis successfully.")
        except redis.RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def get_cache_key(self, session_id: str):
        return f"session:{session_id}"

    def get_time(self) -> tuple:
        """
        Gets the current time from Redis server using TIME command.
        Returns a tuple of (timestamp_seconds, microseconds)
        """
        try:
            redis_time = self.client.time()
            return redis_time
        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
            return None

    def get_timestamp(self) -> int:
        """
        Gets the current timestamp from Redis server using TIME command.
        Returns the timestamp in seconds.
        """
        try:
            redis_time = self.get_time()
            if redis_time:
                return int(redis_time[0])
            return None
        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
            return None

    def add_session_data_to_cache(self, session_data: DbSession) -> "QuizData":
        """
        Add session data to the cache.
        """
        try:
            cache_key = self.get_cache_key(session_data.session_id)

            quiz_data = QuizData(
                session_id=session_data.session_id,
                quiz_state=QuizState.WAITING,
                quiz_id=session_data.quiz_id,
                current_question_number=0,
                current_question=None,
            )

            self.client.set(cache_key, json.dumps(quiz_data.model_dump_json()))

            logger.info(f"Session data added to cache for session {cache_key}")

            return quiz_data
        except Exception as e:
            logger.error(f"Error in add_session_data: {e}")
            return None

    def update_quiz_data(self, quiz_data: "QuizData") -> bool:
        """
        Add session data to the cache.
        """
        try:
            cache_key = self.get_cache_key(quiz_data.session_id)
            self.client.set(cache_key, json.dumps(quiz_data.model_dump_json()))
            logger.info(f"Session data updated in cache for session {cache_key}")
            return True
        except Exception as e:
            logger.error(f"Error in update_quiz_data: {e}")
            return False

    def remove_session_data(self, session_id: str) -> bool:
        """
        Remove session data from the cache.
        """
        try:
            cache_key = self.get_cache_key(session_id)
            self.client.delete(cache_key)
            logger.info(f"Session data removed from cache for session {cache_key}")
            return True
        except Exception as e:
            logger.error(f"Error in remove_session_data: {e}")
            return False

    def get_quiz_data(self, session_id: str) -> Optional["QuizData"]:
        """
        Get session data from the cache.
        """
        try:
            cache_key = self.get_cache_key(session_id)
            quiz_data = self.client.get(cache_key)
            if quiz_data:
                quiz_data_dict = json.loads(quiz_data.decode())
                return QuizData(
                    session_id=quiz_data_dict.get("session_id"),
                    quiz_state=quiz_data_dict.get("quiz_state"),
                    quiz_id=quiz_data_dict.get("quiz_id"),
                    current_question_number=quiz_data_dict.get(
                        "current_question_number"
                    ),
                    current_question=(
                        DbQuestion.get_from_cache(
                            quiz_data_dict.get("current_question")
                        )
                        if quiz_data_dict.get("current_question")
                        else None
                    ),
                )

            else:
                raise Errors.ServerError(
                    status_code=500,
                    error_code=5001,
                    message="Quiz data not found in cache",
                )
        except Exception as e:
            logger.error(f"Error in get_quiz_data: {e}")
            raise Errors.ServerError(
                status_code=500, error_code=5001, message="Quiz data not found in cache"
            )

    def clean_all_cache(self):
        """
        Clean all cache data
        """
        try:
            self.client.flushall()
            logger.info(f"Cache data cleaned")
            return True
        except Exception as e:
            logger.error(f"Error in clean_all_cache: {e}")
            return False

    def close(self):
        self.client.close()


class QuizData(BaseModel):
    session_id: str
    quiz_state: QuizState
    quiz_id: str
    current_question_number: int
    current_question: Optional[DbQuestion]

    @field_validator("quiz_state")
    def validate_quiz_state(cls, v):
        return v.value

    def model_dump_json(self):
        return {
            "session_id": self.session_id,
            "quiz_state": self.quiz_state,
            "quiz_id": self.quiz_id,
            "current_question_number": self.current_question_number,
            "current_question": (
                self.current_question.model_dump_json()
                if self.current_question
                else None
            ),
        }

    def client_model_dump_json(self):
        """
        This function is to send the data to the client. Hiding the next question and answers.
        """
        return {
            "session_id": self.session_id,
            "quiz_state": self.quiz_state,
            "quiz_id": self.quiz_id,
            "current_question_number": self.current_question_number,
            "current_question": (
                self.current_question.client_model_dump_json()
                if self.current_question
                else None
            ),
        }

    def start_quiz(self):
        self.quiz_state = QuizState.ACTIVE
        self.current_question_number = 1
        self.current_question = db_manager.questions.get_question_by_index(
            self.quiz_id, self.current_question_number
        )


class PubSubManager:
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
        )
        self.publish_queue = asyncio.Queue()

    def add_payload_to_publish_queue(self, session_id: str, payload: dict) -> None:
        try:
            channel = self.get_session_channel(session_id)
            message = {"payload": payload, "channel": channel}
            self.publish_queue.put_nowait(message)
        except Exception as e:
            logger.error(f"Error in add_payload_to_publish_queue: {e}")

    async def _publish_loop(self) -> None:
        """Publishes a message to a Redis channel for a session."""
        while True:
            try:
                message = await self.publish_queue.get()
                payload = message.get("payload")
                channel = message.get("channel")
                subscribers = self.client.publish(channel, json.dumps(payload))
                logger.debug(f"Broadcasted message to {subscribers} subscribers")
            except Exception as e:
                logger.error(f"Error in _publish_loop: {e}")

    async def pubsub_listener_to_async(self, session_id: str) -> AsyncGenerator:
        """Yields messages from a Redis channel for a session."""
        channel = self.get_session_channel(session_id)
        try:
            logger.debug(f"Subscribing to channel: {channel}")
            while True:
                message = self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    yield message
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in pubsub_listener_to_async: {e}")

    async def listen_to_channel(self, session_id: str) -> AsyncGenerator[dict, None]:
        """
        Listen to a specific channel and yield messages.
        This function is for each WebSocket connection to listen to the channel.
        """
        try:
            channel = self.get_session_channel(session_id)

            pubsub = self.client.pubsub()

            pubsub.subscribe(channel)

            logger.debug(f"Starting listener for channel: {channel}")

            while True:
                message = pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode message on {channel}: {e}")
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in channel listener for {channel}: {e}")
            raise Errors.ServerError(
                status_code=500, error_code=5001, message="Quiz data not found in cache"
            )

    def get_session_channel(self, session_id: str) -> str:
        """Get the channel name for a session."""
        return f"session:{session_id}"

    async def stop_publish_loop(self):
        """Stop the publish loop"""
        self._publish_loop_task.cancel()
        await self._publish_loop_task

    async def close(self):
        """Close the Redis connection."""
        self.client.close()
        await self.stop_publish_loop()
        logger.info("PubSubManager closed")

    async def start(self):
        self._publish_loop_task = asyncio.create_task(self._publish_loop())
        logger.info("PubSubManager started")
        return self
