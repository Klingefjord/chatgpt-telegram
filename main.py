from asyncio import sleep
import asyncio
from datetime import datetime, timedelta
import os
import typing
import pytz
import telegram
import logging
import dotenv
import nest_asyncio
from modules.chat import Chat, ChatGPTChat, LangChainChat
from modules.google import Google
from utils.persistence import clear_history, get_history, persist_message, persistence
from modules.schedule import Scheduler
from utils.auth import auth
from telegram.helpers import escape_markdown
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    Defaults,
    filters,
)

# setup
dotenv.load_dotenv()

# logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# set the global timezone. TODO configure per user.
os.environ["TZ"] = "Europe/Berlin"

application = (
    Application.builder()
    .token(os.environ.get("TELEGRAM_API_KEY"))
    .persistence(persistence)
    .defaults(defaults=Defaults(tzinfo=pytz.timezone(os.environ["TZ"])))
    .build()
)

job_queue = application.job_queue

# dict of browser instances for each user.
chats: typing.Dict[str, Chat] = {}

# set up the Google API
google = Google(os.getenv("SERP_API_KEY"))

# set up the scheduler
scheduler = Scheduler(job_queue)


@auth()
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message to OpenAI"""
    username = update.effective_user.username

    # create a chat instance for the user if not already present
    if username not in chats:
        chats[username] = LangChainChat(username, get_history(context))

    chat = chats[username]

    async def typing():
        await application.bot.send_chat_action(update.effective_chat.id, "typing")

    # get the response from the API
    response = await chat.send_message(
        update.message.text, typing=typing, context=context
    )
    response = escape_markdown(response, version=2)

    # send the response to the user
    await update.message.reply_text(
        response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )

    # persist the message and response to the chat data
    persist_message(update, context, response)


@auth()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text("You are ready to start using Lydia. Say hello!")


@auth()
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the browser instance for the user."""
    username = update.effective_user.username

    if username in chats:
        await update.message.reply_text("Resetting your assistant...")

        # clear the chat instance and history
        await clear_history(context)
        del chats[username]

        # create a new chat instance
        chats[username] = LangChainChat(username)

    await update.message.reply_text("You are ready to start using Lydia. Say hello!")


@auth()
async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the browser instance for the user."""
    if update.effective_user.username not in chats:
        return await update.message.reply_text(
            "You don't have an assistant yet. Use /start to get started."
        )

    chat = chats[update.effective_user.username]

    async def typing():
        await application.bot.send_chat_action(update.effective_chat.id, "typing")

    text = update.message.text.replace("/browse", "").strip()
    response = await google.google(text, chat=chat, typing=typing)
    response = escape_markdown(response, version=2)

    await update.message.reply_text(
        response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )

    # persist the message
    persist_message(update, context, response)


@auth()
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule an event for the user."""

    if update.effective_user.username not in chats:
        return await update.message.reply_text(
            "You don't have an assistant yet. Use /start to get started."
        )

    chat = chats[update.effective_user.username]

    async def typing():
        await application.bot.send_chat_action(update.effective_chat.id, "typing")

    response = await scheduler.schedule(
        update.message.text.replace("/schedule", "").strip(),
        username=update.effective_user.username,
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
        typing=typing,
        chat=chat,
    )
    response = escape_markdown(response, version=2)

    await update.message.reply_text(
        response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )

    # persist the message
    persist_message(update, context, response)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    print(f"Update {update} caused error {context.error}")
    logger.warning('Error "%s"', context.error)


def main():
    # Handle messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, send),
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("browse", browse))
    application.add_error_handler(error)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
