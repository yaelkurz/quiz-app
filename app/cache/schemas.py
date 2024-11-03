from enum import StrEnum
import json
from pydantic import BaseModel, field_validator
from app.db.schemas import DbQuestion, DbSession
from typing import Optional


class QuizState(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
