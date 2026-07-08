import dataclasses
from collections.abc import Sequence

from models.db import ResultForStats


@dataclasses.dataclass(frozen=True)
class Stats:
    rounds_count: int
    rounds_won_count: int
    average_frame: float | None


async def count_stats(results: Sequence[ResultForStats]) -> Stats:
    rounds_count = len(results)
    rounds_won = [result for result in results if result.won]
    rounds_won_count = len(rounds_won)
    total_frames = 0
    for result in rounds_won:
        assert result.win_frame is not None
        total_frames += result.win_frame
    average_frame = (total_frames / rounds_won_count) if rounds_won_count else None

    return Stats(rounds_count=rounds_count, rounds_won_count=rounds_won_count, average_frame=average_frame)
