import contextlib
from typing import Dict, Any
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import TextArea, Button, TabPane, TabbedContent, Static
from textual.reactive import reactive
from heare.developer.user_interface import UserInterface
from heare.developer.sandbox import SandboxMode


class ToolUsagePane(Container):
    def compose(self):
        yield TextArea(id="tool-usage-area", classes="tool-usage")
        with Horizontal():
            yield Button("Confirm", id="confirm-tool-usage", variant="primary")
            yield Button("Deny", id="deny-tool-usage", variant="error")


class ToolResultPane(VerticalScroll):
    def compose(self):
        yield Static(id="tool-result-content", expand=True)


class Sidebar(Container):
    def compose(self):
        with TabbedContent():
            with TabPane("Tool Usage"):
                yield ToolUsagePane()
            with TabPane("Tool Result"):
                yield ToolResultPane()


class TerminalUserInterface(UserInterface):
    def __init__(self, app, sandbox_mode: SandboxMode):
        self.app = app
        self.sandbox_mode = sandbox_mode
        self.user_input = reactive("")
        self.waiting_for_input = reactive(False)
        self.waiting_for_permission = reactive(False)
        self.permission_result = False

    def handle_system_message(self, message: str) -> None:
        self.app.append_to_conversation("system", message)

    def handle_assistant_message(self, message: str) -> None:
        self.app.append_to_conversation("assistant", message)

    def permission_callback(
        self,
        action: str,
        resource: str,
        sandbox_mode: SandboxMode,
        action_arguments: Dict | None,
    ) -> bool:
        formatted_params = (
            "\n".join([f"  {key}: {value}" for key, value in action_arguments.items()])
            if action_arguments
            else ""
        )
        content = (
            f"Action: {action}\n"
            f"Resource: {resource}\n"
            f"Arguments:\n{formatted_params}\n"
            "Allow this action? (Confirm/Deny)"
        )

        self.app.update_tool_usage(content)
        self.app.show_sidebar()

        # Use a reactive variable to wait for user input
        self.waiting_for_permission = True

        # Wait for user input
        while self.waiting_for_permission:
            self.app.run_async(self.app.process_messages())

        return self.permission_result

    def permission_rendering_callback(
        self,
        action: str,
        resource: str,
        action_arguments: Dict | None,
    ) -> None:
        pass

    def handle_tool_use(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
    ):
        formatted_params = "\n".join(
            [f"  {key}: {value}" for key, value in tool_params.items()]
        )
        content = (
            f"Action: {tool_name}\n"
            f"Resource: {tool_params.get('path', 'N/A')}\n"
            f"Arguments:\n{formatted_params}"
        )
        self.app.update_tool_usage(content)
        self.app.show_sidebar()

    def handle_tool_result(self, name: str, result: Dict[str, Any]) -> None:
        # Get the content based on tool type
        content = (
            result["content"]
            if name not in ["read_file", "write_file", "edit_file"]
            else "File operation completed"
        )

        # Format the result to show both the command and output
        formatted_result = (
            f"Tool Command: {name}\n"
            f"Parameters: {result.get('params', 'N/A')}\n"
            f"\nOutput:\n{content}"
        )

        self.app.update_tool_result(formatted_result)
        self.app.show_sidebar(tab="Tool Result")

    def get_user_input(self, prompt: str = "") -> str:
        # self.app.append_to_conversation("prompt", prompt)

        # Use a reactive variable to wait for user input
        self.waiting_for_input = True
        self.user_input = ""

        # Wait for user input
        while self.waiting_for_input:
            self.app.run_async(self.app.process_messages())

        return self.user_input

    def handle_user_input(self, user_input: str):
        self.app.append_to_conversation("human", user_input)

    def status(
        self, message: str, spinner: str = None
    ) -> contextlib.AbstractContextManager:
        return contextlib.AbstractContextManager()

    def display_token_count(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        total_cost: float,
    ) -> None:
        content = (
            f"Token Count:\n"
            f"Prompt: {prompt_tokens}\n"
            f"Completion: {completion_tokens}\n"
            f"Total: {total_tokens}\n"
            f"Cost: ${round(total_cost, 2)}"
        )
        self.app.append_to_conversation("token_count", content)

    def display_welcome_message(self) -> None:
        welcome_message = (
            "Welcome to the Heare Developer Terminal, your personal coding assistant.\n"
            "For multi-line input, start with '{' on a new line, enter your content, and end with '}' on a new line."
        )
        self.app.append_to_conversation("welcome", welcome_message)
