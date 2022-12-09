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
        template = f"""You are a chatbot having a conversation with {username}. You try to give as accurate and thruthful answers as possible. 
        You cannot answer questions that need to know what date it is currently.
        
        You are not allowed to browse the internet. You don't knw what date it is. You cannot remind the user or perform actions on her behalf.

        If you don't know the answer, you can ask the human for more information or earnestly tell {username} that you don't know the answer. 
        If you cannot perform the requested action, clearly state so. If the action needs internet, suggest that the user use the /browse command. If the action requested needs scheduling, suggest the user use /schedule.

        Here is a summary of the conversation so far:
        {{summary}}

        Conversation:
        {{history}}
        {username}: {{human_input}}
        Chatbot:"""

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
