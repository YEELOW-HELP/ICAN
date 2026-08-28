"""Deterministic structured-answer validation (Matching V1 M1). Pure
functions, no DB access, no AI -- every rule here is a direct consequence
of an `AssessmentItem.response_type` and (for choice items) its declared
`AssessmentItemOption` set."""

from __future__ import annotations

from app.db.models_basic_assessment import AssessmentItem, AssessmentItemOption, ResponseType
from app.services.exceptions import InvalidResponseError

LIKERT_5_MIN = 1
LIKERT_5_MAX = 5


def validate_response(
    item: AssessmentItem,
    *,
    numeric_value: int | None = None,
    boolean_value: bool | None = None,
    selected_option_keys: list[str] | None = None,
    options: list[AssessmentItemOption] | None = None,
) -> None:
    """Raises `InvalidResponseError` if the payload does not match
    `item.response_type`. Never coerces or silently drops an unexpected
    field -- an answer either matches its item's declared shape exactly,
    or it is rejected."""

    options = options or []

    if item.response_type == ResponseType.LIKERT_5:
        if boolean_value is not None or selected_option_keys:
            raise InvalidResponseError(f"item {item.item_key}: LIKERT_5 accepts only numeric_value")
        if numeric_value is None or not (LIKERT_5_MIN <= numeric_value <= LIKERT_5_MAX):
            raise InvalidResponseError(
                f"item {item.item_key}: LIKERT_5 requires an integer in [{LIKERT_5_MIN}, {LIKERT_5_MAX}]"
            )

    elif item.response_type == ResponseType.NUMERIC:
        if boolean_value is not None or selected_option_keys:
            raise InvalidResponseError(f"item {item.item_key}: NUMERIC accepts only numeric_value")
        if numeric_value is None:
            raise InvalidResponseError(f"item {item.item_key}: NUMERIC requires numeric_value")

    elif item.response_type == ResponseType.BOOLEAN:
        if numeric_value is not None or selected_option_keys:
            raise InvalidResponseError(f"item {item.item_key}: BOOLEAN accepts only boolean_value")
        if boolean_value is None:
            raise InvalidResponseError(f"item {item.item_key}: BOOLEAN requires boolean_value")

    elif item.response_type == ResponseType.SINGLE_CHOICE:
        if numeric_value is not None or boolean_value is not None:
            raise InvalidResponseError(f"item {item.item_key}: SINGLE_CHOICE accepts only selected_option_keys")
        if not selected_option_keys or len(selected_option_keys) != 1:
            raise InvalidResponseError(f"item {item.item_key}: SINGLE_CHOICE requires exactly one selected option")
        _assert_options_valid(item, selected_option_keys, options)

    elif item.response_type == ResponseType.MULTI_CHOICE:
        if numeric_value is not None or boolean_value is not None:
            raise InvalidResponseError(f"item {item.item_key}: MULTI_CHOICE accepts only selected_option_keys")
        if not selected_option_keys:
            raise InvalidResponseError(f"item {item.item_key}: MULTI_CHOICE requires at least one selected option")
        _assert_options_valid(item, selected_option_keys, options)

    else:  # pragma: no cover -- exhaustive over ResponseType
        raise InvalidResponseError(f"item {item.item_key}: unknown response_type {item.response_type!r}")


def _assert_options_valid(
    item: AssessmentItem, selected_option_keys: list[str], options: list[AssessmentItemOption]
) -> None:
    valid_keys = {opt.option_key for opt in options}
    invalid = set(selected_option_keys) - valid_keys
    if invalid:
        raise InvalidResponseError(f"item {item.item_key}: unknown option key(s) {sorted(invalid)}")
    if len(set(selected_option_keys)) != len(selected_option_keys):
        raise InvalidResponseError(f"item {item.item_key}: duplicate option keys in selection")
