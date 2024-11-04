from enum import StrEnum


class QuizState(StrEnum):
    WAITING_TO_START = "waiting"
    ACTIVE = "active"
    QUESTION_TIMEDOUT = "timedout"
    ENDED = "ended"
