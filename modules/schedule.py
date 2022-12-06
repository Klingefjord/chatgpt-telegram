# I'm sorry, but I am not capable of checking in with you at a specific time.
# I am a text-based AI assistant and do not have the ability to check in with you in real-time.
# Is there something specific you need help with or have a question about?
# I would be happy to assist you to the best of my abilities.


from datetime import datetime
from modules.chat_gpt import ChatGPT


class Scheduler:
    def needs_scheduling(self, text: str):
        """Check if the response needs scheduling by looking at keywords in the model"""

        text = text.lower()

        cue_count = 0
        if "'I'm sorry" in text:
            cue_count += 1

        if "time" in text:
            cue_count += 1

        if "real-time" in text:
            cue_count += 1

        if "date" in text:
            cue_count += 1

        if "schedule" in text:
            cue_count += 1

        if cue_count >= 3:
            print(f"Looks like prompt needs scheduling:\n\n{text}")
            return True

    async def schedule(self, api: ChatGPT, text: str) -> str:
        now = datetime.utcnow()

        prompt = f"""
        Fill in Reminder and Time like the following example:

        Q: Remind me to book a dinner on Friday. Time right now is {datetime.strptime(str, '%A %m-%d-%y %H:%M')}
        Ansert: Book a dinner on Friday :
        Time: Friday 12-01-01 19:00

        ----

        Time: {now}
        """
