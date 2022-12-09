from telegram import Update
from telegram.ext import ContextTypes, PicklePersistence

# the persistence object
persistence = PicklePersistence(filepath="./data/data")

KEY = "history"


def persist_message(update: Update, context: ContextTypes.DEFAULT_TYPE, response: str):
    """
    Persist a message to the chat data.
    """

    # create the history array if not present
    if not KEY in context.chat_data:
        context.chat_data[KEY] = []

    # save the message to history
    context.chat_data[KEY].append((update.effective_user.username, update.message.text))

    # save the response to history
    context.chat_data[KEY].append(("AI", response))


async def clear_history(context: ContextTypes.DEFAULT_TYPE):
    """
    Clear the chat data.
    """

    context.chat_data[KEY] = []

    # waits for the db to update
    await context.refresh_data()


def get_history(context: ContextTypes.DEFAULT_TYPE):
    """
    Get the chat history.
    """

    if KEY in context.chat_data:
        return context.chat_data[KEY]
    return []
