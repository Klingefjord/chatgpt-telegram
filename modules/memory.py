from typing import Any, Dict, List
from langchain import BasePromptTemplate, LLMChain, OpenAI
from langchain.chains.conversation.prompt import SUMMARY_PROMPT
from langchain.chains.base import Memory
from telegram.ext import ContextTypes

# the history of the conversation, stored as a string as per memory.
CHAT_KEY = "history"
# the summary of the conversation, stored as a string as per memory.
SUMMARY_KEY = "summary"


async def clear_history(context: ContextTypes.DEFAULT_TYPE):
    """
    Clear the chat data.
    """

    context.chat_data[CHAT_KEY] = ""
    context.chat_data[SUMMARY_KEY] = ""

    # waits for the db to update
    await context.refresh_data()


def _get_prompt_input_key(inputs: Dict[str, Any], memory_variables: List[str]) -> str:
    # "stop" is a special key that can be passed as input but is not used to
    # format the prompt.
    prompt_input_keys = list(set(inputs).difference(memory_variables + ["stop"]))
    if len(prompt_input_keys) != 1:
        raise ValueError(f"One input key expected got {prompt_input_keys}")
    return prompt_input_keys[0]


class AutoSummaryMemory(Memory):
    """
    A memory that automatically summarizes the conversation when the buffer is getting too large.
    """

    buffer: str
    summary: str

    memory_key: str = "history"  #: :meta private:
    summary_key: str = "summary"  #: :meta private:

    buffer_max_len: int = 512  # how many words before we summarize the conversation.
    summary_token_limit: int = 256  # how long the summary is allowed to be

    prompt: BasePromptTemplate = SUMMARY_PROMPT
    llm = OpenAI(max_tokens=summary_token_limit)

    @property
    def memory_variables(self) -> List[str]:
        """Will always return list of memory variables.

        :meta private:
        """
        return [self.memory_key, self.summary_key]

    def sync_context(self, context: ContextTypes.DEFAULT_TYPE):
        """Sync context with memory."""
        context.chat_data[CHAT_KEY] = self.buffer
        context.chat_data[SUMMARY_KEY] = self.summary

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        """Return history and summary."""
        return {
            self.memory_key: self.buffer,
            self.summary_key: self.summary,
        }

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save context from this conversation to buffer."""
        prompt_input_key = _get_prompt_input_key(inputs, self.memory_variables)

        if len(outputs) != 1:
            raise ValueError(f"One output key expected, got {outputs.keys()}")

        human = "Human: " + inputs[prompt_input_key]
        ai = "Assistant: " + outputs[list(outputs.keys())[0]]

        # add the new lines to the buffer.
        self.buffer += "\n" + "\n".join([human, ai])

        # summarize the temporary buffer if it is too long.
        if len(self.buffer) > self.buffer_max_len:
            # summarize the buffer.
            chain = LLMChain(llm=self.llm, prompt=self.prompt)
            self.summary = chain.predict(summary=self.summary, new_lines=self.buffer)
            self.buffer = ""
