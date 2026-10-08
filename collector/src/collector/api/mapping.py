"""Application DTO to HTTP schema boundary."""
from dataclasses import asdict
from decimal import Decimal
from typing import TypeVar
from pydantic import BaseModel
from .schemas import PageResponse, PaginationResponse, ReviewCreatedResponse

S = TypeVar("S", bound=BaseModel)

def to_response(dto, schema: type[S]) -> S:
    data = asdict(dto)
    _decimal_strings(data)
    return schema.model_validate(data)

def to_page(page, schema: type[S]) -> PageResponse[S]:
    return PageResponse[schema](
        items=[to_response(item, schema) for item in page.items],
        pagination=PaginationResponse(page=page.page, page_size=page.page_size, total_items=page.total_items, total_pages=page.total_pages),
    )

def to_review_created(review) -> ReviewCreatedResponse:
    return ReviewCreatedResponse(
        review_id=review.id,
        process_id=review.process_id,
        profile_id=review.profile_id,
        operational_resolution_id=review.operational_resolution_id,
        decision=review.decision,
        reason=review.reason_code,
        comment=review.comment,
        reviewer_id=review.reviewer.reviewer_id,
        reviewer_display_name=review.reviewer.display_name,
        was_stale_at_decision=review.was_stale_at_decision,
        latest_resolution_id_at_decision=review.latest_resolution_id_at_decision,
        decided_at=review.decided_at,
    )

def _decimal_strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, Decimal): value[key] = format(item, "f")
            else: _decimal_strings(item)
    elif isinstance(value, list):
        for item in value: _decimal_strings(item)
