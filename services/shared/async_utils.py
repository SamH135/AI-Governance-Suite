"""Shared async helpers."""

import asyncio

_tasks: set = set()


def spawn(coro):
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task
