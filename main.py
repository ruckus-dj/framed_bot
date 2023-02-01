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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

framed_pattern = r'Framed #(?P<round>[\d]+)\n🎥(?P<result>(?: 🟥| 🟩| ⬛){6})\n\nhttps:\/\/framed\.wtf'


class FramedFilter(MessageFilter):
    def filter(self, message: Message):
        return re.search(framed_pattern, message.text) is not None


FRAMED_FILTER = FramedFilter(name='FramedFilter')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Привет")


async def new_framed_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await User.update_from_tg_user(update.effective_user)
    result = re.search(framed_pattern, update.message.text)

    framed_round = int(result.groupdict()['round'])
    framed_result = result.groupdict()['result']
    round_won = '🟩' in framed_result
    win_frame = framed_result.count('🟥') + 1 if round_won else None

    saved = await FramedResult.save_result(update.effective_user.id, framed_round, round_won, win_frame)

    if saved:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Спасибо, записал",
            reply_to_message_id=update.message.id
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Твои результаты на этот раунд у меня уже есть",
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

    application.run_polling()
