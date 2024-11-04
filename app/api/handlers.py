import json
from fastapi import WebSocket
from app.cache.schemas import QuizState
from app.cache.models import QuizData
from app.api.errors import Errors
from app.api.schemas import WsConnectionType
from app.db.models import DbUser, DbManager
from app.db.schemas import UserAnswer
import logging
from typing import Union

logger = logging.getLogger(__name__)

db_manager = DbManager()

MESSAGE_TYPES_DATA_FUNCTION_MAPPING = {}


def register_message_handler(message_type: str):
    def add_to_mapping_dict(func):
        MESSAGE_TYPES_DATA_FUNCTION_MAPPING[message_type] = func
        return func

    return add_to_mapping_dict


@register_message_handler("moderator-choice")
def handle_moderators_choice(
    message: dict,
    quiz_data: QuizData,
    connection_type: WsConnectionType,
    user: DbUser,
    current_timestamp: int,
) -> QuizData:
    """
    This function changes quiz state based on the moderator's choice event.
    Only moderators can change the quiz state from here.
    """
    try:
        if connection_type != WsConnectionType.MODERATOR:
            raise Errors.USER_FORBIDDEN
        choice = message.get("choice")
        option_type = choice.get("option_type")
        option = choice.get("option")
        if option_type == "cmd":
            if option == "Start Quiz":
                quiz_data.start_quiz(current_timestamp)
            elif option == "End Quiz":
                quiz_data.end_quiz()
            elif option == "Next Question":
                quiz_data.next_question(current_timestamp)
        return quiz_data
    except Exception as e:
        logger.error(f"Error in handle_moderator_choice: {e}")
        raise Errors.ServerError


@register_message_handler("participant-choice")
def handle_participent_choice(
    message: dict,
    quiz_data: QuizData,
    connection_type: WsConnectionType,
    user: DbUser,
    current_timestamp: int,
) -> QuizData:
    """
    This function changes quiz state based on a participant's choice event.
    Only participant can change the quiz state from here.
    """
    try:
        if connection_type != WsConnectionType.PARTICIPANT:
            raise Errors.USER_FORBIDDEN
        choice = message.get("choice")
        option_type = choice.get("option_type")
        option = choice.get("option")
        if option_type == "cmd":
            pass  # TODO
        if option_type == "answer":
            db_manager.quiz_participants_answers.insert_users_answer(
                UserAnswer.from_option(option)
            )
    except Exception as e:
        logger.error(f"Error in handle_moderator_choice: {e}")
        raise Errors.ServerError


def handle_message(
    message: dict,
    quiz_data: QuizData,
    connecrion_type: WsConnectionType,
    user: DbUser,
    current_timestamp: int,
) -> tuple[QuizData, dict, dict]:
    """
    This function manages the message handling process.
    Quiz data is updated based on the message type.
    Messages are sent from the WebSocket client to the server or from the server (in case of a question timeout) to the server.
    """
    try:
        message_type = message.get("type")
        if message_type not in MESSAGE_TYPES_DATA_FUNCTION_MAPPING:
            raise Errors.INVALID_MESSAGE_TYPE

        updated_quiz_data = MESSAGE_TYPES_DATA_FUNCTION_MAPPING[message_type](
            message, quiz_data, connecrion_type, user, current_timestamp
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
        if quiz_data.quiz_state == QuizState.WAITING_TO_START:
            return {
                "moderator_display_text": f"Quiz is waiting to start.",
                "participant_display_text": f"Quiz is waiting to start.",
                "moderator_menu": [
                    {"option": "Start Quiz", "option_type": "cmd"},
                    {"option": "End Quiz", "option_type": "cmd"},
                ],
                "participant_menu": [{"option": "Leave Quiz", "option_type": "cmd"}],
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                **payload,
            }

        if quiz_data.quiz_state == QuizState.ACTIVE:

            options = [
                {
                    "option": a.answer,
                    "option_type": "answer",
                    "answer-id": a.answer_id,
                    "quiz-id": a.quiz_id,
                }
                for a in quiz_data.current_question.answers.answers
            ]

            return {
                "moderator_display_text": f"Quiz is active.\nQuestion {quiz_data.current_question_number}\nQuestion: {quiz_data.current_question.question}",
                "participant_display_text": f"Quiz is active.\nQuestion {quiz_data.current_question_number}\nQuestion: {quiz_data.current_question.question}",
                "participant_menu": options
                + [{"option": "End Quiz", "option_type": "cmd"}],
                "moderator_menu": [
                    {"option": "Next Question", "option_type": "cmd"},
                    {"option": "End Quiz", "option_type": "cmd"},
                ],
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                **payload,
            }

        if quiz_data.quiz_state == QuizState.QUESTION_TIMEDOUT:
            return {
                "moderator_display_text": f"Question timed out.",
                "participant_display_text": f"Question timed out.",
                "participant_menu": [{"option": "End Quiz", "option_type": "cmd"}],
                "moderator_menu": [
                    {"option": "Next Question", "option_type": "cmd"},
                    {"option": "End Quiz", "option_type": "cmd"},
                ],
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                **payload,
            }
        if quiz_data.quiz_state == QuizState.ENDED:
            ...
    except Exception as e:
        logger.error(f"Error in get_payload: {e}")
        raise Errors.ServerError.to_websocket_close()


@register_message_handler("timeout")
def handle_timeout(
    message: dict,
    quiz_data: QuizData,
    connection_type: WsConnectionType,
    user: DbUser,
    current_timestamp: int,
) -> QuizData:
    """
    This function changes quiz state based on a timeout event.
    """
    try:
        if connection_type != WsConnectionType.MODERATOR:
            raise Errors.USER_FORBIDDEN
        if quiz_data.quiz_state == QuizState.ACTIVE:
            quiz_data.timeout_question()
        return quiz_data
    except Exception as e:
        logger.error(f"Error in handle_timeout: {e}")
        raise Errors.ServerError
