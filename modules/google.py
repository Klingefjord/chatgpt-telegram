from typing import Coroutine
from serpapi import GoogleSearch
from modules.chat import Chat
from telegram.ext import ContextTypes
import json
import dotenv

dotenv.load_dotenv()


class Google:
    """Allow the user to Google for answers by exposing the SerpAPI and summarizing the results with a language model."""

    def __init__(self, api_key) -> None:
        self.api_key = api_key

    async def google(
        self,
        text: str,
        chat: Chat,
        typing: Coroutine,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> str:
        """Get the response from the webpage, summarized by the ChatGPT api"""

        if typing:
            await typing()

        response = await chat.send_message(
            f"""If I ask you "{text}", and you didn't know the answer but had access to google, what would you search for? search query needs to be designed such as to give you as much detail as possible.
            
            Answer with x only, where x is the google search string that would let you help me answer the question.
            I want you to only reply with the output inside and nothing else. Do no write explanations or anything else.

            Query:""",
            typing=typing,
            context=context,
        )

        # send the google search query to Google:
        if typing:
            await typing()

        # search google for the query
        results = self.__google_search(response)

        # create a prompt for summarizing the google result
        prompt = f"""
        Pretend I was able to run a google search for "{text}" instead of you and I got the following results: 
        \"\"\"
        {results}
        \"\"\"
        Provide a answer to the following, cleanly formatted:
        
        {text}
        """

        return await chat.send_message(
            prompt,
            context=context,
            typing=typing,
        )

    def __google_search(self, query):
        """Perform the google search using SerpAPI"""

        params = {
            "q": query,
            "hl": "en",
            "gl": "de",
            "api_key": self.api_key,
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        print(f"Got google search results for {query}")
        parsed_response = self.__parse_response(query, results)
        print(parsed_response)
        return parsed_response

    def __parse_response(self, query, response_dict):
        """Extract the most relevant information from the response"""

        textual_response = f"Search results for `{query}`:\n"

        if "questions_and_answers" in response_dict:
            textual_response += "Questions and Answers:\n"
            for question_and_answer in response_dict["questions_and_answers"]:
                textual_response += f"""
                Q: {question_and_answer.get('question', 'NA')}
                A: {question_and_answer.get('answer', 'NA')}
                """

        if "answer_box" in response_dict:
            textual_response += f"Answer Box: {json.dumps(response_dict['answer_box'])}"

        if "organic_results" in response_dict:
            textual_response += "Organic Results:\n"
            for organic_result in response_dict["organic_results"]:
                textual_response += f"""
            Title: {organic_result.get('title', 'NA')}
            Snippet: {organic_result.get('snippet', 'NA')}
            """

        if "knowledge_graph" in response_dict:
            textual_response += (
                f"Knowledge Graph: {json.dumps(response_dict['knowledge_graph'])}"
            )

        return (
            textual_response[:500] + "..."
            if len(textual_response) > 500
            else textual_response
        )
