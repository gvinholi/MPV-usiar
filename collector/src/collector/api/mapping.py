"""Application DTO to HTTP schema boundary."""
from dataclasses import asdict
from decimal import Decimal
from typing import TypeVar
from pydantic import BaseModel
from .schemas import PageResponse, PaginationResponse

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

def _decimal_strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, Decimal): value[key] = format(item, "f")
            else: _decimal_strings(item)
    elif isinstance(value, list):
        for item in value: _decimal_strings(item)
