import os
import time
from typing import Coroutine
from anyio import sleep
from playwright.async_api import async_playwright, ElementHandle
from telegram.helpers import escape_markdown


class ChatGPT:
    """
    ChatGPT API

    This class wraps a headless chrome browser instance that navigates to the chat.openai.com webpage.
    You will need to provide your OpenAI username and password for the bot to log in to the webpage. Do so at your own risk.

    OpenAI changes their website frequently, so this class may break at any time. The code should be simple enough for you to fix yourself though.

    usage:

    chat = ChatGPT(openai_username, openai_password)
    await chat.connect()
    await chat.login()
    response = await chat.send_message("Hello")
    print(response)
    """

    def __init__(self, openai_username: str, openai_password: str) -> None:
        self.openai_username = openai_username
        self.openai_password = openai_password
        self.is_logged_in = False
        self.is_ready = False

    async def __format_text(self, text_element: ElementHandle) -> str:
        """Format the text in the text element, removing code tags and escaping markdown"""

        #
        # the rest of this function tries to format code in the text
        #
        try:
            code_blocks = await text_element.query_selector_all("pre")
        except Exception as e:
            return "Server probably disconnected, try running /reset"

        if len(code_blocks) == 0:
            text = await text_element.inner_text()
            return escape_markdown(text, version=2)

        response = ""

        # replace <code> tags with backticks
        for child in await text_element.query_selector_all("p,pre"):
            tag = await child.get_property("tagName")

            if str(tag) == "PRE":
                code_container = await child.query_selector("code")
                text = await code_container.inner_text()
                response += f"\n\n```\n{escape_markdown(text, version=2)}\n```"
            else:
                text = await child.inner_html()
                response += escape_markdown(text, version=2)

        # remove any remaining <code> tags.
        response = response.replace("<code\>", "`")
        response = response.replace("</code\>", "`")

        return response

    async def __get_response(self):
        """Get the latest message from the webpage"""

        # get the latest response from the webpage.
        page_elements = await self.page.query_selector_all("div[class*='prose']")
        prose = page_elements[-1]

        # format the response
        response = await self.__format_text(prose)

        # return the formatted text.
        return response

    async def __click_through_modal(self):
        """Click through the welcome modal if it is present"""

        while True:
            next_button = self.page.locator("button", has_text="Next")
            done_button = self.page.locator("button", has_text="Done")

            if await done_button.is_visible():
                await done_button.click()
                break
            elif await next_button.is_visible():
                await next_button.click()
            else:
                break

            await sleep(1)

    async def __get_input_box(self):
        """Get the child textarea of `PromptTextarea__TextareaWrapper`"""
        return await self.page.query_selector("textarea")

    async def connect(self, headless=False, user_data_dir="/tmp/playwright"):
        """
        Connect to the webpage by creating a browser instance
        headless: whether to run the browser in headless mode
        """

        play = await async_playwright().start()
        context = await play.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36",
            headless=headless,
        )

        self.page = await context.new_page()

        # mark the browser as ready
        self.ready = True

    async def login(self, attempt=1, max_attempts=3):
        """Log in to OpenAI Chat"""

        if attempt >= max_attempts:
            raise Exception(f"Failed to login after {attempt} attempts")

        if not self.ready:
            raise Exception("Browser is not ready, use .connect() first")

        try:
            # navigate to the webpage
            await self.page.goto("https://chat.openai.com/")

            # check if we're already logged in
            if await self.__get_input_box() is not None:
                print("Already logged in")
                await self.__click_through_modal()
                return

            print("Logging in, attempt ", attempt)
            await sleep(1)

            # click on the login button
            login_button = self.page.locator("button", has_text="Log in")
            await login_button.click()
            await sleep(1)

            save = self.page.locator("button[value='default']", has_text="Continue")

            # fill in the email
            email = self.page.locator("input[id='username']")
            await email.fill(self.openai_username)
            await save.click()
            await sleep(1)

            # fill in the password
            password = self.page.locator("input[id='password']")
            await password.fill(self.openai_password)
            await save.click()
            await sleep(1)

            # the user should be logged in now. Otherwise, try again.
            if await self.__get_input_box() is None:
                return await self.login(attempt=attempt + 1)

            # There might be a modal blocking the screen that we need to click through.
            await self.__click_through_modal()

            self.is_logged_in = True
        except Exception as e:
            print("Error logging in. Taking screenshot.", e)
            await self.page.screenshot(path=f"login_fail_{attempt}.png")
            return await self.login(attempt=attempt + 1)

    async def send_message(
        self,
        message: str,
        typing_action: Coroutine = None,
        typing_action_interval=5,
        poll_interval=0.5,
        timeout=90,
    ):
        """
        Send a message to the webpage.

        message: the message to send
        typing_action: a coroutine that will be executed while the bot is typing every poll.
        poll_interval: how often to poll the webpage for a response in seconds.
        timeout: how long to wait for a response before giving up in seconds.
        """

        print("Sending chatgpt message...")

        box = await self.__get_input_box()
        await box.click()
        await box.fill(message)
        await box.press("Enter")

        #
        # wait for a response
        #
        start_time = time.time()

        last_poll = start_time

        while True:
            # simulate typing if needed.
            if typing_action is not None:
                if time.time() - last_poll > typing_action_interval:
                    last_poll = time.time()
                    await typing_action()

            # check if the page is loading.
            loading = await self.page.query_selector_all(
                "div[class*='prose'][class*='result-streaming']"
            )

            if not loading:
                break

            # time out after 90 seconds
            if time.time() - start_time > timeout:
                break

            # check again in after the piolling interval.
            await sleep(poll_interval)

        print(f"Got chatgpt response. Took ", time.time() - start_time, " seconds.")

        # return the response
        return await self.__get_response()
