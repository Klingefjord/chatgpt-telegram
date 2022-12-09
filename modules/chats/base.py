from abc import ABC, abstractmethod
from typing import Coroutine


class Chat(ABC):
    """The interface of a chatbot"""

    @abstractmethod
    async def send_message(
        self, message: str, typing: Coroutine = None, **kwargs
    ) -> str:
        raise NotImplementedError()
