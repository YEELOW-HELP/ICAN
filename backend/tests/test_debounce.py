import asyncio

from app.bot.debounce import Debouncer


async def test_rapid_pushes_are_coalesced_into_one_flush():
    flushes: list[tuple[int, list[str]]] = []

    async def flush(key: int, texts: list[str]) -> None:
        flushes.append((key, texts))

    debouncer = Debouncer(delay_seconds=0.05, flush=flush)

    debouncer.push(1, "20 000")
    await asyncio.sleep(0.01)
    debouncer.push(1, "грн")  # arrives before the first flush fires — should cancel and merge

    await asyncio.sleep(0.1)

    assert flushes == [(1, ["20 000", "грн"])]


async def test_separate_keys_flush_independently():
    flushes: list[tuple[int, list[str]]] = []

    async def flush(key: int, texts: list[str]) -> None:
        flushes.append((key, texts))

    debouncer = Debouncer(delay_seconds=0.03, flush=flush)

    debouncer.push(1, "a")
    debouncer.push(2, "b")

    await asyncio.sleep(0.08)

    assert sorted(flushes) == [(1, ["a"]), (2, ["b"])]


async def test_messages_spaced_apart_flush_separately():
    flushes: list[tuple[int, list[str]]] = []

    async def flush(key: int, texts: list[str]) -> None:
        flushes.append((key, texts))

    debouncer = Debouncer(delay_seconds=0.03, flush=flush)

    debouncer.push(1, "first")
    await asyncio.sleep(0.08)  # let it flush before the next push
    debouncer.push(1, "second")
    await asyncio.sleep(0.08)

    assert flushes == [(1, ["first"]), (1, ["second"])]
