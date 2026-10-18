"""Ordered registry. A new model is a register() call, not another branch in the caller."""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Highest priority wins. Re-registering the same id replaces the previous entry."""

    def __init__(self) -> None:
        self._items: list[tuple[int, str, T]] = []

    def register(self, item_id: str, item: T, *, priority: int = 0) -> T:
        key = str(item_id)
        self._items = [row for row in self._items if row[1] != key]
        self._items.append((priority, key, item))
        self._items.sort(key=lambda row: -row[0])
        return item

    def get(self, item_id: str) -> T | None:
        key = str(item_id)
        for _, iid, item in self._items:
            if iid == key:
                return item
        return None

    def ids(self) -> list[str]:
        return [iid for _, iid, _ in self._items]

    def all(self) -> list[T]:
        return [item for _, _, item in self._items]
