import os
import pytz
import dotenv
import telegram
import logging
import asyncio
import dotenv
from api import Mendable
from utils.auth import auth
from telegram.helpers import escape_markdown
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    CallbackContext,
    MessageHandler,
    CommandHandler,
    PicklePersistence,
    Defaults,
    filters,
)

# Prepare the environment
dotenv.load_dotenv()

# logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# set the global timezone.
os.environ["TZ"] = "Europe/Berlin"

application = (
    Application.builder()
    .token(os.environ.get("TELEGRAM_BOT_TOKEN"))
    .persistence(PicklePersistence(filepath="./data.pickle"))
    .defaults(defaults=Defaults(tzinfo=pytz.timezone(os.environ["TZ"])))
    .build()
)

mendable = Mendable(api_key=os.environ.get("MENDABLE_API_KEY"))


async def send_typing_action(context: CallbackContext, chat_id):
    """Send typing action while processing the query."""
    for _ in range(0, 3):
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(5)


@auth()
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message to Mendable"""
    # Start the typing task.
    typing_task = asyncio.create_task(
        send_typing_action(context, update.effective_chat.id)
    )

    # send typing action
    await application.bot.send_chat_action(update.effective_chat.id, "typing")

    # get the response from the API
    response = await mendable.call(query=update.message.text)
    response = escape_markdown(response, version=2)

    # Cancel the typing task.
    typing_task.cancel()

    # send the response to the user
    await update.message.reply_text(
        response,
        disable_web_page_preview=True,
        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2,
    )


@auth()
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the bot"""
    mendable.history = []
    mendable.conversation_id = None
    await update.message.reply_text("Reset successful ✅")


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    print(f"Update {update} caused error {context.error}")
    logger.warning('Error "%s"', context.error)


def main():
    # Handle messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, send),
    )
    application.add_handler(CommandHandler("qa", send))
    application.add_handler(CommandHandler("reset", reset))
    application.add_error_handler(error)

    # Run the bot
    application.run_polling()


if __name__ == "__main__":
    main()
