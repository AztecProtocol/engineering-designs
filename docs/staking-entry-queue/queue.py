import time
from collections import deque
from typing import List, Tuple


class DelayedEntryQueue:
    """
    A queue that holds entries for a minimum duration before allowing them to be dequeued.

    Attributes:
        max_dequeue_count (int): Maximum number of elements that can be dequeued at once
        delay_seconds (float): Minimum time in seconds an element must wait before being dequeued
    """

    def __init__(self, max_dequeue_count: int, delay_seconds: float):
        """
        Initialize the delayed entry queue.

        Args:
            max_dequeue_count: Maximum number of elements to return in a single dequeue operation
            delay_seconds: Minimum time in seconds an element must be in the queue before it can be dequeued
        """
        self.max_dequeue_count = max_dequeue_count
        self.delay_seconds = delay_seconds
        self._queue: deque[Tuple[int, float]] = deque()  # Store (id, timestamp) pairs
        self._id_set: set[int] = set()  # Track unique IDs for O(1) duplicate checking

    def enqueue(self, id: int) -> bool:
        """
        Add an ID to the queue if it doesn't already exist.

        Args:
            id: The unique identifier to add to the queue

        Returns:
            True if the ID was added, False if it was a duplicate
        """
        if id in self._id_set:
            return False

        self._queue.append((id, time.time()))
        self._id_set.add(id)
        return True

    def dequeue(self, current_time: float) -> List[int]:
        """
        Remove and return up to N elements that have been in the queue for at least D seconds.

        Returns:
            List of IDs that have met the delay requirement (up to max_dequeue_count elements)
        """
        ready_elements = []

        # Check elements from the front of the queue (oldest first)
        while self._queue and len(ready_elements) < self.max_dequeue_count:
            id, enqueue_time = self._queue[0]

            # Check if this element has been in the queue long enough
            if current_time - enqueue_time >= self.delay_seconds:
                self._queue.popleft()
                self._id_set.remove(id)
                ready_elements.append(id)
            else:
                # Since queue is ordered by time, if this element isn't ready,
                # no subsequent elements will be ready either
                break

        return ready_elements

    def size(self) -> int:
        """Return the current number of elements in the queue."""
        return len(self._queue)

    def peek_ready_count(self) -> int:
        """Return the number of elements currently ready to be dequeued."""
        current_time = time.time()
        ready_count = 0

        for id, enqueue_time in self._queue:
            if current_time - enqueue_time >= self.delay_seconds:
                ready_count += 1
            else:
                break

        return ready_count
