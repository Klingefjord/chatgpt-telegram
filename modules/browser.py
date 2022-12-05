
from playwright.sync_api import sync_playwright
from telegram.helpers import escape, escape_markdown

class Browser:
    def __init__(self) -> None:
        # Open the webpage
        play = sync_playwright().start()
        browser = play.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright",
            headless=False,
        )
        self.page = browser.new_page()

    def get_last_message(self):
        """Get the latest message"""
        page_elements = self.page.query_selector_all("div[class*='ConversationItem__Message']")
        last_element = page_elements[-1]
        prose = last_element.query_selector(".prose")
        try:
            code_blocks = prose.query_selector_all("pre")
        except AttributeError as e:
            response = "Server probably disconnected, try running /reload"
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
                    # replace all <code>x</code> things with `x`
                    text = child.inner_html()
                    response += escape_markdown(text, version=2)
            response = response.replace("<code\>", "`")
            response = response.replace("</code\>", "`")
        else:
            response = escape_markdown(prose.inner_text(), version=2)
        return response

     
    def get_input_box(self):
        """Get the child textarea of `PromptTextarea__TextareaWrapper`"""
        return self.page.query_selector("textarea")

    def is_logged_in(self):
        """See if we have a textarea with data-id='root'"""
        return self.get_input_box() is not None

    def send_message(self, message):
        """Send a message to the webpage"""
        box = self.get_input_box()
        box.click()
        box.fill(message)
        box.press("Enter")