from app.db.models import DbManager
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
    DbQuiz,
    UserAnswer,
)


if __name__ == "__main__":
    # Initialize the database manager
    db = DbManager()
    db.create_tables()
    # user = DbUser(
    #     user_id="u-123",
    #     username="test",
    #     email="user@email.com",
    #     create_date=datetime.now(),
    # )
    # db.users.add_user(user)
    # user2 = DbUser(
    #     user_id="u-456",
    #     username="test2",
    #     email="user2@email.com",
    #     create_date=datetime.now(),
    # )
    # db.users.add_user(user2)
    # quiz = DbQuiz(
    #     quiz_id="q-123", quiz_name="Test Quiz", quiz_description="Test Description"
    # )
    # db.quizzes.add_quiz(quiz)
    # permissions = UserPermission(
    #     quiz_id="q-123", user_id="u-123", permission=UserRole.MODERATOR
    # )
    # db.quiz_permissions.add_permission(permissions)

    # question_1 = DbQuestion(
    #     quiz_id="q-123",
    #     question_id="q-123-1",
    #     question="What is 1+1",
    #     question_number=1,
    #     question_type=QuestionType.MULTIPLE_CHOICE,
    #     points=10,
    #     seconds_to_answer=30,
    #     answers=AnswerOptions(
    #         answers=[
    #             AnswerOption(
    #                 answer="1",
    #                 correct_answer=False,
    #                 answer_id="a",
    #                 question_id="q-123-1",
    #                 quiz_id="q-123",
    #             ),
    #             AnswerOption(
    #                 answer="2",
    #                 correct_answer=True,
    #                 answer_id="b",
    #                 question_id="q-123-1",
    #                 quiz_id="q-123",
    #             ),
    #         ]
    #     ),
    # )
    # db.questions.insert_question(question_1)

    # question_2 = DbQuestion(
    #     quiz_id="q-123",
    #     question_id="q-123-2",
    #     question="What is 2+2",
    #     question_number=2,
    #     question_type=QuestionType.MULTIPLE_CHOICE,
    #     points=10,
    #     seconds_to_answer=40,
    #     answers=AnswerOptions(
    #         answers=[
    #             AnswerOption(
    #                 answer="1",
    #                 correct_answer=False,
    #                 answer_id="a",
    #                 question_id="q-123-2",
    #                 quiz_id="q-123",
    #             ),
    #             AnswerOption(
    #                 answer="2",
    #                 correct_answer=False,
    #                 answer_id="b",
    #                 question_id="q-123-2",
    #                 quiz_id="q-123",
    #             ),
    #             AnswerOption(
    #                 answer="3",
    #                 correct_answer=False,
    #                 answer_id="c",
    #                 question_id="q-123-2",
    #                 quiz_id="q-123",
    #             ),
    #             AnswerOption(
    #                 answer="4",
    #                 correct_answer=True,
    #                 answer_id="d",
    #                 question_id="q-123-2",
    #                 quiz_id="q-123",
    #             ),
    #         ]
    #     ),
    # )
    # db.questions.insert_question(question_2)

    # session = DbSession(
    #     session_id="s-123",
    #     quiz_id="q-123",
    #     start_datetime=datetime.now(),
    #     room_id="r-123",
    #     moderator_id="u-123",
    # )
    # db.quiz_sessions.add_session(session)

    # db.questions.delete_question(quiz_id="q-123", question_id="q-123-1")
    # db.questions.delete_table()

    # participent_answer = UserAnswer(
    #     user_id="u-456",
    #     question_id="q-123-1",
    #     answer_id="b",
    #     timestamp=123,
    #     session_id="s-123",
    #     quiz_id="q-123",
    #     points=10,
    #     is_correct=True,
    # )
    # db.quiz_participants_answers.insert_users_answer(participent_answer)

    # db.quiz_participants_answers.delete_all_rows()
