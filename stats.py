import dataclasses
from collections.abc import Sequence
from typing import override

from models.db import ResultForStats


@dataclasses.dataclass(frozen=True)
class Stats:
    rounds_count: int
    rounds_won_count: int
    average_frame: float | None


@dataclasses.dataclass(frozen=True, slots=True)
class MissingWinFrameError(Exception):
    result_index: int

    @override
    def __str__(self) -> str:
        return f'winning result at index {self.result_index} has no win_frame'


async def count_stats(results: Sequence[ResultForStats]) -> Stats:
    rounds_count = len(results)
    rounds_won = [result for result in results if result.won]
    rounds_won_count = len(rounds_won)
    total_frames = 0
    for result_index, result in enumerate(rounds_won):
        if result.win_frame is None:
            raise MissingWinFrameError(result_index=result_index)
        total_frames += result.win_frame
    average_frame = (total_frames / rounds_won_count) if rounds_won_count else None

    return Stats(rounds_count=rounds_count, rounds_won_count=rounds_won_count, average_frame=average_frame)
