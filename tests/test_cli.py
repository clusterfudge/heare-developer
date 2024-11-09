from heare.developer.user_interface import UserInterface
from heare.developer.sandbox import SandboxMode


class TestUserInterface(UserInterface):
    def __init__(self):
        self.next_input = ""
        self.messages = []

    def handle_assistant_message(self, message: str) -> None:
        self.messages.append(("assistant", message))

    def handle_system_message(self, message: str) -> None:
        self.messages.append(("system", message))

    def permission_callback(
        self,
        action: str,
        resource: str,
        sandbox_mode: SandboxMode,
        action_arguments: dict | None,
    ) -> bool:
        response = self.get_user_input(f"Allow {action} on {resource}? [y/n] ")
        # Take the last line of input for the y/n response
        last_line = response.strip().split("\n")[-1].lower()
        return last_line == "y"

    def handle_tool_use(self, tool_name: str, tool_params: dict) -> bool:
        return True

    def handle_tool_result(self, name: str, result: dict) -> None:
        pass

    def get_user_input(self, prompt: str = "") -> str:
        result = self.next_input
        return result

    def handle_user_input(self, user_input: str) -> str:
        return user_input

    def display_token_count(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        total_cost: float,
    ) -> None:
        pass

    def display_welcome_message(self) -> None:
        pass

    def status(self, message: str, spinner: str = None):
        class NoOpContextManager:
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return NoOpContextManager()


def test_permission_check_single_line():
    ui = TestUserInterface()
    ui.next_input = "y"
    result = ui.permission_callback(
        "read", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE, None
    )
    assert result


def test_permission_check_multi_line():
    ui = TestUserInterface()
    ui.next_input = "This is a\nmulti-line\ninput\ny"
    result = ui.permission_callback(
        "write", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE, None
    )
    assert result


def test_permission_check_negative_response():
    ui = TestUserInterface()
    ui.next_input = "n"
    result = ui.permission_callback(
        "delete", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE, None
    )
    assert not result
