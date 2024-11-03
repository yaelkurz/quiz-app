from enum import StrEnum
import json
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional, List


class UserRole(StrEnum):
    MODERATOR = "moderator"
    PARTICIPANT = "participant"


class QuestionType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"

    @classmethod
    def from_str(cls, question_type: str):
        return cls(question_type)


class DbUser(BaseModel):
    user_id: str
    username: str
    email: str
    create_date: datetime

    @classmethod
    def get_from_db(
        cls, user_id: str, username: str, email: str, create_date: datetime
    ):
        return cls(
            user_id=user_id, username=username, email=email, create_date=create_date
        )


class DbParticipent(BaseModel):
    quiz_id: str
    user_id: str
    session_id: str
    score: Optional[int] = None
    joined_at: datetime
    left_at: Optional[datetime] = None


class UserPermission(BaseModel):
    quiz_id: str
    user_id: str
    permission: UserRole

    @classmethod
    def get_from_db(cls, quiz_id: str, user_id: str, permission: str):
        permission = UserRole(permission)
        return cls(quiz_id=quiz_id, user_id=user_id, permission=permission)

    @field_validator("permission")
    def validate_permission(cls, v):
        return v.value


class DbSession(BaseModel):
    quiz_id: str
    room_id: str
    session_id: str
    moderator_id: str
    start_datetime: datetime
    end_datetime: Optional[datetime] = None

    @classmethod
    def get_from_db(
        cls,
        quiz_id: str,
        room_id: str,
        session_id: str,
        moderator_id: str,
        start_datetime: datetime,
        end_datetime: Optional[datetime] = None,
    ):
        return cls(
            quiz_id=quiz_id,
            room_id=room_id,
            session_id=session_id,
            moderator_id=moderator_id,
            start_datetime=start_datetime,
            end_date=end_datetime,
        )


class AnswerOption(BaseModel):
    """
    Represents a single answer option for a question.
    """

    answer: str = Field(..., description="The text of the answer option")
    correct_answer: bool = Field(
        default=False, description="Whether this option is the correct answer"
    )

    def model_dump_json(self):
        return {"answer": self.answer, "correct_answer": self.correct_answer}


class AnswerOptions(BaseModel):
    answers: List[AnswerOption]

    def model_dump_json(self):
        return [answer.model_dump_json() for answer in self.answers]

    @classmethod
    def from_str(cls, answers: str):
        return cls(answers=json.loads(answers))


class DbQuestion(BaseModel):
    question_id: str
    question: str
    question_number: int
    points: int
    answers: AnswerOptions
    question_type: QuestionType

    @model_validator(mode="after")
    def validate_answers(cls, v):
        if v == QuestionType.MULTIPLE_CHOICE:
            if len(cls.answers) < 2:
                raise ValueError(
                    "Multiple choice questions must have at least 2 answer options"
                )
            if sum([1 for option in cls.answers if option.correct_answer]) != 1:
                raise ValueError(
                    "Multiple choice questions must have exactly 1 correct answer"
                )
        return v

    @field_validator("points")
    def validate_points(cls, v):
        if v < 0:
            raise ValueError("Points must be greater than 0")
        return v

    @field_validator("question_number")
    def validate_question_number(cls, v):
        if v < 0:
            raise ValueError("Question number must be greater than 0")
        return v

    @field_validator("question_type")
    def validate_question_type(cls, v):
        return v.value

    def model_dump_json(self):
        return {
            "question_id": self.question_id,
            "question": self.question,
            "question_number": self.question_number,
            "points": self.points,
            "answers": self.answers.model_dump_json(),
            "question_type": self.question_type,
        }

    def client_model_dump_json(self):
        return {
            "question_id": self.question_id,
            "question": self.question,
            "question_number": self.question_number,
            "points": self.points,
            "question_type": self.question_type,
        }

    @classmethod
    def get_from_db(
        cls,
        question_id: str,
        question: str,
        question_number: int,
        points: int,
        answers: str,
        question_type: str,
    ):
        return cls(
            question_id=question_id,
            question=question,
            question_number=question_number,
            points=points,
            answers=AnswerOptions.from_str(answers),
            question_type=QuestionType.from_str(question_type),
        )

    @classmethod
    def get_from_cache(cls, question_dict: dict):
        return cls(
            question_id=question_dict.get("question_id"),
            question=question_dict.get("question"),
            question_number=question_dict.get("question_number"),
            points=question_dict.get("points"),
            answers=AnswerOptions(answers=question_dict.get("answers")),
            question_type=QuestionType(question_dict.get("question_type")),
        )