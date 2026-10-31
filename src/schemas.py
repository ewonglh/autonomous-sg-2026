from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


QuestionType = Literal["multiple_choice", "word_cloud", "qa"]
ChartStyle = Literal["bar", "donut"]


class SessionCreated(BaseModel):
    code: str
    host_key: str


class SessionCreate(BaseModel):
    title: str = Field(default="Untitled session", max_length=120)


class Option(BaseModel):
    id: int
    label: str


class QuestionListItem(BaseModel):
    id: int
    position: int
    type: QuestionType
    text: str
    options: list[Option]
    is_open: bool
    results_visible: bool
    response_count: int
    chart: ChartStyle | None = None


class QuestionList(BaseModel):
    active_question_id: int | None
    questions: list[QuestionListItem]


class QuestionCreate(BaseModel):
    type: QuestionType
    text: str
    options: list[str] = Field(default_factory=list)
    chart: ChartStyle | None = None

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
        if self.type != "multiple_choice" and self.options:
            raise ValueError("Only multiple-choice questions accept choice options")
        if self.type != "multiple_choice" and self.chart is not None:
            raise ValueError("Only multiple-choice questions have a chart style")
        return self


class QuestionCreated(BaseModel):
    id: int


class QuestionUpdate(BaseModel):
    is_open: bool | None = None
    results_visible: bool | None = None
    chart: ChartStyle | None = None

    @model_validator(mode="after")
    def require_question_flag(self) -> "QuestionUpdate":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Question changes must not be null")
        return self


class QuestionOrder(BaseModel):
    question_ids: list[int]


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


class MultipleChoiceResults(BaseModel):
    options: list[OptionCount]


class WordCloudResults(BaseModel):
    words: list[WordCount]


PublicResults = MultipleChoiceResults | WordCloudResults


class ActiveQuestion(BaseModel):
    id: int
    type: QuestionType
    text: str
    options: list[Option]
    is_open: bool
    results_visible: bool
    response_count: int
    results: PublicResults | None
    chart: ChartStyle | None = None


class SessionState(BaseModel):
    title: str
    active_question: ActiveQuestion | None


class QuestionResults(BaseModel):
    question_id: int
    type: QuestionType
    options: list[OptionCount] | None = None
    words: list[WordCount] | None = None


class Results(BaseModel):
    results: list[QuestionResults]
