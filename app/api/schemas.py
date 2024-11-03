from enum import StrEnum


class WsConnectionType(StrEnum):
    MODERATOR = "moderator"
    PARTICIPANT = "participant"
    UNKNOWN = "unknown"
