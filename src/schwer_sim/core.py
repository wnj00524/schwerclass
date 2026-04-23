from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import heapq
import random


@dataclass(order=True)
class ScheduledEvent:
    tick: int
    priority: int
    event_type: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)


class EventQueue:
    def __init__(self) -> None:
        self._q: list[ScheduledEvent] = []

    def push(self, ev: ScheduledEvent) -> None:
        heapq.heappush(self._q, ev)

    def pop_due(self, tick: int) -> list[ScheduledEvent]:
        due: list[ScheduledEvent] = []
        while self._q and self._q[0].tick <= tick:
            due.append(heapq.heappop(self._q))
        return due


class DeterministicEngine:
    def __init__(self, dt_seconds: float, seed: int) -> None:
        self.dt_seconds = dt_seconds
        self.seed = seed
        self.rng = random.Random(seed)
        self.tick = 0
        self.queue = EventQueue()
        self.handlers: dict[str, Callable[[dict[str, Any]], None]] = {}

    def register_handler(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self.handlers[event_type] = handler

    def schedule(self, ticks_from_now: int, event_type: str, payload: dict[str, Any] | None = None, priority: int = 10) -> None:
        self.queue.push(
            ScheduledEvent(
                tick=self.tick + ticks_from_now,
                priority=priority,
                event_type=event_type,
                payload=payload or {},
            )
        )

    def step(self) -> list[ScheduledEvent]:
        self.tick += 1
        due = self.queue.pop_due(self.tick)
        for ev in due:
            handler = self.handlers.get(ev.event_type)
            if handler:
                handler(ev.payload)
        return due
