import contextlib
from typing import List

from rich.status import Status

from heare.developer.context import AgentContext
from heare.developer.models import MODEL_MAP
from .framework import tool
from heare.developer.user_interface import UserInterface


@tool
def agent(
    context: "AgentContext", prompt: str, tool_names: List[str], model: str = None
):
    """Run a prompt through a sub-agent with a limited set of tools.
    Use an agent when you believe that the action desired will require multiple steps, but you do not
    believe the details of the intermediate steps are important -- only the result.
    The sub-agent will take multiple turns and respond with a result to the query.
    When selecting this tool, the model should choose a list of tools (by tool name)
    that is the likely minimal set necessary to achieve the agent's goal.
    Do not assume that the user can see the response of the agent, and summarize it for them.
    Do not indicate in your response that you used a sub-agent, simply present the results.

    Args:
        prompt: the initial prompt question to ask the
        tool_names: a list of tool names from the existing tools to provide to the sub-agent. this should be a subset!
        model: optional model alias to use for the sub-agent. Supported aliases:
            - "light": Use Claude 3.5 Haiku - faster and more cost-effective for simple tasks like
                       information retrieval, basic formatting, or straightforward reasoning
            - "smart": Use Claude 3.7 Sonnet - better for complex tasks requiring deeper reasoning,
                       detailed analysis, and more sophisticated responses

              If not provided or invalid, uses the parent context's model.
    """
    from heare.developer.agent import run

    with context.user_interface.status(f"Initiating sub-agent: {prompt}") as status:
        ui = CaptureInterface(parent=context.user_interface, status=status)

        # Create a sub-agent context with the current context as parent
        sub_agent_context = context.with_user_interface(ui)

        # Handle the model parameter if provided
        if model:
            # Define model aliases to model keys in MODEL_MAP
            model_aliases = {
                "light": "haiku",  # Faster, more cost-effective model
                "smart": "sonnet-3.7",  # More capable for complex reasoning
            }

            # Check if the provided model alias is valid
            if model in model_aliases:
                # Get the model key from aliases
                model_key = model_aliases[model]

                # Get the model spec from MODEL_MAP
                if model_key in MODEL_MAP:
                    # Update the sub_agent_context with the model spec from MODEL_MAP
                    sub_agent_context.model_spec = MODEL_MAP[model_key]

        try:
            # Run the agent with single response mode
            chat_history = run(
                agent_context=sub_agent_context,
                initial_prompt=prompt,
                single_response=True,
                tool_names=tool_names,
            )

            # Make sure the chat history is flushed in case run() didn't do it
            # (this can happen if there's an exception in run())
            sub_agent_context.flush(chat_history)

            # Get the final assistant message from chat history
            for message in reversed(chat_history):
                if message["role"] == "assistant":
                    # Handle both string and list content formats
                    if isinstance(message["content"], str):
                        return message["content"]
                    elif isinstance(message["content"], list):
                        # Concatenate all text blocks
                        return "".join(
                            block.text
                            for block in message["content"]
                            if hasattr(block, "text")
                        )

            return "No response generated"
        except Exception:
            # If there's an exception, still try to flush any partial chat history
            if "chat_history" in locals() and chat_history:
                sub_agent_context.flush(chat_history)
            # Re-raise the exception
            raise


class CaptureInterface(UserInterface):
    def get_user_input(self, prompt: str = "") -> str:
        pass

    def display_welcome_message(self) -> None:
        pass

    def status(
        self, message: str, spinner: str = None, update=False
    ) -> contextlib.AbstractContextManager:
        if update:
            self._status.update(message, spinner=spinner or "aesthetic")
        return self._status

    def __init__(self, parent: UserInterface, status: Status) -> None:
        self.output = []
        self.parent = parent
        self._status = status

    def handle_system_message(self, message):
        self.output.append(message)

    def handle_user_input(self, message):
        self.output.append(message)

    def handle_assistant_message(self, message):
        self.output.append(message)

    def handle_tool_use(self, tool_name, tool_input):
        message = f"Using tool {tool_name} with input {tool_input}"
        self.status(message, update=True)
        self.output.append(message)

    def handle_tool_result(self, tool_name, result):
        self.output.append(f"Tool {tool_name} result: {result}")

    def display_token_count(
        self, prompt_tokens, completion_tokens, total_tokens, total_cost
    ):
        pass

    def permission_callback(self, operation, path, sandbox_mode, action_arguments):
        return True

    def permission_rendering_callback(self, operation, path, action_arguments):
        return True
