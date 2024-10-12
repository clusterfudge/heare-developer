from abc import ABC, abstractmethod
from typing import Dict, Any


class UserInterface(ABC):
    @abstractmethod
    def handle_assistant_message(self, message: str) -> None:
        """
        Handle and display a new message from the assistant.

        :param message: The message from the assistant
        """

    @abstractmethod
    def handle_tool_use(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        requires_permission: bool = False,
    ) -> bool:
        """
        Handle and display information about a tool being used, optionally check for permissions.

        :param tool_name: The name of the tool being used
        :param tool_params: The parameters passed to the tool
        :param requires_permission: Whether this tool use requires permission
        :return: If requires_permission is True, return True if permission granted, False otherwise.
                 If requires_permission is False, return True (assume caller treats result as "should_invoke_tool").
        """

    @abstractmethod
    def handle_tool_result(self, tool_name: str, result: Any) -> None:
        """
        Handle and display the result of a tool use.

        :param tool_name: The name of the tool that was used
        :param result: The result returned by the tool
        """

    @abstractmethod
    def get_user_input(self, prompt: str = "") -> str:
        """
        Get input from the user.

        :param prompt: An optional prompt to display to the user
        :return: The user's input as a string
        """

    @abstractmethod
    def display_token_count(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        total_cost: float,
    ) -> None:
        """
        Display token count information.

        :param prompt_tokens: Number of tokens in the prompt
        :param completion_tokens: Number of tokens in the completion
        :param total_tokens: Total number of tokens
        :param total_cost: Total cost of the operation
        """

    @abstractmethod
    def display_welcome_message(self) -> None:
        """
        Display a welcome message to the user.
        """
