import os
import time
from anyio import sleep
from playwright.async_api import async_playwright
from telegram import Update
from telegram.helpers import escape, escape_markdown


class Browser:
    def __init__(self, user_id: str) -> None:
        """Create a browser instance for a user"""
        self.user_id = user_id

    async def connect(self):
        """Connect to the webpage"""

        play = await async_playwright().start()
        context = await play.chromium.launch_persistent_context(
            user_data_dir=f"/tmp/playwright_{self.user_id}",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36",
            headless=True,
        )

        self.page = await context.new_page()

    async def get_last_message(self):
        """Get the latest message"""
        page_elements = await self.page.query_selector_all("div[class*='prose']")
        prose = page_elements[-1]
        # prose = await last_element.query_selector(".prose")

        #
        # the rest of this function tries to format code in the text
        #
        try:
            code_blocks = await prose.query_selector_all("pre")
        except Exception as e:
            return "Server probably disconnected, try running /reset"

        if len(code_blocks) == 0:
            text = await prose.inner_text()
            return escape_markdown(text, version=2)

        response = ""
        # get all children of prose and add them one by one to respons
        for child in await prose.query_selector_all("p,pre"):
            print(child.get_property("tagName"))
            if str(child.get_property("tagName")) == "PRE":
                code_container = await child.query_selector(
                    "div[class*='CodeSnippet__CodeContainer']"
                )
                text = await code_container.inner_text()
                response += f"\n```\n{escape_markdown(text, version=2)}\n```"
            else:
                # replace <code></code> formatting with ``
                text = await child.inner_html()
                response += escape_markdown(text, version=2)
        response = response.replace("<code\>", "`")
        response = response.replace("</code\>", "`")

        return response

    async def click_through_modal(self):
        """Click through the welcome modal, if it is present"""

        print("Clicking through modal...")

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

    async def login(self, attempt=0):
        """Log in to OpenAI Chat. Try 3 times before giving up"""
        if attempt > 2:
            raise Exception("Failed to login")

        # navigate to the webpage
        await self.page.goto("https://chat.openai.com/")

        # check if we're already logged in
        if await self.__get_input_box() is not None:
            print("Already logged in")
            await self.click_through_modal()
            return

        print("Logging in, attempt ", attempt + 1)
        await sleep(1)

        # click on the login button
        login_button = self.page.locator("button", has_text="Log in")
        await login_button.click()
        await sleep(1)

        save = self.page.locator("button[value='default']", has_text="Continue")

        # fill in the email
        email = self.page.locator("input[id='username']")
        await email.fill(os.getenv("OPEN_AI_USERNAME"))
        await save.click()
        await sleep(1)

        # fill in the password
        password = self.page.locator("input[id='password']")
        await password.fill(os.getenv("OPEN_AI_PASSWORD"))
        await save.click()
        await sleep(2)

        # the user should be logged in now. Otherwise, try again.
        if await self.__get_input_box() is None:
            return self.login(attempt=attempt + 1)

        # There might be a modal blocking the screen that we need to click through.
        await self.click_through_modal()

    async def send_message(self, message):
        """Send a message to the webpage"""
        box = await self.__get_input_box()
        await box.click()
        await box.fill(message)
        await box.press("Enter")
