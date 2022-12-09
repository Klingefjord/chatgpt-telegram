# I'm sorry, but I am not capable of checking in with you at a specific time.
# I am a text-based AI assistant and do not have the ability to check in with you in real-time.
# Is there something specific you need help with or have a question about?
# I would be happy to assist you to the best of my abilities.


import asyncio
from datetime import datetime, timedelta
from functools import partial
from typing import Coroutine
from langchain import OpenAI

from pydantic import BaseModel
from modules.chats.base import Chat
from telegram.ext import CallbackContext
from telegram.ext import JobQueue
from telegram.ext import ContextTypes


class Scheduler:
    """Singleton class for scheduling reminders"""

    def __init__(self, job_queue: JobQueue) -> None:
        self.date_format = "%A %m-%d-%y %H:%M"
        self.job_queue = job_queue
        self.parse_llm = OpenAI(max_tokens=256)
        self.response_llm = OpenAI(max_tokens=128, model_name="text-curie-001")

    @staticmethod
    async def callback(context: ContextTypes.DEFAULT_TYPE):
        job = context.job
        await context.bot.send_message(job.chat_id, text=job.data)

    async def call(self, llm: OpenAI, prompt: str) -> str:
        """Async wrapper around a LLM"""

        function = partial(llm, prompt)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, function)
        return response

    async def schedule(
        self,
        text: str,
        chat: Chat,
        username: str,
        user_id: str,
        chat_id: str,
        typing: Coroutine,
    ) -> str:
        now = datetime.now().strftime(self.date_format)

        #
        # get a time and reminder from a prompt from the user
        #
        prompt = f"""You are an excellent message parser. Parse a message to {username} based on a query.
        The response needs to be a JSON object and contain two keys, "time" and "message".

        EXAMPLE
        query: "Remind me to book a dinner for Ellie's birthday on Friday. Time right now is {now}."
        response: {"{"}
            "time": "Friday 12-01-01 19:00",
            "message": "Hi {username}! It's time to book a dinner for Ellie's birthday."
        {"}"}
        END OF EXAMPLE

        query: "{text}. Time right now is {now}."
        response: {"{"}"""

        response = await self.call(self.parse_llm, prompt)

        # extract the time and reminder from the response
        time = response.split('"time": "')[1].split('",')[0].strip()
        message = response.split('"message": "')[1].split('"')[0].strip()

        # convert the time to a datetime object
        time = datetime.strptime(time, self.date_format)

        #
        # schedule the reminder
        #
        self.job_queue.run_once(
            self.callback,
            when=time,
            data=message,
            chat_id=chat_id,
            user_id=user_id,
        )

        print(f"Scheduled job for {username} at {time}")

        #
        # send a confirmation message to the user
        #
        prompt = f"""You are a reminder chatbot AI. You are kind and succint.
        Tell the user that you have scheduled a reminder for them at {time}.

        {username}: {text}
        AI:"""

        await typing()

        response = await self.call(self.response_llm, prompt)
        return response

        return "Done"
