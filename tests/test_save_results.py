from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from telegram import Chat, Message, ReactionTypeEmoji, Update, User
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, ContextTypes, ExtBot, JobQueue

import main
from models.episode_result import EpisodeResult
from models.framed_result import FramedResult
from models.user import User as BotUser


@dataclass(frozen=True, slots=True)
class ReactionCall:
    chat_id: int
    message_id: int
    reaction: ReactionTypeEmoji


@dataclass(frozen=True, slots=True)
class SendMessageCall:
    chat_id: int
    text: str
    reply_to_message_id: int


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    callback: Callable[[ContextTypes.DEFAULT_TYPE], Awaitable[None]]
    when: timedelta
    data: int
    chat_id: int


@dataclass(slots=True)
class BotRecorder:
    should_fail_reaction: bool = False
    reaction_calls: list[ReactionCall] = field(default_factory=list)
    send_message_calls: list[SendMessageCall] = field(default_factory=list)

    async def set_message_reaction(self, *, chat_id: int, message_id: int, reaction: ReactionTypeEmoji) -> bool:
        self.reaction_calls.append(ReactionCall(chat_id=chat_id, message_id=message_id, reaction=reaction))
        if self.should_fail_reaction:
            raise TelegramError('reactions are unavailable')
        return True

    async def send_message(self, *, chat_id: int, text: str, reply_to_message_id: int) -> Message:
        self.send_message_calls.append(
            SendMessageCall(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id)
        )
        user = User(id=1, first_name='Bot', is_bot=True)
        chat = Chat(id=chat_id, type='group')
        return Message(
            message_id=777,
            date=datetime.now(UTC),
            chat=chat,
            from_user=user,
            text=text,
        )


@dataclass(slots=True)
class JobQueueRecorder:
    calls: list[ScheduledJob] = field(default_factory=list)

    def run_once(
        self,
        callback: Callable[[ContextTypes.DEFAULT_TYPE], Awaitable[None]],
        when: timedelta,
        data: int,
        *,
        chat_id: int,
    ) -> ScheduledJob:
        job = ScheduledJob(callback=callback, when=when, data=data, chat_id=chat_id)
        self.calls.append(job)
        return job


@dataclass(frozen=True, slots=True)
class RecordedContext:
    context: ContextTypes.DEFAULT_TYPE
    bot: BotRecorder
    job_queue: JobQueueRecorder


def make_update(text: str = 'Framed #42\n🎥 🟥 🟩 ⬛ ⬛ ⬛ ⬛\n\nhttps://framed.wtf') -> Update:
    user = User(id=99, first_name='Test', is_bot=False)
    chat = Chat(id=123, type='group')
    message = Message(
        message_id=456,
        date=datetime.now(UTC),
        chat=chat,
        from_user=user,
        text=text,
    )
    return Update(update_id=1, message=message)


def make_context(monkeypatch: pytest.MonkeyPatch, *, fail_reaction: bool = False) -> RecordedContext:
    application = ApplicationBuilder().token('123:ABC').build()
    context = ContextTypes.DEFAULT_TYPE(application)
    bot = BotRecorder(should_fail_reaction=fail_reaction)
    job_queue = JobQueueRecorder()
    assert context.job_queue is not None

    async def set_message_reaction(
        _bot: ExtBot[None], *, chat_id: int, message_id: int, reaction: ReactionTypeEmoji
    ) -> bool:
        return await bot.set_message_reaction(chat_id=chat_id, message_id=message_id, reaction=reaction)

    async def send_message(_bot: ExtBot[None], *, chat_id: int, text: str, reply_to_message_id: int) -> Message:
        return await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id)

    def run_once(
        _job_queue: JobQueue[ContextTypes.DEFAULT_TYPE],
        callback: Callable[[ContextTypes.DEFAULT_TYPE], Awaitable[None]],
        when: timedelta,
        data: int,
        *,
        chat_id: int,
    ) -> ScheduledJob:
        return job_queue.run_once(callback, when, data, chat_id=chat_id)

    monkeypatch.setattr(type(context.bot), 'set_message_reaction', set_message_reaction)
    monkeypatch.setattr(type(context.bot), 'send_message', send_message)
    monkeypatch.setattr(type(context.job_queue), 'run_once', run_once)
    return RecordedContext(context=context, bot=bot, job_queue=job_queue)


def make_result_model(saved: bool):
    class ResultModel:
        calls: list[tuple[int, int, bool, int | None]] = []

        @staticmethod
        async def save_result(user_id: int, framed_round: int, won: bool, win_frame: int | None) -> bool:
            ResultModel.calls.append((user_id, framed_round, won, win_frame))
            return saved

    return ResultModel


@pytest.mark.asyncio
async def test_save_results_uses_saved_reaction_when_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    update = make_update()
    test_context = make_context(monkeypatch)
    result_model = make_result_model(True)
    update_from_user = AsyncMock()
    monkeypatch.setattr(BotUser, 'update_from_tg_user', update_from_user)

    await main.save_results(update, test_context.context, main.framed_pattern, result_model)

    update_from_user.assert_awaited_once_with(update.effective_user)
    assert result_model.calls == [(99, 42, True, 2)]
    assert test_context.bot.reaction_calls == [
        ReactionCall(chat_id=123, message_id=456, reaction=main.saved_result_reaction)
    ]
    assert test_context.bot.send_message_calls == []
    assert test_context.job_queue.calls == []


@pytest.mark.asyncio
async def test_save_results_uses_trophy_reaction_when_saved_on_first_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update = make_update('Framed #42\n🎥 🟩 ⬛ ⬛ ⬛ ⬛ ⬛\n\nhttps://framed.wtf')
    test_context = make_context(monkeypatch)
    result_model = make_result_model(True)
    update_from_user = AsyncMock()
    monkeypatch.setattr(BotUser, 'update_from_tg_user', update_from_user)

    await main.save_results(update, test_context.context, main.framed_pattern, result_model)

    assert result_model.calls == [(99, 42, True, 1)]
    assert test_context.bot.reaction_calls == [
        ReactionCall(chat_id=123, message_id=456, reaction=main.first_frame_saved_result_reaction)
    ]
    assert test_context.bot.send_message_calls == []
    assert test_context.job_queue.calls == []


@pytest.mark.asyncio
async def test_save_results_uses_duplicate_reaction_when_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    update = make_update()
    test_context = make_context(monkeypatch)
    result_model = make_result_model(False)
    update_from_user = AsyncMock()
    monkeypatch.setattr(BotUser, 'update_from_tg_user', update_from_user)

    await main.save_results(update, test_context.context, main.framed_pattern, result_model)

    assert result_model.calls == [(99, 42, True, 2)]
    assert test_context.bot.reaction_calls == [
        ReactionCall(chat_id=123, message_id=456, reaction=main.duplicate_result_reaction)
    ]
    assert test_context.bot.send_message_calls == []
    assert test_context.job_queue.calls == []


@pytest.mark.asyncio
async def test_save_results_falls_back_to_reply_when_reaction_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    update = make_update()
    test_context = make_context(monkeypatch, fail_reaction=True)
    result_model = make_result_model(True)
    update_from_user = AsyncMock()
    monkeypatch.setattr(BotUser, 'update_from_tg_user', update_from_user)

    await main.save_results(update, test_context.context, main.framed_pattern, result_model)

    assert test_context.bot.reaction_calls == [
        ReactionCall(chat_id=123, message_id=456, reaction=main.saved_result_reaction)
    ]
    assert test_context.bot.send_message_calls == [
        SendMessageCall(chat_id=123, text='Спасибо, записал', reply_to_message_id=456)
    ]
    assert len(test_context.job_queue.calls) == 1
    job = test_context.job_queue.calls[0]
    assert job.callback is main.delete_message_task
    assert job.when == timedelta(seconds=30)
    assert job.data == 777
    assert job.chat_id == 123


@pytest.mark.asyncio
async def test_new_framed_data_delegates_to_save_results(monkeypatch: pytest.MonkeyPatch) -> None:
    update = make_update()
    test_context = make_context(monkeypatch)
    save_results = AsyncMock()
    monkeypatch.setattr(main, 'save_results', save_results)

    await main.new_framed_data(update, test_context.context)

    save_results.assert_awaited_once_with(update, test_context.context, main.framed_pattern, FramedResult)


@pytest.mark.asyncio
async def test_new_episode_data_delegates_to_save_results(monkeypatch: pytest.MonkeyPatch) -> None:
    update = make_update('Episode #7\n📺 🟥 🟥 🟩 ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛\n\nhttps://episode.wtf')
    test_context = make_context(monkeypatch)
    save_results = AsyncMock()
    monkeypatch.setattr(main, 'save_results', save_results)

    await main.new_episode_data(update, test_context.context)

    save_results.assert_awaited_once_with(update, test_context.context, main.episode_pattern, EpisodeResult)
