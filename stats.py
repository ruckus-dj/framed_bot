import dataclasses

from models import FramedResult
from models.episode_result import EpisodeResult


@dataclasses.dataclass(frozen=True)
class Stats:
    rounds_count: int
    rounds_won_count: int
    average_frame: float


async def count_stats(results: list[FramedResult] | list[EpisodeResult]) -> Stats:
    rounds_count = len(results)
    rounds_won: list[FramedResult] = list(filter(lambda framed_result: framed_result.won, results))
    rounds_won_count = len(rounds_won)
    average_frame = (sum([framed_result.win_frame for framed_result in rounds_won]) / rounds_won_count) \
        if rounds_won_count else None

    return Stats(rounds_count=rounds_count, rounds_won_count=rounds_won_count, average_frame=average_frame)
