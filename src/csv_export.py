"""CSV formatting for session response exports."""
import csv
import io
from collections.abc import Iterable, Sequence


HEADERS = (
    "session_code",
    "question_order",
    "question_type",
    "question_text",
    "answer",
    "participant_id",
    "submitted_at_utc",
    "qa_upvotes",
)
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _safe_text(value: object) -> object:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def render_csv(rows: Iterable[Sequence[object]]) -> bytes:
    """Return UTF-8 with BOM CSV bytes, with spreadsheet formulas neutralised."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADERS)
    writer.writerows(tuple(_safe_text(value) for value in row) for row in rows)
    return output.getvalue().encode("utf-8-sig")
