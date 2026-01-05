import asyncio

import pytest

from phone_agent.agent import PhoneAgent


@pytest.mark.asyncio
async def test_compress_history_images_schedules_in_running_loop(monkeypatch):
    agent = PhoneAgent()
    calls: list[list[int]] = []

    def fake_sync(indices: list[int]):
        calls.append(indices)

    monkeypatch.setattr(agent, "_compress_history_images_sync", fake_sync)

    task = agent._compress_history_images([1, 2, 3], loop=asyncio.get_running_loop())

    assert isinstance(task, asyncio.Task)

    await task

    assert calls == [[1, 2, 3]]


def test_compress_history_images_runs_synchronously_without_loop(monkeypatch):
    agent = PhoneAgent()
    calls: list[list[int]] = []

    def fake_sync(indices: list[int]):
        calls.append(indices)

    monkeypatch.setattr(agent, "_compress_history_images_sync", fake_sync)

    result = agent._compress_history_images([42], loop=None)

    assert result is None
    assert calls == [[42]]
