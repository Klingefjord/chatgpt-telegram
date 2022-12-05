import os
from revChatGPT.revChatGPT import Chatbot

config = {
    "Authorization": os.getenv("OPENAI_API_KEY"),
    "session_token": os.getenv("SESSION_TOKEN"),
}


class ChatbotWrapper:
    def __init__(self) -> None:
        self.chatbot = Chatbot(config, conversation_id="oliver")
        self.chatbot.reset_chat()
        self.chatbot.refresh_session()

    def send_message(self, message):
        try:
            response = self.chatbot.get_chat_response(message)
            return response["message"]
        except Exception as e:
            print(e)
            return "Sorry, I'm having some issues right now"
