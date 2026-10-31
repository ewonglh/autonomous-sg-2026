"""Room codes are stored in uppercase but accepted in any letter case."""
from typing import Annotated

from fastapi import Path
from pydantic import AfterValidator


def normalize_code(value: str) -> str:
    return value.strip().upper()


RoomCode = Annotated[str, Path(), AfterValidator(normalize_code)]
