import json
from app.db.models import DbManager
from datetime import datetime
from app.db.schemas import (
    UserRole,
    DbUser,
    UserPermission,
    DbSession,
    DbParticipent,
    DbQuestion,
    AnswerOption,
    QuestionType,
    AnswerOptions,
)


if __name__ == "__main__":
    # Initialize the database manager
    db = DbManager()
    # db.create_tables()
    # user = DbUser(
    #     user_id="u-123",
    #     username="test",
    #     email="user@email.com",
    #     create_date=datetime.now(),
    # )
    # db.users.add_user(user)
    user2 = DbUser(
        user_id="u-456",
        username="test2",
        email="user2@email.com",
        create_date=datetime.now(),
    )
    db.users.add_user(user2)
    permissions = UserPermission(
        quiz_id="q-123", user_id="u-123", permission=UserRole.MODERATOR
    )
    # db.quiz_permissions.add_permission(permissions)
    # question = DbQuestion(
    #     quiz_id="q-123",
    #     question_id="q-123-1",
    #     question="What is 1+1",
    #     question_number=1,
    #     question_type=QuestionType.MULTIPLE_CHOICE,
    #     points=10,
    #     answers=AnswerOptions(
    #         options=[
    #             AnswerOption(answer="1", correct_answer=False),
    #             AnswerOption(answer="2", correct_answer=True),
    #         ]
    #     ),
    # )
    # db.questions.insert_question(question)

    # session = DbSession(
    #     session_id="s-123",
    #     quiz_id="q-123",
    #     start_datetime=datetime.now(),
    #     room_id="r-123",
    #     moderator_id="u-123",
    # )
    # db.quiz_sessions.add_session(session)
