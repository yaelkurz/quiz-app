import json
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import IntEnum
from typing import Optional
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class ErrorBase(Exception):
    """Base error model with structured information."""

    def __init__(self, status_code: int, error_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message

        def __str__(self):
            return f"status_code:{self.error_code} error_code:{self.error_code} message:{self.message}"

    def to_http_exception(self) -> HTTPException:
        """Convert the error instance to a FastAPI HTTPException."""
        logger.error(f"Http Exception Error {self.error_code}: {self.message}")
        return HTTPException(status_code=self.status_code, detail=self.details)

    def to_websocket_close(self) -> dict:
        """Generate WebSocket close details with a code and reason."""
        logger.error(f"Websocket Close Error {self.error_code}: {self.message}")
        return {"code": self.error_code, "reason": self.details}


class Errors:
    MISSING_USER_ID_HEADER = ErrorBase(
        status_code=400, error_code=4001, message="user_id header is missing"
    )
    SESSION_NOT_FOUND = ErrorBase(
        status_code=404, error_code=4040, message="Session not found"
    )
    USER_FORBIDDEN = ErrorBase(
        status_code=403, error_code=4030, message="User is not authorized"
    )
    INVALID_MESSAGE_TYPE = ErrorBase(
        status_code=400,
        error_code=4002,
        message="Invalid message type",
    )
    SESSION_CLOSED_FOR_NEW_PARTICIPANTS = ErrorBase(
        status_code=400,
        error_code=4003,
        message="Session is closed for new participants",
    )
    ServerError = ErrorBase(
        status_code=500, error_code=5000, message="Internal Server Error"
    )


class UserLeftException(Exception):
    def __init__(self):
        super().__init__()
        self.message = "User Left"

        def __str__(self):
            return "User Left"


class QuizEndedException(Exception):
    def __init__(self):
        super().__init__()
        self.message = "Quiz Ended"

        def __str__(self):
            return "Quiz Ended"
