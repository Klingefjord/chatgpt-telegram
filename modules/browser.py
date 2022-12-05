
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
            user_data_dir="/tmp/playwright",
            headless=False,
        )

        self.page = await context.new_page()


    async def get_last_message(self):
        """Get the latest message"""
        page_elements = await self.page.query_selector_all("div[class*='ConversationItem__Message']")
        last_element = page_elements[-1]
        prose = last_element.query_selector(".prose")
        try:
            code_blocks = await prose.query_selector_all("pre")
        except Exception as e:
            response = "Server probably disconnected, try running /reset"
        if len(code_blocks) > 0:
            # get all children of prose and add them one by one to respons
            response = ""
            for child in await prose.query_selector_all("p,pre"):
                print(child.get_property("tagName"))
                if str(child.get_property("tagName")) == "PRE":
                    code_container = await child.query_selector(
                        "div[class*='CodeSnippet__CodeContainer']"
                    )
                    response += f"\n```\n{escape_markdown(code_container.inner_text(), version=2)}\n```"
                else:
                    # replace <code></code> formatting with ``
                    text = child.inner_html()
                    response += escape_markdown(text, version=2)
            response = response.replace("<code\>", "`")
            response = response.replace("</code\>", "`")
        else:
            response = escape_markdown(prose.inner_text(), version=2)
        return response

     
    async def __get_input_box(self):
        """Get the child textarea of `PromptTextarea__TextareaWrapper`"""
        return await self.page.query_selector("textarea")

    async def login(self, attempt=0):
        """Log in to OpenAI Chat. Try 3 times before giving up"""
        if attempt > 2:
            raise Exception("Failed to login")

        # check if we're already logged in
        await self.page.goto("https://chat.openai.com/")
        if await self.__get_input_box() is not None:
            print("Already logged in")
            return
        
        print("Logging in")

        # click on the login button        
        await self.page.locator("button", has_text='Log in').click()
        await sleep(1)

        save = await self.page.locator("button[value='default']", has_text='Continue')

        # fill in the email
        email = await self.page.locator("input[id='username']")
        await email.fill(os.getenv("OPEN_AI_USERNAME"))
        await save.click()
        await sleep(1)

        # fill in the password
        password = await self.page.locator("input[id='password']")
        await password.fill(os.getenv("OPEN_AI_PASSWORD"))
        await save.click()
        await time.sleep(5)

        # the user should be logged in now. Otherwise, try again.
        if self.__get_input_box() is None:
            return self.login(attempt=attempt+1)

    async def send_message(self, message):
        """Send a message to the webpage"""
        box = await self.__get_input_box()
        await box.click()
        await box.fill(message)
        await box.press("Enter")