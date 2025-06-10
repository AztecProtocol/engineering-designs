import marimo

__generated_with = "0.13.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import random
    import matplotlib.pyplot as plt
    return mo, plt, random


@app.cell(hide_code=True)
def _():
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

        def enqueue(self, id: int, current_time: float) -> bool:
            """
            Add an ID to the queue if it doesn't already exist.

            Args:
                id: The unique identifier to add to the queue

            Returns:
                True if the ID was added, False if it was a duplicate
            """
            if id in self._id_set:
                return False

            self._queue.append((id, current_time))
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

    return (DelayedEntryQueue,)


@app.cell(hide_code=True)
def _(
    DelayedEntryQueue,
    delay,
    dequeue_count,
    dequeue_frequency,
    initial_validator_set_size,
    random,
    simulation_steps,
):
    entry_queue = DelayedEntryQueue(delay_seconds=delay.value, max_dequeue_count=dequeue_count.value)
    X = [i for i in range(0, min(simulation_steps.value, delay.value + (initial_validator_set_size.value // dequeue_count.value) * dequeue_frequency.value))]

    for _ in range(1,initial_validator_set_size.value):
        entry_queue.enqueue(random.randint(1,2**160-1), 0)

    queue_length = []
    validator_set_size = []
    validators = []
    churn = []

    for x in X:
        old_size = len(validators)
        if x % 12 == 0:
            for d in entry_queue.dequeue(x):
                validators.append(d)
        queue_length.append(entry_queue.size())
        new_size = len(validators)
        validator_set_size.append(new_size)
        if new_size > 0:
            churn.append((new_size - old_size) / new_size)
        else:
            churn.append(0)
    return X, churn, validator_set_size


@app.cell(hide_code=True)
def _(mo):
    dequeue_count = mo.ui.slider(0,50, value=5)
    delay = mo.ui.dropdown(options=[0,12, 36, 36*32, 36*32*5, 86400], value=36*32)
    simulation_steps = mo.ui.dropdown(options=[i * 86400 for i in range(1,10)], value = 2 * 86400)
    initial_validator_set_size = mo.ui.slider(1,2**12, value=2**12)
    dequeue_frequency = mo.ui.dropdown(options=[i*12 for i in range(1,5)], value = 12)
    return (
        delay,
        dequeue_count,
        dequeue_frequency,
        initial_validator_set_size,
        simulation_steps,
    )


@app.cell
def _(
    delay,
    dequeue_count,
    dequeue_frequency,
    initial_validator_set_size,
    mo,
    simulation_steps,
):
    mo.md(
        f"""
    Initial Validators Queued: {initial_validator_set_size}
    Dequeue Count: {dequeue_count}
    Dequeue Frequency: {dequeue_frequency}
    Delay Seconds: {delay}

    Simulation Seconds: {simulation_steps}

    """
    )
    return


@app.cell(hide_code=True)
def _(X, churn, delay, plt, validator_set_size):
    # Create an x-axis that matches the number of steps in the simulation.

    # Create a figure and a set of subplots (1 row, 2 columns)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # --- First Plot: Validator Set Size ---
    ax1.plot(X, validator_set_size, color='b')
    ax1.set_title('Validator Set Size Over Time')
    ax1.set_xlabel('Seconds')
    ax1.set_ylabel('Number of Active Validators')
    ax1.grid(True)

    # --- Second Plot: Churn ---
    ax2.plot(X[delay.value:], churn[delay.value:], color='r')
    ax2.set_title('Validator Churn Over Time')
    ax2.set_xlabel('Seconds')
    ax2.set_ylabel('Churn Rate')
    ax2.grid(True)

    # Adjust layout to prevent titles from overlapping and display the plot
    plt.tight_layout()
    plt.show()
    return


@app.cell
def _(X, mo):
    mo.md(f"""It will take {round(X[-1] / (60*60))} hours to clear the queue""")
    return


if __name__ == "__main__":
    app.run()
