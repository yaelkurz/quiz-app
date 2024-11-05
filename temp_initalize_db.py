from datetime import datetime
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
