import asyncio
import logging
import re

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    filters,
    MessageHandler,
    AIORateLimiter,
)
from telegram.ext.filters import MessageFilter, Message

from config import BOT_TOKEN
from models import init_db, User, FramedResult
from models.episode_result import EpisodeResult
from stats import count_stats, Stats

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

framed_pattern = r'Framed #(?P<round>[\d]+)\n🎥(?P<result>(?: 🟥| 🟩| ⬛){6})\n\nhttps:\/\/framed\.wtf'
episode_pattern = r'Episode #(?P<round>[\d]+)\n📺(?P<result>(?: 🟥| 🟩| ⬛){10})\n\nhttps:\/\/episode\.wtf'


class FramedFilter(MessageFilter):
    def filter(self, message: Message):
        return re.search(framed_pattern, message.text) is not None


FRAMED_FILTER = FramedFilter(name='FramedFilter')


class EpisodeFilter(MessageFilter):
    def filter(self, message: Message):
        return re.search(episode_pattern, message.text) is not None


EPISODE_FILTER = EpisodeFilter(name='EpisodeFilter')


def pluralize(count: int, first_form: str, second_form: str, third_form: str):
    if count % 10 == 1 and count != 11:
        return first_form
    if count % 10 in (2, 3, 4) and count not in (12, 13, 14):
        return second_form
    return third_form


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Привет')


async def save_results(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        pattern: str,
        result_class: type[FramedResult] | type[EpisodeResult],
):
    await User.update_from_tg_user(update.effective_user)
    result = re.search(pattern, update.message.text)

    data_round = int(result.groupdict()['round'])
    data_result = result.groupdict()['result']
    data_won = '🟩' in data_result
    data_win_frame = data_result.count('🟥') + 1 if data_won else None

    saved = await result_class.save_result(update.effective_user.id, data_round, data_won, data_win_frame)

    if saved:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Спасибо, записал',
            reply_to_message_id=update.message.id
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Твои результаты на этот раунд у меня уже есть',
            reply_to_message_id=update.message.id
        )


async def new_framed_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_results(update, context, framed_pattern, FramedResult)


async def new_episode_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_results(update, context, episode_pattern, EpisodeResult)


async def generate_stats_text(framed_stats: Stats, episode_stats: Stats):
    text = f'Ты участвовал в '
    if framed_stats.rounds_count:
        text += f'{framed_stats.rounds_count} ' \
                f'{pluralize(framed_stats.rounds_count, "раунде", "раундах", "раундах")} ' \
                f'framed.wtf, ' \

        if framed_stats.rounds_won_count:
            text += f'отгадал {framed_stats.rounds_won_count} ' \
                    f'{pluralize(framed_stats.rounds_won_count, "фильм", "фильма", "фильмов")} ' \
                    f'в среднем с {framed_stats.average_frame} кадра.'
        else:
            text += f'но ни разу ничего не отгадал.'

    if framed_stats.rounds_count and episode_stats.rounds_count:
        text += '\nА ещё в '

    if episode_stats.rounds_count:
        text += f'{episode_stats.rounds_count} ' \
                f'{pluralize(framed_stats.rounds_count, "раунде", "раундах", "раундах")} ' \
                f'episode.wtf, '

        if episode_stats.rounds_won_count:
            text += f'отгадал {episode_stats.rounds_won_count} ' \
                    f'{pluralize(framed_stats.rounds_won_count, "сериал", "сериала", "сериалов")} ' \
                    f'в среднем с {episode_stats.average_frame} кадра.'
        else:
            text += f'но ни разу ничего не отгадал.'

    return text


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await User.get(update.effective_user.id)

    if not user:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Я тебя не знаю',
            reply_to_message_id=update.message.id
        )
        return

    framed_stats = await count_stats(user.framed_results)
    episode_stats = await count_stats(user.episode_results)

    text = await generate_stats_text(framed_stats, episode_stats)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_to_message_id=update.message.id
    )


if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

    loop = asyncio.get_event_loop()
    coroutine = init_db()
    loop.run_until_complete(coroutine)

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    framed_data_handler = MessageHandler(filters.ChatType.GROUPS & FRAMED_FILTER, new_framed_data)
    application.add_handler(framed_data_handler)

    episode_data_handler = MessageHandler(filters.ChatType.GROUPS & EPISODE_FILTER, new_episode_data)
    application.add_handler(episode_data_handler)

    stats_handler = CommandHandler('stats', stats)
    application.add_handler(stats_handler)

    application.run_polling()
