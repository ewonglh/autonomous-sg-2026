from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SessionCreated(BaseModel):
    code: str
    host_key: str


class SessionCreate(BaseModel):
    title: str = Field(default="Untitled session", max_length=120)


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


class QuestionListItem(BaseModel):
    id: int
    position: int
    type: Literal["multiple_choice", "word_cloud"]
    text: str
    options: list[Option]
    is_open: bool
    results_visible: bool
    response_count: int


class QuestionList(BaseModel):
    active_question_id: int | None
    questions: list[QuestionListItem]


class QuestionCreate(BaseModel):
    type: Literal["multiple_choice", "word_cloud"]
    text: str
    options: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def require_question_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question text must not be blank")
        return value

    @field_validator("options")
    @classmethod
    def require_option_labels(cls, values: list[str]) -> list[str]:
        values = [value.strip() for value in values]
        if any(not value for value in values):
            raise ValueError("Option labels must not be blank")
        return values

    @model_validator(mode="after")
    def validate_options_for_type(self) -> "QuestionCreate":
        if self.type == "multiple_choice" and len(self.options) < 2:
            raise ValueError("Multiple-choice questions need at least two options")
        if self.type == "word_cloud" and self.options:
            raise ValueError("Word-cloud questions do not accept choice options")
        return self


class QuestionCreated(BaseModel):
    id: int


class QuestionUpdate(BaseModel):
    is_open: bool | None = None
    results_visible: bool | None = None

    @model_validator(mode="after")
    def require_question_flag(self) -> "QuestionUpdate":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Question flags must be booleans")
        return self


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
