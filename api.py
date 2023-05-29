import aiohttp
from pydantic import BaseModel


class Mendable(BaseModel):
    """Mendable API"""

    api_key: str
    conversation_id: str | None = None
    history: list[dict] = []

    async def _start_conversation(self) -> str:
        """Start a Mendable conversation"""

        data = {"api_key": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.mendable.ai/v0/newConversation", json=data
            ) as response:
                response_data = await response.json()
                return response_data["conversation_id"]

    async def call(self, query: str) -> dict[str, str]:
        """Call the Mendable API"""

        if self.conversation_id is None:
            self.conversation_id = await self._start_conversation()

        data = {
            "question": query,
            "shouldStream": False,
            "conversation_id": self.conversation_id,
            "history": self.history,
            "api_key": self.api_key,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.mendable.ai/v0/mendableChat", json=data
            ) as response:
                response_data = await response.json()
                response_text = response_data["answer"]["text"]
                sources = response_data["sources"][:3]
                self.history.append({"prompt": query, "response": response_text})

                if len(sources) > 0:
                    response_text += "\n\n"
                    response_text += "\n".join([s["link"] for s in sources])

                return response_text
