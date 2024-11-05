import asyncio
from datetime import datetime
import os
from fastapi import FastAPI, WebSocket
import logging
from app.api.errors import UserLeftException
from app.api.models import (
    NewQuizRequest,
    NewSessionRequest,
    SignupRequest,
    WebSocketManager,
)
from app.cache.models import CacheManager, PubSubManager
from app.db.models import DbManager, DbUser
from contextlib import asynccontextmanager
from app.api.models import QuizEndedException
from app.db.schemas import (
    AnswerOption,
    AnswerOptions,
    DbQuestion,
    DbQuiz,
    DbSession,
    UserPermission,
    UserRole,
)

cache_manager = CacheManager()
db_manager = DbManager()
pubsub_manager = PubSubManager()

WEBSOCKET_TIMEOUT = int(os.getenv("WEBSOCKET_TIMEOUT", "360"))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager to handle the lifespan of the FastAPI application.
    """
    try:
        await pubsub_manager.start()
        yield
    finally:
        await cache_manager.close()
        await db_manager.close()
        await pubsub_manager.close()


app = FastAPI(lifespan=lifespan)


@app.websocket("/{session_id}")
async def main_ws(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for quiz moderators.
    Handles connection validation, message processing, and resource cleanup.
    """
    manager = WebSocketManager(
        websocket=websocket,
        session_id=session_id,
        cache_manager=cache_manager,
        db_manager=db_manager,
        pubsub_manager=pubsub_manager,
    )

    await websocket.accept()

    logger.info(f"Moderator connected to session {session_id}")

    if not await manager.validate_connection_and_initialize_cache():
        return

    try:

        await manager.send_initial_payload()

        tasks = manager.manage_tasks()

        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
            timeout=WEBSOCKET_TIMEOUT,
        )

        for task in pending:
            # Cancel tasks if the connection is closed
            if websocket.client_state.value != 1:
                logger.info(
                    f"Closing task: {task} for session {session_id} for user {manager.user.user_id}"
                )
                task.cancel()

        for task in done:
            if isinstance(task.exception(), QuizEndedException) or isinstance(
                task.exception(), UserLeftException
            ):
                for p in pending:
                    p.cancel()
                break
            else:
                logger.error(
                    f"Task {task} for session {session_id} for user {manager.user.user_id} exited with exception {task.exception()}"
                )

    except Exception as e:
        logger.error(f"Error in WS Manager: {e}")
    finally:
        logger.info(f"Moderator disconnected from session {session_id}")
        # Close the connection if it's not already closed
        if websocket.client_state.value != 2:
            await manager.close_connection()


@app.post("/users/signup")
def signup(signup_request: SignupRequest):
    """
    Endpoint for users to sign up for a quiz.
    """
    try:
        user = DbUser(
            user_id=DbUser.generate_new_id(),
            username=signup_request.username,
            email=signup_request.email,
            create_date=datetime.now(),
        )
        db_manager.users.add_user(user)
        return {"user_id": user.user_id}
    except Exception as e:
        logger.error(f"Error in signup: {e}")
        return {"error": "Error in signup"}


@app.post("/sessions/new")
def create_session(new_session_request: NewSessionRequest):
    """
    Endpoint to create a new session.
    """
    session = DbSession(
        session_id=DbSession.generate_session_id(),
        quiz_id=new_session_request.quiz_id,
        start_datetime=datetime.now(),
        room_id=DbSession.generate_room_id(),
        moderator_id=new_session_request.user_id,
    )
    db_manager.quiz_sessions.add_session(session)
    return {"session_id": session.session_id}


@app.post("/quiz/new")
def create_quiz(new_quiz_request: NewQuizRequest):
    """
    Endpoint to create a new quiz.
    """
    quiz = DbQuiz(
        quiz_id=DbQuiz.generate_quiz_id(),
        quiz_name=new_quiz_request.quiz.name,
        quiz_description=new_quiz_request.quiz.description,
    )
    db_manager.quizzes.add_quiz(quiz)

    permissions = UserPermission(
        user_id=new_quiz_request.user_id,
        quiz_id=quiz.quiz_id,
        permission=UserRole.MODERATOR,
    )
    db_manager.quiz_permissions.add_permission(permissions)

    for i, q_ in enumerate(new_quiz_request.quiz.questions, 1):
        question_id = DbQuestion.generate_question_id()
        question = DbQuestion(
            question_id=question_id,
            question=q_.question,
            question_number=i,
            question_type=q_.question_type,
            points=q_.points,
            seconds_to_answer=q_.seconds_to_answer,
            answers=AnswerOptions(
                answers=[
                    AnswerOption(
                        answer=a.answer,
                        correct_answer=a.correct_answer,
                        answer_id=AnswerOption.generate_answer_id(),
                        question_id=question_id,
                        quiz_id=quiz.quiz_id,
                    )
                    for a in q_.answers
                ]
            ),
            quiz_id=quiz.quiz_id,
        )
        db_manager.questions.insert_question(question)
    return {"quiz_id": quiz.quiz_id}
