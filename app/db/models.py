import json
import os
import logging
from typing import List, Optional
import psycopg2
from psycopg2.extras import DictCursor
from app.db.schemas import (
    DbUser,
    UserPermission,
    DbParticipent,
    DbSession,
    DbQuestion,
    DbQuiz,
    UserAnswer,
)
from app.api.errors import Errors

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DB_URL")


class BaseRepository:
    def __init__(self, connection: psycopg2.extensions.connection):
        self.connection = connection
        self.cursor = self.connection.cursor(cursor_factory=DictCursor)

    def close(self):
        if self.connection:
            self.connection.close()


class QuestionsRepository(BaseRepository):
    def create_table(self):
        """Create the questions table if it doesn't exist."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                question_id TEXT,
                quiz_id TEXT NOT NULL,
                question TEXT NOT NULL,
                question_number INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                points INTEGER NOT NULL,
                answers JSONB,
                seconds_to_answer INTEGER NOT NULL,
                PRIMARY KEY (question_id, quiz_id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
            )
            """
        )
        self.connection.commit()

    def insert_question(self, question: DbQuestion) -> bool:
        """
        Adds or updates a question to the questions table.
        """
        try:
            self.cursor.execute(
                """
                INSERT INTO questions (
                    question_id, quiz_id, question, question_number,
                    question_type, points, answers, seconds_to_answer
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (question_id, quiz_id) DO UPDATE SET
                    question = EXCLUDED.question,
                    question_number = EXCLUDED.question_number,
                    question_type = EXCLUDED.question_type,
                    points = EXCLUDED.points,
                    answers = EXCLUDED.answers,
                    seconds_to_answer = EXCLUDED.seconds_to_answer
                """,
                (
                    question.question_id,
                    question.quiz_id,
                    question.question,
                    question.question_number,
                    question.question_type,
                    question.points,
                    json.dumps(question.answers.model_dump_json()),
                    question.seconds_to_answer,
                ),
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting question: {e}")
            return False

    def delete_question(self, question_id: str, quiz_id: str) -> bool:
        """
        Deletes a question from the questions table.
        """
        try:
            self.cursor.execute(
                """
                DELETE FROM questions
                WHERE question_id = %s AND quiz_id = %s
                """,
                (question_id, quiz_id),
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting question: {e}")
            return False

    def get_quiz_questions(self, quiz_id: str) -> List[DbQuestion]:
        """
        Gets all questions for a quiz.
        """
        try:
            self.cursor.execute(
                """
                SELECT question_id, question, question_number, question_type,
                       points, answers, seconds_to_answer
                FROM questions
                WHERE quiz_id = %s
                ORDER BY question_number
                """,
                (quiz_id,),
            )
            rows = self.cursor.fetchall()
            return [
                DbQuestion.get_from_db(
                    question_id=row["question_id"],
                    question=row["question"],
                    question_number=row["question_number"],
                    question_type=row["question_type"],
                    points=row["points"],
                    answers=row["answers"],
                    seconds_to_answer=row["seconds_to_answer"],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting quiz questions: {e}")
            raise Errors.ServerError

    def delete_table(self) -> bool:
        """
        Deletes the questions table.
        """
        try:
            self.cursor.execute(
                """
                DROP TABLE IF EXISTS questions
                """
            )
            self.connection.commit()

            return True
        except Exception as e:
            logger.error(f"Error deleting table: {e}")
            return False


class QuizParticipentsRepository(BaseRepository):
    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_participents (
                quiz_id TEXT,
                session_id TEXT,
                user_id TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                left_at TIMESTAMP,
                score INTEGER DEFAULT 0,
                PRIMARY KEY (quiz_id, session_id, user_id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (session_id) REFERENCES quiz_sessions(session_id)
            )
            """
        )
        self.connection.commit()

    def add_participant(self, participent: DbParticipent) -> bool:
        try:
            self.cursor.execute(
                """
                INSERT INTO quiz_participents (
                    quiz_id, session_id, user_id, score, joined_at, left_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (quiz_id, session_id, user_id) DO UPDATE SET
                    score = EXCLUDED.score,
                    left_at = EXCLUDED.left_at
                """,
                (
                    participent.quiz_id,
                    participent.session_id,
                    participent.user_id,
                    participent.score,
                    participent.joined_at,
                    participent.left_at,
                ),
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding participent: {e}")
            return False


class QuizPermissionsRepository(BaseRepository):
    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_permissions (
                quiz_id TEXT,
                user_id TEXT,
                permission TEXT NOT NULL,
                PRIMARY KEY (quiz_id, user_id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """
        )
        self.connection.commit()

    def add_permission(self, user_permission: UserPermission) -> bool:
        try:
            self.cursor.execute(
                """
                INSERT INTO quiz_permissions (quiz_id, user_id, permission)
                VALUES (%s, %s, %s)
                ON CONFLICT (quiz_id, user_id) DO UPDATE SET
                    permission = EXCLUDED.permission
                """,
                (
                    user_permission.quiz_id,
                    user_permission.user_id,
                    user_permission.permission,
                ),
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding quiz permission: {e}")
            return False

    def get_user_permission(
        self, quiz_id: str, user_id: str
    ) -> Optional[UserPermission]:
        try:
            self.cursor.execute(
                """
                SELECT permission
                FROM quiz_permissions
                WHERE quiz_id = %s AND user_id = %s
                """,
                (quiz_id, user_id),
            )
            row = self.cursor.fetchone()
            return (
                UserPermission.get_from_db(quiz_id, user_id, row["permission"])
                if row
                else None
            )
        except psycopg2.Error as e:
            logger.error(f"Error getting user permission: {e}")
            return None


class UsersRepository(BaseRepository):
    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT,
                create_date TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def add_user(self, user: DbUser) -> bool:
        try:
            self.cursor.execute(
                """
                INSERT INTO users (user_id, username, email, create_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    email = EXCLUDED.email
                """,
                (user.user_id, user.username, user.email, user.create_date),
            )
            self.connection.commit()
            return True
        except psycopg2.Error as e:
            logger.error(f"Error adding user: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[DbUser]:
        try:
            self.cursor.execute(
                """
                SELECT user_id, username, email, create_date
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = self.cursor.fetchone()
            return (
                DbUser.get_from_db(
                    user_id=row["user_id"],
                    username=row["username"],
                    email=row["email"],
                    create_date=row["create_date"],
                )
                if row
                else None
            )
        except psycopg2.Error as e:
            logger.error(f"Error getting user: {e}")
            return None


class QuizSessionsRepository(BaseRepository):
    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                session_id TEXT PRIMARY KEY,
                quiz_id TEXT,
                room_id TEXT,
                start_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_datetime TIMESTAMP,
                moderator_id TEXT,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id),
                FOREIGN KEY (moderator_id) REFERENCES users(user_id)
            )
            """
        )
        self.connection.commit()

    def add_session(self, session: DbSession) -> bool:
        try:
            self.cursor.execute(
                """
                INSERT INTO quiz_sessions (
                    session_id, quiz_id, room_id, start_datetime,
                    end_datetime, moderator_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    end_datetime = EXCLUDED.end_datetime
                """,
                (
                    session.session_id,
                    session.quiz_id,
                    session.room_id,
                    session.start_datetime,
                    session.end_datetime,
                    session.moderator_id,
                ),
            )
            self.connection.commit()
            return True
        except psycopg2.Error as e:
            logger.error(f"Error adding session: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[DbSession]:
        try:
            self.cursor.execute(
                """
                SELECT session_id, quiz_id, room_id, start_datetime,
                       end_datetime, moderator_id
                FROM quiz_sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = self.cursor.fetchone()
            return (
                DbSession.get_from_db(
                    session_id=row["session_id"],
                    quiz_id=row["quiz_id"],
                    room_id=row["room_id"],
                    start_datetime=row["start_datetime"],
                    end_datetime=row["end_datetime"],
                    moderator_id=row["moderator_id"],
                )
                if row
                else None
            )
        except psycopg2.Error as e:
            logger.error(f"Error getting session: {e}")
            return None


class QuizDataRepository(BaseRepository):
    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id TEXT PRIMARY KEY,
                quiz_name TEXT NOT NULL,
                quiz_description TEXT
            )
            """
        )
        self.connection.commit()

    def add_quiz(self, quiz: DbQuiz) -> bool:
        try:
            self.cursor.execute(
                """
                INSERT INTO quizzes (quiz_id, quiz_name, quiz_description)
                VALUES (%s, %s, %s)
                ON CONFLICT (quiz_id) DO UPDATE SET
                    quiz_name = EXCLUDED.quiz_name,
                    quiz_description = EXCLUDED.quiz_description
                """,
                (quiz.quiz_id, quiz.quiz_name, quiz.quiz_description),
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding quiz: {e}")
            return None


class QuizParticipantsAnswersRepository(BaseRepository):
    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_participants_answers (
                session_id TEXT,
                user_id TEXT,
                question_id TEXT,
                answer_id TEXT,
                points INTEGER,
                is_correct BOOLEAN,
                timestamp INTEGER,
                quiz_id TEXT,
                PRIMARY KEY (session_id, user_id, question_id),
                FOREIGN KEY (session_id) REFERENCES quiz_sessions(session_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (question_id, quiz_id) REFERENCES questions(question_id, quiz_id)  -- Fixed foreign key reference
            )
            """
        )
        self.connection.commit()

    def insert_users_answer(self, user_answer: UserAnswer) -> None:
        try:
            self.cursor.execute(
                """
                INSERT INTO quiz_participants_answers (
                    session_id,quiz_id, user_id, question_id, answer_id, points, is_correct, timestamp
                )
                VALUES (%s, %s,%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_answer.session_id,
                    user_answer.quiz_id,
                    user_answer.user_id,
                    user_answer.question_id,
                    user_answer.answer_id,
                    user_answer.points,
                    user_answer.is_correct,
                    user_answer.timestamp,
                ),
            )
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error inserting user answer: {e}")

    def delete_all_rows(self):
        try:
            self.cursor.execute(
                """
                DELETE FROM quiz_participants_answers
                """
            )
            self.connection.commit()
        except Exception as e:
            logger.error(f"Error deleting all rows: {e}")


class DbManager:
    def __init__(self):
        self.connection = psycopg2.connect(DB_URL)
        self.quizzes = QuizDataRepository(self.connection)
        self.users = UsersRepository(self.connection)
        self.quiz_permissions = QuizPermissionsRepository(self.connection)
        self.questions = QuestionsRepository(self.connection)
        self.quiz_participents = QuizParticipentsRepository(self.connection)
        self.quiz_sessions = QuizSessionsRepository(self.connection)
        self.quiz_participants_answers = QuizParticipantsAnswersRepository(
            self.connection
        )

    def create_tables(self):
        self.users.create_table()
        self.quizzes.create_table()
        self.quiz_sessions.create_table()
        self.quiz_permissions.create_table()
        self.questions.create_table()
        self.quiz_participents.create_table()
        self.quiz_participants_answers.create_table()

    def close(self):
        self.users.close()
        self.quiz_permissions.close()
        self.questions.close()
        self.quiz_participents.close()
        self.quiz_sessions.close()
        self.quizzes.close()
        self.quiz_participants_answers.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
