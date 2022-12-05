
import os
import time
from playwright.sync_api import sync_playwright
from telegram import Update
from telegram.helpers import escape, escape_markdown

class Browser:

    def __init__(self, user_id: str) -> None:
        """Create a browser instance for a user"""
        play = sync_playwright().start()
        browser = play.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright",
            headless=True,
        )

        self.page = browser.new_page()
        self.user_id = user_id


    def get_last_message(self):
        """Get the latest message"""
        page_elements = self.page.query_selector_all("div[class*='ConversationItem__Message']")
        last_element = page_elements[-1]
        prose = last_element.query_selector(".prose")
        try:
            code_blocks = prose.query_selector_all("pre")
        except Exception as e:
            response = "Server probably disconnected, try running /reset"
        if len(code_blocks) > 0:
            # get all children of prose and add them one by one to respons
            response = ""
            for child in prose.query_selector_all("p,pre"):
                print(child.get_property("tagName"))
                if str(child.get_property("tagName")) == "PRE":
                    code_container = child.query_selector(
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

     
    def __get_input_box(self):
        """Get the child textarea of `PromptTextarea__TextareaWrapper`"""
        return self.page.query_selector("textarea")

    def login(self, attempt=0):
        """Log in to OpenAI Chat. Try 3 times before giving up"""
        if attempt > 2:
            raise Exception("Failed to login")

        # check if we're already logged in
        self.page.goto("https://chat.openai.com/")
        if self.__get_input_box() is not None:
            print("Already logged in")
            return
        
        print("Logging in")

        # click on the login button        
        self.page.locator("button", has_text='Log in').click()
        time.sleep(3)

        save = self.page.locator("button[value='default']", has_text='Continue')

        # fill in the email
        email = self.page.locator("input[id='username']")
        email.fill(os.getenv("OPEN_AI_USERNAME"))
        save.click()
        time.sleep(1)

        # fill in the password
        password = self.page.locator("input[id='password']")
        password.fill(os.getenv("OPEN_AI_PASSWORD"))
        save.click()
        time.sleep(5)

        # the user should be logged in now. Otherwise, try again.
        if self.__get_input_box() is None:
            return self.login(attempt=attempt+1)


    async def check_loading(self, update: Update, typing_func: callable):
        # with a timeout of 90 seconds, created a while loop that checks if loading is done
        loading = self.page.query_selector_all(
            "button[class^='PromptTextarea__PositionSubmit']>.text-2xl"
        )
        # keep checking len(loading) until it's empty or 45 seconds have passed
        await typing_func()
        start_time = time.time()
        while len(loading) > 0:
            if time.time() - start_time > 90:
                break
            time.sleep(0.5)
            loading = self.page.query_selector_all(
                "button[class^='PromptTextarea__PositionSubmit']>.text-2xl"
            )
            await typing_func()

    def send_message(self, message):
        """Send a message to the webpage"""
        box = self.__get_input_box()
        box.click()
        box.fill(message)
        box.press("Enter")