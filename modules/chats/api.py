from abc import ABC, abstractmethod
from functools import partial
import os
import time
import asyncio
from anyio import sleep
from langchain import LLMChain, OpenAI, PromptTemplate
from playwright.async_api import async_playwright, ElementHandle
from typing import Coroutine, List, Tuple
from telegram import Chat
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes
from modules.memory import CHAT_KEY, SUMMARY_KEY, AutoSummaryMemory


class APIChat(Chat):
    chain: LLMChain
    """The LLMChain that is used to generate responses"""

    def __init__(
        self,
        username: str,
        context: ContextTypes.DEFAULT_TYPE = None,
    ) -> None:
        template = f"""
Assistant is a large language model trained by OpenAI on data up until 2021.
Assistant is designed to be able to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics. As a language model, Assistant is able to generate human-like text based on the input it receives, allowing it to engage in natural-sounding conversations and provide responses that are coherent and relevant to the topic at hand.
Assistant is constantly learning and improving, and its capabilities are constantly evolving. It is able to process and understand large amounts of text, and can use this knowledge to provide accurate and informative responses to a wide range of questions. It tells the user when it does not know a question, or ask the user clarifying questions. It does not know the current date and cannot answer questions about current events.
{{summary}}

Conversation:
{{history}}
Human: {{human_input}}
Assistant:"""

        prompt = PromptTemplate(
            input_variables=["history", "summary", "human_input"],
            template=template,
        )

        #
        # Load the memory from the context.
        #
        buffer = ""
        summary = ""

        if context is not None:
            if CHAT_KEY in context.chat_data:
                buffer = context.chat_data[CHAT_KEY]
            if SUMMARY_KEY in context.chat_data:
                summary = context.chat_data[SUMMARY_KEY]

        memory = AutoSummaryMemory(
            memory_key="history",
            summary_key="summary",
            buffer=buffer,
            summary=summary,
        )

        #
        # set up the LLM chain.
        #
        self.chain = LLMChain(
            llm=OpenAI(),
            prompt=prompt,
            verbose=True,
            memory=memory,
        )

    async def call(self, message: str) -> str:
        """Async wrapper around the LLM"""
        function = partial(self.chain.predict, human_input=message)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, function)

        return response

    async def send_message(
        self,
        message: str,
        typing: Coroutine = None,
        context: ContextTypes.DEFAULT_TYPE = None,
        **kwargs,
    ):
        if typing:
            await typing()

        # call the language model.
        response = await self.call(message)

        # perist the result.
        self.chain.memory.sync_context(context)

        # return the response.
        return response
