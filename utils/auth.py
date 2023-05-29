from functools import wraps
import dotenv
import os

dotenv.load_dotenv()

allowed_chat_ids = os.getenv("ALLOWED_CHAT_IDS").split(",")


def auth():
    """Verify that the user is allowed to use the bot."""

    def decorator(func: callable):
        @wraps(func)
        async def wrapper(update, context):
            if str(update.message.chat_id) in allowed_chat_ids:
                await func(update, context)
            else:
                await update.message.reply_text(
                    "You are not authorized to use this bot"
                )

        return wrapper

    return decorator
