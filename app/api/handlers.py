import json
from fastapi import WebSocket
from app.cache.schemas import QuizState
from app.cache.models import QuizData
from app.api.errors import Errors, UserLeftException
from app.api.schemas import WsConnectionType
from app.db.models import DbUser, DbManager
from app.db.schemas import UserAnswer
import logging
from typing import Union, Optional

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
) -> tuple[QuizData, Optional[str], Optional[str]]:
    """
    This function changes quiz state based on the moderator's choice event.
    Only moderators can change the quiz state from here.
    """
    try:
        moderator_event, participant_event = None, None
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
            elif option == "Go To Results":
                quiz_data.get_results()
        return quiz_data, moderator_event, participant_event
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
) -> tuple[QuizData, Optional[str], Optional[str]]:
    """
    This function changes quiz state based on a participant's choice event.
    Only participant can change the quiz state from here.
    """
    try:
        moderator_event, participant_event = None, None

        if connection_type != WsConnectionType.PARTICIPANT:
            raise Errors.USER_FORBIDDEN
        choice = message.get("choice")
        option_type = choice.get("option_type")
        option = choice.get("option")
        if option_type == "cmd":
            if option == "Leave Quiz":
                raise UserLeftException
        if option_type == "answer":
            correct_answer = answer_is_correct(choice, quiz_data)
            db_manager.quiz_participants_answers.insert_users_answer(
                UserAnswer(
                    user_id=user.user_id,
                    question_id=choice.get("question-id"),
                    answer_id=choice.get("answer-id"),
                    timestamp=current_timestamp,
                    session_id=quiz_data.session_id,
                    quiz_id=quiz_data.quiz_id,
                    points=quiz_data.current_question.points,
                    is_correct=correct_answer,
                )
            )
            moderator_event = f"Participant {user.user_id} answered question"
        return quiz_data, moderator_event, participant_event

    except UserLeftException:
        raise UserLeftException
    except Exception as e:
        logger.error(f"Error in handle_moderator_choice: {e}")
        raise Errors.ServerError


def handle_message(
    message: dict,
    quiz_data: QuizData,
    connecrion_type: WsConnectionType,
    user: DbUser,
    current_timestamp: int,
) -> tuple[QuizData, Optional[str], Optional[str]]:
    """
    This function manages the message handling process.
    Quiz data is updated based on the message type.
    Messages are sent from the WebSocket client to the server or from the server (in case of a question timeout) to the server.
    """
    try:
        message_type = message.get("type")
        if message_type not in MESSAGE_TYPES_DATA_FUNCTION_MAPPING:
            raise Errors.INVALID_MESSAGE_TYPE

        (updated_quiz_data, moderator_event, participant_event) = (
            MESSAGE_TYPES_DATA_FUNCTION_MAPPING[message_type](
                message, quiz_data, connecrion_type, user, current_timestamp
            )
        )
        return updated_quiz_data, moderator_event, participant_event
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
                "type": "update",
            }

        if quiz_data.quiz_state == QuizState.ACTIVE:
            last_question = quiz_data.current_question_number == len(
                quiz_data.questions
            )
            moderators_menu = get_active_mod_menu(last_question)

            options = [
                {
                    "option": a.answer,
                    "option_type": "answer",
                    "answer-id": a.answer_id,
                    "quiz-id": a.quiz_id,
                    "question-id": a.question_id,
                }
                for a in quiz_data.current_question.answers.answers
            ]
            display = f"Quiz is active.\nQuestion {quiz_data.current_question_number}\nQuestion: {quiz_data.current_question.question}"

            return {
                "moderator_display_text": display,
                "participant_display_text": display,
                "participant_menu": options
                + [{"option": "Leave Quiz", "option_type": "cmd"}],
                "moderator_menu": moderators_menu,
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                "type": "update",
            }

        if quiz_data.quiz_state == QuizState.QUESTION_TIMEDOUT:
            last_question = quiz_data.current_question_number == len(
                quiz_data.questions
            )

            moderators_menu = get_active_mod_menu(last_question)

            return {
                "moderator_display_text": f"Question timed out.",
                "participant_display_text": f"Question timed out.",
                "participant_menu": [{"option": "Leave Quiz", "option_type": "cmd"}],
                "moderator_menu": moderators_menu,
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                "type": "update",
            }
        if quiz_data.quiz_state == QuizState.ENDED:
            return {
                "moderator_display_text": f"Quiz Ended.",
                "participant_display_text": f"Quiz Ended.",
                "participant_menu": [{"option": "Leave Quiz", "option_type": "cmd"}],
                "moderator_menu": [{"option": "End Quiz", "option_type": "cmd"}],
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                "type": "end",
            }
            raise
        if quiz_data.quiz_state == QuizState.SHOW_RESULTS:
            res_string = f"Quiz is over\n Results:\n{quiz_data.pretty_print_results()}"
            return {
                "moderator_display_text": res_string,
                "participant_display_text": res_string,
                "participant_menu": [{"option": "Leave Quiz", "option_type": "cmd"}],
                "moderator_menu": [{"option": "End Quiz", "option_type": "cmd"}],
                "moderator_event": moderator_event,
                "participant_event": participant_event,
                "quiz_data": quiz_data.model_dump_json(),
                "type": "update",
            }
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
        moderator_event, participant_event = None, None
        if connection_type != WsConnectionType.MODERATOR:
            raise Errors.USER_FORBIDDEN
        if quiz_data.quiz_state == QuizState.ACTIVE:
            quiz_data.timeout_question()
        return quiz_data, moderator_event, participant_event
    except Exception as e:
        logger.error(f"Error in handle_timeout: {e}")
        raise Errors.ServerError


def answer_is_correct(selected_choice, quiz_data) -> bool:

    if quiz_data.quiz_id != selected_choice.get("quiz-id"):
        return False

    quiz_data_question = [
        q
        for q in quiz_data.questions
        if q.question_id == selected_choice.get("question-id")
    ][0]

    for a in quiz_data_question.answers.answers:
        if a.answer_id == selected_choice.get("answer-id"):
            return a.correct_answer
    return False


def get_active_mod_menu(last_question: bool) -> list[dict]:
    if last_question:
        return [
            {"option": "Go To Results", "option_type": "cmd"},
            {"option": "End Quiz", "option_type": "cmd"},
        ]
    else:
        return [
            {"option": "Next Question", "option_type": "cmd"},
            {"option": "End Quiz", "option_type": "cmd"},
        ]


class UserLeftException(Exception):
    def __init__(self):
        super().__init__()
        self.message = "User Left"

        def __str__(self):
            return "User Left"
