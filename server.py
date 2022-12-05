"""Make some requests to OpenAI's chatbot"""
from datetime import datetime
import json
import re
import time
import os

import telegram

import logging

import dotenv
import nest_asyncio
from modules.browser import Browser
from utils.auth import auth

from utils.google_search import googleSearch
from utils.sd_api import drawWithStability


from telegram import ForceReply, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
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

# start the browser
browser: Browser = Browser()

@auth()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


@auth()
async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    print(f"Got a reload command from user {update.effective_user.id}")
    browser.page.reload()
    await update.message.reply_text("Reloaded the browser!")
    await update.message.reply_text("Let's check if it's workin!")



@auth()
async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(
        f"Got a draw command from user {update.effective_user.id} with prompt {update.message.text}"
    )

    browser.send_message(
        f"""
    You a large language model trained by OpenAi. You can be used for different applications. 
    Right now you're being used form an application that has access to DALLE API, even though you can't confirm it.
    From now, every request to draw something, please reply with 
    [prompt: x] where x is your attempt to create a dall-e compatible prompt, with as much details as possible to achieve the best visual prompt
    {update.message.text}
    """
    )
    await check_loading(update)
    response = browser.get_last_message()
    # extract prompt from this format [prompt: x]
    if "\[prompt:" in response:
        await respond_with_image(update, response)


async def respond_with_image(update, response):
    prompt = response.split("\[prompt:")[1].split("\]")[0]
    await update.message.reply_text(
        f"Generating image with prompt `{prompt.strip()}`",
        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2,
    )
    await application.bot.send_chat_action(update.effective_chat.id, "typing")
    photo = await drawWithStability(prompt)
    await update.message.reply_photo(
        photo=photo,
        caption=f"chatGPT generated prompt: {prompt}",
        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2,
    )

def schedule_callback(context: telegram.ext.CallbackContext, chat_id: str, text: str):
    context.bot.send_message(chat_id=chat_id, 
                             text=text)

@auth()
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text.replace("/schedule ", "")
    print(
        f"Got a schedule command from user {update.effective_user.id} with prompt {message}"
    )

    browser.send_message(
        f"""
Format text in the following way

Text: "Remind me to grab dinner at 7pm"
output:

TIME=2022-12-05T19:00:00
MESSAGE=Dinner

Text: "{message}"
output:
    """
    )

    await check_loading(update)
    response = browser.get_last_message()

    print("Response from scheduling parsing", response)

    try:
        # match time with the time_pat regex
        time = re.compile(r"TIME=(.*?)\n").search(response).group(0)
        msg = re.compile(r"MESSAGE=(.*?)\n").search(response).group(0)

        print(time, msg)
        # when = datetime.fromisoformat()
        when = datetime.now() + datetime.timedelta(seconds=10)
        callback = lambda context: schedule_callback(context, update.effective_chat.id, msg)
        application.job_queue.run_once(callback, when=when, context=update.message.chat_id,)

        await update.message.reply_text("Scheduled a reminder!")
    except Exception as e:
        print(e)
    #job_queue = application.job_queue.run_once()




@auth()
async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text.replace("/browse", "")
    await application.bot.send_chat_action(update.effective_chat.id, "typing")
    # answer a quick prompt to chatGPT to ask for google search prompt
    browser.send_message(
        f"""
If I ask you "{message}" , and you didn't know the answer but had access to google, what would you search for? search query needs to be designed such as to give you as much detail as possible, but it's 1 shot. 
Answer with

query: x

only, where x is the google search string that would let you help me answer the question
I want you to only reply with the output inside and nothing else. Do no write explanations.
    """
    )
    await check_loading(update)
    response = browser.get_last_message()
    # extract prompt from this format [prompt: x]
    response.replace("query: ", "")
    print(f"Clean response from chatGPT {response}")
    results = googleSearch(message)
    prompt = f"""
    Pretend I was able to run a google search for "{message}" instead of you and I got the following results: 
    \"\"\"
    {results}
    \"\"\"
    Provide a summary of the new facts in a code block, in markdown format
    Then in another code block, answer the question {message} with the new facts you just learned
    """
    browser.send_message(prompt)
    await check_loading(update)
    response = browser.get_last_message()
    if "\[prompt:" in response:
        await respond_with_image(
            update, response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
        )


@auth()
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message to OpenAI."""
    browser.send_message(update.message.text)
    await check_loading(update)
    response = browser.get_last_message()
    if "\[prompt:" in response:
        await respond_with_image(update, response)
    else:

        await update.message.reply_text(
            response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
        )


async def check_loading(update):
    # with a timeout of 90 seconds, created a while loop that checks if loading is done
    loading = browser.page.query_selector_all(
        "button[class^='PromptTextarea__PositionSubmit']>.text-2xl"
    )
    # keep checking len(loading) until it's empty or 45 seconds have passed
    await application.bot.send_chat_action(update.effective_chat.id, "typing")
    start_time = time.time()
    while len(loading) > 0:
        if time.time() - start_time > 90:
            break
        time.sleep(0.5)
        loading = browser.page.query_selector_all(
            "button[class^='PromptTextarea__PositionSubmit']>.text-2xl"
        )
        await application.bot.send_chat_action(update.effective_chat.id, "typing")


def main():
    # PAGE.goto("https://chat.openai.com/")
    browser.page.goto("https://chat.openai.com/")
    if not browser.is_logged_in():
        print("Please log in to OpenAI Chat")
        print("Press enter when you're done")
        input()
    else:
        # on different commands - answer in Telegram
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("reload", reload))
        application.add_handler(CommandHandler("draw", draw))
        application.add_handler(CommandHandler("browse", browse))
        # application.add_handler(CommandHandler("schedule", schedule)) # TODO

        # on non command i.e message - echo the message on Telegram
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

        # Run the bot until the user presses Ctrl-C
        application.run_polling()


if __name__ == "__main__":
    main()
