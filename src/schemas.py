from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


QuestionType = Literal["multiple_choice", "word_cloud", "qa"]
ChartStyle = Literal["bar", "donut"]
MAX_TEXT_LENGTH = 300
MAX_OPTIONS = 10
MAX_OPTION_LENGTH = 100


def clean_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Question text must not be blank")
    if len(value) > MAX_TEXT_LENGTH:
        raise ValueError(f"Question text must be at most {MAX_TEXT_LENGTH} characters")
    return value


def clean_options(values: list[str]) -> list[str]:
    values = [value.strip() for value in values]
    if any(not value for value in values):
        raise ValueError("Option labels must not be blank")
    if any(len(value) > MAX_OPTION_LENGTH for value in values):
        raise ValueError(f"Option labels must be at most {MAX_OPTION_LENGTH} characters")
    if len(values) > MAX_OPTIONS:
        raise ValueError(f"Questions can have at most {MAX_OPTIONS} options")
    if len({value.casefold() for value in values}) != len(values):
        raise ValueError("Option labels must be different from each other")
    return values


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
    image_url: str | None = None


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
        return clean_text(value)

    @field_validator("options")
    @classmethod
    def require_option_labels(cls, values: list[str]) -> list[str]:
        return clean_options(values)

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
    text: str | None = None
    options: list[str] | None = None

    @model_validator(mode="after")
    def require_values_for_fields_sent(self) -> "QuestionUpdate":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Question fields must not be null")
        if self.text is not None:
            self.text = clean_text(self.text)
        if self.options is not None:
            self.options = clean_options(self.options)
            if len(self.options) < 2:
                raise ValueError("Multiple-choice questions need at least two options")
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
    image_url: str | None = None


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


class QaItem(BaseModel):
    id: int
    text: str
    upvotes: int
    upvoted_by_me: bool


class QaList(BaseModel):
    items: list[QaItem]


class QaCreate(BaseModel):
    text: str = Field(max_length=280)

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question text must not be blank")
        return value


class ImageUpload(BaseModel):
    data_url: str
