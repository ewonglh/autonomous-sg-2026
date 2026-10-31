from typing import Literal

from pydantic import BaseModel, Field


class SessionCreated(BaseModel):
    code: str
    host_key: str


class Option(BaseModel):
    id: int
    label: str


class ActiveQuestion(BaseModel):
    id: int
    type: Literal["multiple_choice", "word_cloud"]
    text: str
    options: list[Option]
    is_open: bool
    results_visible: bool


class SessionState(BaseModel):
    title: str
    active_question: ActiveQuestion | None


class QuestionCreate(BaseModel):
    type: Literal["multiple_choice", "word_cloud"]
    text: str
    options: list[str] = Field(default_factory=list)


class QuestionCreated(BaseModel):
    id: int


class QuestionUpdate(BaseModel):
    is_open: bool | None = None
    results_visible: bool | None = None


class ActiveSet(BaseModel):
    question_id: int


class ResponseCreate(BaseModel):
    option_id: int | None = None
    text: str | None = None


class Ok(BaseModel):
    ok: bool = True


class OptionCount(BaseModel):
    option_id: int
    label: str
    count: int


class WordCount(BaseModel):
    word: str
    count: int


class QuestionResults(BaseModel):
    question_id: int
    type: Literal["multiple_choice", "word_cloud"]
    options: list[OptionCount] | None = None
    words: list[WordCount] | None = None


class Results(BaseModel):
    results: list[QuestionResults]
