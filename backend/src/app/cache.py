from __future__ import annotations

import time
from collections import OrderedDict
from typing import Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, max_size: int = 128, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get_or_set(self, key: str, factory: Callable[[], T]) -> tuple[T, bool]:
        now = time.monotonic()
        entry = self._items.get(key)
        if entry and entry[0] > now:
            self._items.move_to_end(key)
            self.hits += 1
            return entry[1], True  # type: ignore[return-value]
        if entry:
            del self._items[key]
        self.misses += 1
        value = factory()
        self._items[key] = (now + self.ttl_seconds, value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)
        return value, False

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._items), "hits": self.hits, "misses": self.misses}


analytics_cache = TTLCache()
forecast_cache = TTLCache()
diagnostic_cache = TTLCache()
dashboard_cache = TTLCache()
