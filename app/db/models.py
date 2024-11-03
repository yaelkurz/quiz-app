# base_repository.py
import json
import os
import sqlite3
import logging
from typing import Dict, List, Optional
from app.db.schemas import DbUser, UserPermission, DbParticipent, DbSession, DbQuestion

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "app/db/quiz.db")


class BaseRepository:

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.cursor = self.connection.cursor()

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
                answers TEXT,
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
                INSERT INTO questions (question_id, quiz_id, question, question_number, question_type, points, answers)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(question_id,quiz_id)
                DO UPDATE SET
                    question = excluded.question,
                    question_number = excluded.question_number,
                    question_type = excluded.question_type,
                    points = excluded.points,
                    answers = excluded.answers
                """,
                (
                    question.question_id,
                    question.quiz_id,
                    question.question,
                    question.question_number,
                    question.question_type,
                    question.points,
                    json.dumps(question.answers.model_dump_json()),
                ),
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting question: {e}")
            return False

    def get_question_by_index(self, quiz_id: str, question_index: int) -> DbQuestion:
        """
        Gets the first question for a quiz.
        """
        try:
            self.cursor.execute(
                """
                SELECT question_id, question, question_number, question_type, points, answers
                FROM questions
                WHERE quiz_id = ?
                AND question_number = ?
                ORDER BY question_number
                LIMIT 1
                """,
                (quiz_id, question_index),
            )
            row = self.cursor.fetchone()
            return (
                DbQuestion.get_from_db(
                    question_id=row[0],
                    question=row[1],
                    question_number=row[2],
                    question_type=row[3],
                    points=row[4],
                    answers=row[5],
                )
                if row
                else None
            )
        except sqlite3.Error as e:
            logger.error(f"Error getting first question: {e}")
            return None


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
                FOREIGN KEY (user_id) REFERENCES users(user_id)
                FOREIGN KEY (session_id) REFERENCES quiz_sessions(session_id)
            )
            """
        )
        self.connection.commit()

    def add_participant(
        self,
        participent: DbParticipent,
    ) -> bool:
        """
        Adds or updates a perticipent to a quiz.
        """
        try:
            self.cursor.execute(
                """
                INSERT INTO quiz_participents (quiz_id, session_id, user_id, score, joined_at, left_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(quiz_id, session_id, user_id)
                DO UPDATE SET score = excluded.score, left_at = excluded.left_at
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
        """Creates a quiz permissions table if it doesn't exist."""
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
        """
        Adds or updates a user's permission for a quiz.

        Args:
            user_permission: UserPermission object containing the permission data

        Returns:
            bool: True if operation was successful, False otherwise
        """
        try:
            self.cursor.execute(
                """
                INSERT INTO quiz_permissions (quiz_id, user_id, permission)
                VALUES (?, ?, ?)
                ON CONFLICT(quiz_id, user_id)
                DO UPDATE SET
                    permission = excluded.permission
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
        """Gets a user's permission for a specific quiz."""
        try:
            self.cursor.execute(
                """
                SELECT permission
                FROM quiz_permissions
                WHERE quiz_id = ? AND user_id = ?
                """,
                (quiz_id, user_id),
            )
            row = self.cursor.fetchone()
            return UserPermission.get_from_db(quiz_id, user_id, row[0]) if row else None
        except sqlite3.Error as e:
            logger.error(f"Error getting user permission: {e}")
            return None


class UsersRepository(BaseRepository):
    def create_table(self):
        """Creates a users table if it doesn't exist."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT,
                create_date DATETIME
            )
            """
        )
        self.connection.commit()

    def add_user(self, user: DbUser) -> bool:
        """Adds or Updates A user.

        Args:
        - user: DbUser: The user to add to the table

        Returns:
        - bool: True if the user was added, False otherwise
        """
        try:
            self.cursor.execute(
                """
                INSERT INTO users (user_id, username, email, create_date)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET username = excluded.username, email = excluded.email
                """,
                (user.user_id, user.username, user.email, user.create_date),
            )
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error adding user: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[DbUser]:
        """Gets a user by their user_id."""
        try:
            self.cursor.execute(
                """
                SELECT user_id, username, email, create_date
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = self.cursor.fetchone()
            return (
                DbUser.get_from_db(
                    user_id=row[0], username=row[1], email=row[2], create_date=row[3]
                )
                if row
                else None
            )
        except sqlite3.Error as e:
            logger.error(f"Error getting user: {e}")
            return None


class QuizSessionsRepository(BaseRepository):
    def create_table(self):
        """Creates a quiz sessions table if it doesn't exist."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                session_id TEXT PRIMARY KEY,
                quiz_id TEXT,
                room_id TEXT,
                start_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_datetime TIMESTAMP,
                moderator_id TEXT,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
                FOREIGN KEY (moderator_id) REFERENCES users(user_id)
            )
            """
        )
        self.connection.commit()

    def add_session(self, session: DbSession) -> bool:
        """Adds or updates a session to the quiz_sessions table."""
        try:
            self.cursor.execute(
                """
                INSERT INTO quiz_sessions (session_id, quiz_id, room_id, start_datetime, end_datetime, moderator_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET end_datetime = excluded.end_datetime
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
        except sqlite3.Error as e:
            logger.error(f"Error adding session: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[DbSession]:
        """Gets a session by its session_id."""
        try:
            self.cursor.execute(
                """
                SELECT session_id, quiz_id, room_id, start_datetime, end_datetime, moderator_id
                FROM quiz_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            )
            row = self.cursor.fetchone()
            return (
                DbSession.get_from_db(
                    session_id=row[0],
                    quiz_id=row[1],
                    room_id=row[2],
                    start_datetime=row[3],
                    end_datetime=row[4],
                    moderator_id=row[5],
                )
                if row
                else None
            )

        except sqlite3.Error as e:
            logger.error(f"Error getting session: {e}")
            return None


class DbManager:
    def __init__(self):
        self.connection = sqlite3.connect(DB_PATH)

        self.users = UsersRepository(self.connection)
        self.quiz_permissions = QuizPermissionsRepository(self.connection)
        self.questions = QuestionsRepository(self.connection)

        self.quiz_participents = QuizParticipentsRepository(self.connection)
        self.quiz_sessions = QuizSessionsRepository(self.connection)

    def create_tables(self):
        self.users.create_table()
        self.quiz_permissions.create_table()
        self.questions.create_table()

        self.quiz_participents.create_table()
        self.quiz_sessions.create_table()

    def close(self):
        self.users.close()
        self.quiz_permissions.close()
        self.questions.close()

        self.quiz_participents.close()
        self.quiz_sessions.close()
