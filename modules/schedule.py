import asyncio
from datetime import datetime
from functools import partial
from typing import Coroutine
from langchain import OpenAI
from telegram.ext import CallbackContext
from telegram.ext import JobQueue


class Scheduler:
    """Schedule reminders for the user by extracting time and date and adding a task to the JobQueue.

    Unfortunately, reminders are not persisted across restarts."""

    def __init__(self, job_queue: JobQueue) -> None:
        self.date_format = "%A %m-%d-%y %H:%M"
        self.job_queue = job_queue
        self.parse_llm = OpenAI(max_tokens=256)
        self.response_llm = OpenAI(max_tokens=128, model_name="text-curie-001")

    @staticmethod
    async def callback(context: CallbackContext):
        job = context.job

        await context.bot.send_message(
            job.chat_id,
            text=job.data,
        )

    async def call(self, llm: OpenAI, prompt: str) -> str:
        """Async wrapper around a LLM"""

        function = partial(llm, prompt)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, function)
        return response

    async def schedule(
        self,
        text: str,
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

        "time" is formatted using "A %m-%d-%y %H:%M".

        EXAMPLE
        query: "Remind me to book a dinner for Ellie's birthday on Friday. Time right now is Thursday 12-01-20 17:00"
        response: {"{"}
            "time": "Friday 12-01-21 19:00",
            "message": "Hi {username}! It's time to book a dinner for Ellie's birthday."
        {"}"}

        query: "Check in with me at 3pm. Time right now is Wednesday 01-20-18 08:22."
        response: {"{"}
            "time": "Friday 01-20-18 15:00",
            "message": "Hi {username}, how are you doing?"
        {"}"}

        query: "Send a message to me tomorrow this time of day. Time right now is Monday 12-20-22 13:08."
        response: {"{"}
            "time": "Tuesday 12-20-22 13:08",
            "message": "Hello {username}."
        {"}"}
        END OF EXAMPLE

        query: "{text}. Time right now is {now}."
        response: {"{"}"""

        response = await self.call(self.parse_llm, prompt)

        try:
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
        except Exception as e:
            print("Failed to schedule job: ", e)
            response = await self.call(
                self.response_llm,
                f"""Asssistant is a large language model trained by OpenAI. It is helpful at a wide range of tasks.
                Assistant is designed to schedule reminders on behalf of the user.
                Assistant failed to schedule a reminder for {username}.
                
                Assistant:""",
            )
            return response

        print(f"Scheduled job for {username} at {time}")

        #
        # send a confirmation message to the user
        #
        prompt = f"""Assistant is a large language model trained by OpenAI.

        Assistant is designed to be helpful at a wide range of tasks. 
        Assistant can schedule reminders on behalf of the user.

        {username}: {text}
        Assistant:"""

        await typing()

        response = await self.call(self.response_llm, prompt)
        return response
