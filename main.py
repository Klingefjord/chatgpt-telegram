from asyncio import sleep
import asyncio
import os
import typing
import telegram
import logging
import dotenv
import nest_asyncio
from modules.chat_gpt import ChatGPT
from modules.google import Google
from utils.auth import auth
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# setup
nest_asyncio.apply()
dotenv.load_dotenv()

# logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# set up app
application = Application.builder().token(os.environ.get("TELEGRAM_API_KEY")).build()

# dict of browser instances for each user.
browsers: typing.Dict[str, ChatGPT] = {}

# set up the Google API
google = Google(os.getenv("SERP_API_KEY"))


@auth()
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message to OpenAI."""

    # get the user's browser instance, or create one if it doesn't exist
    if update.effective_user.username not in browsers:
        await update.message.reply_text("Hang on, setting up your assistant...")
        await create_browser(update.effective_user.username)

    browser = browsers[update.effective_user.username]

    async def typing():
        await application.bot.send_chat_action(update.effective_chat.id, "typing")

    # get the response from the API
    response = await browser.send_message(update.message.text, typing_action=typing)
    if google.needs_google(response):
        response = await google.google(
            update.message.text, api=browser, typing_action=typing
        )

    # send the response to the user
    await update.message.reply_text(
        response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )


@auth()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""

    if update.effective_user.username in browsers:
        await update.message.reply_text(
            "You already have an assistant. Use /reset to reset your assistant."
        )
        return

    await create_browser(update.effective_user.username)
    await update.message.reply_text("You are ready to start using Lydia. Say hello!")


@auth()
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the browser instance for the user."""

    if update.effective_user.username in browsers:
        update.message.reply_text("Resetting your assistant...")
        await browsers[update.effective_user.username].login()
        await update.message.reply_text(
            "You are ready to start using Lydia. Say hello!"
        )
    else:
        await update.message.reply_text(
            "You don't have an assistant yet. Use /start to get started."
        )


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    print(f"Update {update} caused error {context.error}")
    logger.warning('Error "%s"', context.error)


@auth()
async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.username not in browsers:
        return await update.message.reply_text(
            "You don't have an assistant yet. Use /start to get started."
        )

    browser = browsers[update.effective_user.username]
    message = update.message.text.replace("/browse", "")

    response = await google.google(browser, message)

    await update.message.reply_text(
        response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )


async def create_browser(username: str) -> ChatGPT:
    print(f"Starting browser for {username}...")

    browser = ChatGPT(
        openai_username=os.getenv("OPEN_AI_USERNAME"),
        openai_password=os.getenv("OPEN_AI_PASSWORD"),
    )

    # log in the user to the chatGPT webpage
    await browser.connect(user_data_dir=f"/tmp/playwright_{username}")
    await browser.login()

    print(f"Successfully started browser for {username}.")

    # cache the browser
    browsers[username] = browser
    return browser


async def setup_browsers():
    for user in os.getenv("ALLOWED_USERS").split(","):
        try:
            await create_browser(user)
        except Exception as e:
            print(f"Error starting browser for {user}: {e}")
            continue


def main():
    # Handle messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("browse", browse))
    application.add_error_handler(error)

    # prepare browsers
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_browsers())

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
