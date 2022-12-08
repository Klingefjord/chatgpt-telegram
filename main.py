from asyncio import sleep
import asyncio
from datetime import datetime, timedelta
import os
import typing
import telegram
import logging
import dotenv
import nest_asyncio
from modules.chat import Chat, ChatGPTChat, LangChainChat
from modules.google import Google
from utils.persistence import clear_history, persist_message, persistence
from modules.schedule import Scheduler
from utils.auth import auth
from telegram.helpers import escape_markdown
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)


# from telegram.ext import Updater

# DB_URI = "postgresql://botuser:@localhost:5432/botdb"

# updater = Updater("TOKEN")
# dispatcher = updater.dispatcher
# dispatcher.job_queue.scheduler.add_jobstore(
#     PTBSQLAlchemyJobStore(
#         dispatcher=dispatcher,
#         url=DB_URI,
#     ),
# )

# from telegram.ext import Updater
# from ptbcontrib.ptb_sqlalchemy_jobstore import PTBSQLAlchemyJobStore

# DB_URI = "postgresql://botuser:@localhost:5432/botdb"

# updater = Updater("TOKEN")
# dispatcher = updater.dispatcher
# dispatcher.job_queue.scheduler.add_jobstore(
#     PTBSQLAlchemyJobStore(
#         dispatcher=dispatcher,
#         url=DB_URI,
#     ),
# )

# updater.start_polling()
# updater.idle()


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

    # get the user's browser instance, or create one if it doesn't exist
    if update.effective_user.username not in chats:
        await update.message.reply_text("Hang on, setting up your assistant...")
        await create_chat(update.effective_user.username)

    chat = chats[update.effective_user.username]

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

    if update.effective_user.username in chats:
        await update.message.reply_text(
            "You already have an assistant. Use /reset to reset your assistant."
        )
        return

    await create_chat(update.effective_user.username)
    await update.message.reply_text("You are ready to start using Lydia. Say hello!")


@auth()
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the browser instance for the user."""

    if update.effective_user.username in chats:
        await update.message.reply_text("Resetting your assistant...")
        await create_chat(update.effective_user.username)
        await update.message.reply_text(
            "You are ready to start using Lydia. Say hello!"
        )
    else:
        await update.message.reply_text(
            "You don't have an assistant yet. Use /start to get started."
        )

    clear_history(context)


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
    response = await google.google(text, chat=chat, typing_action=typing)
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


async def create_chat(username: str) -> Chat:
    use_langchain = os.getenv("LANGCHAIN", "False") == "True"

    if use_langchain:
        return await create_langchain_chat(username)
    else:
        return await create_chatgpt_chat(username)


async def create_langchain_chat(username: str) -> LangChainChat:
    """Create a langchain representation of a user conversation"""

    if username in chats:
        return chats[username]

    chats[username] = LangChainChat(username)
    return chats[username]


async def create_chatgpt_chat(username: str) -> ChatGPTChat:
    """Create a browser wrapper for a user conversation"""

    print(f"Starting browser for {username}...")

    chat = Chat(
        openai_username=os.getenv("OPEN_AI_USERNAME"),
        openai_password=os.getenv("OPEN_AI_PASSWORD"),
    )

    # log in the user to the chatGPT webpage
    await chat.connect(user_data_dir=f"/tmp/playwright_{username}")
    await chat.login()

    print(f"Successfully started browser for {username}.")

    # cache the browser
    chats[username] = chat
    return chat


async def setup_chats():
    for user in os.getenv("ALLOWED_USERS").split(","):
        try:
            await create_langchain_chat(user)
        except Exception as e:
            print(f"Error starting browser for {user}: {e}")
            continue


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

    # prepare browsers
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_chats())

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
