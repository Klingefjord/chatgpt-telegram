
from functools import wraps
import os

if os.environ.get("TELEGRAM_USER_ID"):
    USER_ID = int(os.environ.get("TELEGRAM_USER_ID"))

def auth():
    """Verify that the user is allowed to use the bot."""
    def decorator(func: callable):
        @wraps(func)
        async def wrapper(update, context):
            if update.effective_user.id == USER_ID:
                await func(update, context)
            else:
                await update.message.reply_text(
                    "You are not authorized to use this bot"
                )

        return wrapper

    return decorator
