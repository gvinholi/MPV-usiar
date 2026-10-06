from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Pagination:
    page: int = 1
    page_size: int = 25

    def __post_init__(self):
        if type(self.page) is not int or self.page < 1:
            raise ValueError("page must be >= 1")
        if type(self.page_size) is not int or not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be 1..100")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        return (self.total_items + self.page_size - 1) // self.page_size
