import json
from fastapi import WebSocket
from app.cache.schemas import QuizState
from app.cache.models import QuizData
from app.api.errors import Errors
from app.api.schemas import WsConnectionType
import logging
from typing import Union

logger = logging.getLogger(__name__)

MESSAGE_TYPES_DATA_FUNCTION_MAPPING = {}


def register_message_handler(message_type: str):
    def add_to_mapping_dict(func):
        MESSAGE_TYPES_DATA_FUNCTION_MAPPING[message_type] = func
        return func

    return add_to_mapping_dict


@register_message_handler("moderator-choice")
def handle_moderator_choice(
    message: dict, quiz_data: QuizData, connection_type: WsConnectionType
) -> QuizData:
    """
    This function changes quiz state based on the moderator's choice event.
    Only moderators can change the quiz state from here.
    """
    try:
        if connection_type == WsConnectionType.PARTICIPANT:
            raise Errors.USER_FORBIDDEN
        choice = message.get("choice")
        if choice == "Start Quiz" and quiz_data.quiz_state == QuizState.WAITING:
            quiz_data.start_quiz()
        return quiz_data
    except Exception as e:
        logger.error(f"Error in handle_moderator_choice: {e}")
        raise Errors.ServerError


def handle_message(
    message: dict, quiz_data: QuizData, connecrion_type: WsConnectionType
) -> tuple[QuizData, dict, dict]:
    try:
        message_type = message.get("type")
        if message_type not in MESSAGE_TYPES_DATA_FUNCTION_MAPPING:
            raise Errors.INVALID_MESSAGE_TYPE

        updated_quiz_data = MESSAGE_TYPES_DATA_FUNCTION_MAPPING[message_type](
            message, quiz_data, connecrion_type
        )
        return updated_quiz_data
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        raise Errors.ServerError


def get_payload(
    quiz_data: QuizData, moderator_event: str = None, participant_event: str = None
) -> Union[dict, None]:
    """
    Gets the payload to be sent to the moderator client and the payload to be published to all participants.
    """
    try:
        payload = {"type": "update"}
        if quiz_data.quiz_state == QuizState.WAITING:
            return {
                "moderator_display_text": f"Quiz is waiting to start.",
                "participant_display_text": f"Quiz is waiting to start.",
                "moderator_menu": ["Start Quiz", "End Quiz"],
                "participant_menu": ["Leave Quiz"],
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                **payload,
            }

        if quiz_data.quiz_state == QuizState.ACTIVE:

            options = [a.answer for a in quiz_data.current_question.answers.answers]

            return {
                "moderator_display_text": f"Quiz is active.\nQuestion {quiz_data.current_question_number}\nQuestion: {quiz_data.current_question.question}",
                "participant_display_text": f"Quiz is active.\nQuestion {quiz_data.current_question_number}\nQuestion: {quiz_data.current_question.question}",
                "participant_menu": options + ["End Quiz"],
                "moderator_menu": ["Next Question", "Pause Quiz", "End Quiz"],
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                **payload,
            }
    except Exception as e:
        logger.error(f"Error in get_payload: {e}")
        raise Errors.ServerError.to_websocket_close()


def handle_pubsub_message(message: dict, quiz_data: QuizData) -> None:
    """
    Handles messages from the moderator's WebSocket connection.
    Returns payload to send to ws after receiving a pub message.
    """
    message
    return message
