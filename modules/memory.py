from typing import Any, Dict, List
from langchain import OpenAI
from langchain.chains.base import Memory
from pydantic import BaseModel


def _get_prompt_input_key(inputs: Dict[str, Any], memory_variables: List[str]) -> str:
    # "stop" is a special key that can be passed as input but is not used to
    # format the prompt.
    prompt_input_keys = list(set(inputs).difference(memory_variables + ["stop"]))
    if len(prompt_input_keys) != 1:
        raise ValueError(f"One input key expected got {prompt_input_keys}")
    return prompt_input_keys[0]


class AutoSummaryMemory(Memory, BaseModel):
    """
    A memory that summarizes the conversation when the conversation approaches the token limit.
    """

    buffer: str = ""
    memory_key: str = "history"  #: :meta private:
    summary_token_limit: int = 512
    summary_token_threshold: int = 1024
    llm = OpenAI(max_tokens=summary_token_limit)

    @property
    def memory_variables(self) -> List[str]:
        """Will always return list of memory variables.

        :meta private:
        """
        return [self.memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        """Return history buffer."""
        return {self.memory_key: self.buffer}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save context from this conversation to buffer."""
        prompt_input_key = _get_prompt_input_key(inputs, self.memory_variables)
        if len(outputs) != 1:
            raise ValueError(f"One output key expected, got {outputs.keys()}")
        human = "Human: " + inputs[prompt_input_key]
        ai = "AI: " + outputs[list(outputs.keys())[0]]
        self.buffer += "\n" + "\n".join([human, ai])
