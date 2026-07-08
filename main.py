import asyncio
import json
import logging
import re
from datetime import timedelta
from enum import IntEnum
from typing import Protocol

from tabulate import tabulate
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
    ReactionTypeEmoji,
    Update,
)
from telegram import (
    Message as TelegramMessage,
)
from telegram.constants import ReactionEmoji
from telegram.error import TelegramError
from telegram.ext import (
    AIORateLimiter,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)
from telegram.ext.filters import Message, MessageFilter

from config import ADMIN_USER_ID, BOT_TOKEN
from models import FramedResult, User, init_db
from models.episode_result import EpisodeResult
from models.group import Group
from stats import Stats, count_stats

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

framed_pattern = r'Framed #(?P<round>[\d]+)\n🎥(?P<result>(?: 🟥| 🟩| ⬛| ⬛️){6})\n\nhttps:\/\/framed\.wtf'
episode_pattern = r'Episode #(?P<round>[\d]+)\n📺(?P<result>(?: 🟥| 🟩| ⬛| ⬛️){10})\n\nhttps:\/\/episode\.wtf'
saved_result_reaction = ReactionTypeEmoji(ReactionEmoji.THUMBS_UP)
duplicate_result_reaction = ReactionTypeEmoji(ReactionEmoji.THUMBS_DOWN)


class TopType(IntEnum):
    TOP_SCORE = 1
    TOP_FRAME = 2
    TOP_WIN = 3
    TOP_ROUNDS = 4


class FramedFilter(MessageFilter):
    def filter(self, message: Message):
        return message.text is not None and re.search(framed_pattern, message.text) is not None


FRAMED_FILTER = FramedFilter(name='FramedFilter')


class EpisodeFilter(MessageFilter):
    def filter(self, message: Message):
        return message.text is not None and re.search(episode_pattern, message.text) is not None


EPISODE_FILTER = EpisodeFilter(name='EpisodeFilter')


class ResultSaver(Protocol):
    @staticmethod
    async def save_result(user_id: int, framed_round: int, won: bool, win_frame: int | None) -> bool: ...


async def delete_message_task(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    if job is None:
        return
    chat_id = job.chat_id
    message_id = job.data
    if chat_id is None or not isinstance(message_id, int):
        return
    await context.bot.delete_message(chat_id, message_id)


def pluralize(count: int, first_form: str, second_form: str, third_form: str):
    if count % 10 == 1 and count != 11:
        return first_form
    if count % 10 in (2, 3, 4) and count not in (12, 13, 14):
        return second_form
    return third_form


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat is None:
        return
    await context.bot.send_message(chat_id=chat.id, text='Привет')


async def save_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pattern: str,
    result_class: type[ResultSaver],
):
    effective_user = update.effective_user
    effective_chat = update.effective_chat
    message = update.message
    if effective_user is None or effective_chat is None or message is None or message.text is None:
        return

    await User.update_from_tg_user(effective_user)
    result = re.search(pattern, message.text)
    if result is None:
        return

    data_round = int(result.groupdict()['round'])
    data_result = result.groupdict()['result']
    data_won = '🟩' in data_result
    data_win_frame = data_result.count('🟥') + 1 if data_won else None

    saved = await result_class.save_result(effective_user.id, data_round, data_won, data_win_frame)

    reaction = saved_result_reaction if saved else duplicate_result_reaction

    try:
        await context.bot.set_message_reaction(
            chat_id=effective_chat.id,
            message_id=message.id,
            reaction=reaction,
        )
        return
    except TelegramError:
        logging.warning('Не удалось проставить реакцию, откатываюсь к сообщению-ответу', exc_info=True)

    job_queue = context.job_queue

    if saved:
        reply_message = await context.bot.send_message(
            chat_id=effective_chat.id,
            text='Спасибо, записал',
            reply_to_message_id=message.id,
        )
    else:
        reply_message = await context.bot.send_message(
            chat_id=effective_chat.id,
            text='Твои результаты на этот раунд у меня уже есть',
            reply_to_message_id=message.id,
        )

    if job_queue is not None:
        job_queue.run_once(delete_message_task, timedelta(seconds=30), reply_message.id, chat_id=effective_chat.id)


async def new_framed_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_results(update, context, framed_pattern, FramedResult)


async def new_episode_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_results(update, context, episode_pattern, EpisodeResult)


async def generate_stats_text(framed_stats: Stats, episode_stats: Stats):
    text = 'Ты участвовал в '
    if framed_stats.rounds_count:
        text += (
            f'{framed_stats.rounds_count} '
            f'{pluralize(framed_stats.rounds_count, "раунде", "раундах", "раундах")} '
            f'framed.wtf, '
        )
        if framed_stats.rounds_won_count:
            text += (
                f'отгадал {framed_stats.rounds_won_count} '
                f'{pluralize(framed_stats.rounds_won_count, "фильм", "фильма", "фильмов")} '
                f'в среднем с {framed_stats.average_frame} кадра.'
            )
        else:
            text += 'но ни разу ничего не отгадал.'

    if framed_stats.rounds_count and episode_stats.rounds_count:
        text += '\nА ещё в '

    if episode_stats.rounds_count:
        text += (
            f'{episode_stats.rounds_count} '
            f'{pluralize(episode_stats.rounds_count, "раунде", "раундах", "раундах")} '
            f'episode.wtf, '
        )

        if episode_stats.rounds_won_count:
            text += (
                f'отгадал {episode_stats.rounds_won_count} '
                f'{pluralize(episode_stats.rounds_won_count, "сериал", "сериала", "сериалов")} '
                f'в среднем с {episode_stats.average_frame} кадра.'
            )
        else:
            text += 'но ни разу ничего не отгадал.'

    return text


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_user = update.effective_user
    effective_chat = update.effective_chat
    message = update.message
    if effective_user is None or effective_chat is None or message is None:
        return

    user = await User.get(effective_user.id)

    if not user:
        await context.bot.send_message(chat_id=effective_chat.id, text='Я тебя не знаю', reply_to_message_id=message.id)
        return

    framed_stats = await count_stats(user.framed_results)
    episode_stats = await count_stats(user.episode_results)

    text = await generate_stats_text(framed_stats, episode_stats)

    reply_message = await context.bot.send_message(chat_id=effective_chat.id, text=text, reply_to_message_id=message.id)

    job_queue = context.job_queue
    if job_queue is None:
        return

    job_queue.run_once(delete_message_task, timedelta(seconds=30), message.id, chat_id=effective_chat.id)

    job_queue.run_once(delete_message_task, timedelta(seconds=30), reply_message.id, chat_id=effective_chat.id)


async def update_chat_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_chat = update.effective_chat
    if effective_chat is None:
        return
    await Group.update_from_tg_chat(effective_chat)


async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_message = update.effective_message
    if effective_message is None or effective_message.text is None:
        return
    _, _, announcement_text = effective_message.text.partition(' ')
    if not announcement_text:
        return
    groups = await Group.get_all()
    for group in groups:
        await context.bot.send_message(chat_id=group.id, text=announcement_text)


def top_reply_markup(top_type: TopType):
    type_to_text = {
        TopType.TOP_SCORE: 'По очкам',
        TopType.TOP_ROUNDS: 'По участиям',
        TopType.TOP_FRAME: 'По кадрам',
        TopType.TOP_WIN: 'По фильмам',
    }
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(type_to_text[_type], callback_data=json.dumps({'top': _type}))
                for _type in type_to_text
                if _type != top_type
            ]
        ]
    )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    effective_chat = update.effective_chat
    message = update.message
    if effective_chat is None or message is None:
        return
    results = await FramedResult.top_score()
    text = await format_top(TopType.TOP_SCORE, results)

    await context.bot.send_message(
        chat_id=effective_chat.id,
        text=text,
        reply_to_message_id=message.id,
        entities=[MessageEntity(MessageEntity.CODE, 0, len(text))],
        reply_markup=top_reply_markup(TopType.TOP_SCORE),
    )


async def format_top(top_type, results) -> str:
    match top_type:
        case TopType.TOP_WIN:
            text = 'Топ по количеству отгаданных фильмов:\n'
        case TopType.TOP_FRAME:
            text = 'Топ по среднему отгаданному кадру:\n'
        case TopType.TOP_SCORE:
            text = 'Топ по очкам:\n'
        case TopType.TOP_ROUNDS:
            text = 'Топ по количеству участий:\n'
        case _:
            text = ''
    text += tabulate(
        [(i, result.name, result.score) for i, result in enumerate(results, 1)],
        ('#', 'Имя', 'Очки'),
        tablefmt='rounded_grid',
    )
    return text


async def inline_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None or query.data is None:
        return
    data = json.loads(query.data)
    top_type = TopType(data['top'])
    results = []
    match top_type:
        case TopType.TOP_WIN:
            results = await FramedResult.top_won()
        case TopType.TOP_FRAME:
            results = await FramedResult.top_average_frame()
        case TopType.TOP_SCORE:
            results = await FramedResult.top_score()
        case TopType.TOP_ROUNDS:
            results = await FramedResult.top_rounds()

    text = await format_top(top_type, results)
    query_message = query.message
    if not isinstance(query_message, TelegramMessage):
        await query.answer()
        return
    await query_message.edit_text(
        text,
        entities=[MessageEntity(MessageEntity.CODE, 0, len(text))],
        reply_markup=top_reply_markup(top_type),
    )

    await query.answer()


if __name__ == '__main__':
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter())
        .persistence(PicklePersistence('bot_data'))
        .build()
    )

    loop = asyncio.get_event_loop()
    coroutine = init_db()
    loop.run_until_complete(coroutine)

    start_handler = CommandHandler('start', start, block=False)
    application.add_handler(start_handler)

    announce_handler = CommandHandler(
        'announce', announce, filters.ChatType.PRIVATE & filters.User(ADMIN_USER_ID), block=False
    )
    application.add_handler(announce_handler)

    chat_update_handler = MessageHandler(filters.ChatType.GROUPS, update_chat_data, block=False)
    application.add_handler(chat_update_handler, -1)

    framed_data_handler = MessageHandler(filters.ChatType.GROUPS & FRAMED_FILTER, new_framed_data, block=False)
    application.add_handler(framed_data_handler)

    episode_data_handler = MessageHandler(filters.ChatType.GROUPS & EPISODE_FILTER, new_episode_data, block=False)
    application.add_handler(episode_data_handler)

    stats_handler = CommandHandler('stats', stats, block=False)
    application.add_handler(stats_handler)

    top_handler = CommandHandler('top', top, block=False)
    application.add_handler(top_handler)

    inline_top_handler = CallbackQueryHandler(inline_top, pattern=r'^{"top": [\d]+}$', block=False)
    application.add_handler(inline_top_handler)

    application.run_polling()
