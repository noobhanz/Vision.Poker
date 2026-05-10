"""Asyncio queue bridging capture → engine → overlay."""

import asyncio
from dataclasses import dataclass
from typing import Optional

import numpy as np

from capture.window_finder import WindowRect
from engine.models import GameState, Metrics


@dataclass
class FrameData:
    """Data packet for a captured frame."""

    frame: np.ndarray
    window_rect: WindowRect
    timestamp: float


@dataclass
class StateData:
    """Data packet for parsed game state."""

    state: GameState
    window_rect: WindowRect
    timestamp: float


class MetricsQueue:
    """
    Thread-safe async queue for passing metrics between pipeline stages.
    """

    def __init__(self, maxsize: int = 10):
        """
        Initialize the metrics queue.

        Args:
            maxsize: Maximum queue size (older items dropped when full)
        """
        self._queue: asyncio.Queue[Metrics] = asyncio.Queue(maxsize=maxsize)
        self._latest: Optional[Metrics] = None

    async def put(self, metrics: Metrics) -> None:
        """
        Put metrics into the queue.
        If queue is full, drops oldest item.

        Args:
            metrics: Metrics to enqueue
        """
        self._latest = metrics

        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        await self._queue.put(metrics)

    async def get(self, timeout: Optional[float] = None) -> Optional[Metrics]:
        """
        Get metrics from the queue.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Metrics or None if timeout
        """
        try:
            if timeout:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None

    def get_nowait(self) -> Optional[Metrics]:
        """Get metrics without waiting."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    @property
    def latest(self) -> Optional[Metrics]:
        """Get the most recent metrics without removing from queue."""
        return self._latest

    def clear(self) -> None:
        """Clear all items from the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class FrameQueue:
    """Async queue for frame data between capture and vision stages."""

    def __init__(self, maxsize: int = 5):
        self._queue: asyncio.Queue[FrameData] = asyncio.Queue(maxsize=maxsize)

    async def put(self, frame_data: FrameData) -> None:
        """Put frame data, dropping oldest if full."""
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(frame_data)

    async def get(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """Get frame data with optional timeout."""
        try:
            if timeout:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None


class StateQueue:
    """Async queue for game state data between vision and engine stages."""

    def __init__(self, maxsize: int = 5):
        self._queue: asyncio.Queue[StateData] = asyncio.Queue(maxsize=maxsize)

    async def put(self, state_data: StateData) -> None:
        """Put state data, dropping oldest if full."""
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(state_data)

    async def get(self, timeout: Optional[float] = None) -> Optional[StateData]:
        """Get state data with optional timeout."""
        try:
            if timeout:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None
