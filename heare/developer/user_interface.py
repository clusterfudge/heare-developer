import contextlib
from abc import ABC, abstractmethod
from typing import Dict, Any

from heare.developer.sandbox import SandboxMode


class UserInterface(ABC):
    @abstractmethod
    def handle_assistant_message(self, message: str) -> None:
        """
        Handle and display a new message from the assistant.

        :param message: The message from the assistant
        """

    @abstractmethod
    def handle_system_message(self, message: str) -> None:
        """
        Handle and display a new system message.

        :param message: The message
        """

    @abstractmethod
    def permission_callback(
        self,
        action: str,
        resource: str,
        sandbox_mode: SandboxMode,
        action_arguments: Dict | None,
    ) -> bool:
        """
        :param action:
        :param resource:
        :param sandbox_mode:
        :param action_arguments:
        :return:
        """

    @abstractmethod
    def permission_rendering_callback(
        self,
        action: str,
        resource: str,
        action_arguments: Dict | None,
    ) -> None:
        """
        :param action:
        :param resource:
        :param action_arguments:
        :return: None
        """

    @abstractmethod
    def handle_tool_use(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
    ):
        """
        Handle and display information about a tool being used, optionally check for permissions.

        :param tool_name: The name of the tool being used
        :param tool_params: The parameters passed to the tool
        """

    @abstractmethod
    def handle_tool_result(self, name: str, result: Dict[str, Any]) -> None:
        """
        Handle and display the result of a tool use.

        :param name:  The name of the original tool invocation
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
    def handle_user_input(self, user_input: str) -> str:
        """
        Handle and display input from the user

        :param user_input: the input from the user
        """

    @abstractmethod
    def display_token_count(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        total_cost: float,
        cached_tokens: int | None = None,
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

    @abstractmethod
    def status(
        self, message: str, spinner: str = None
    ) -> contextlib.AbstractContextManager:
        """
        Display a status message to the user.
        :param message:
        :param spinner:
        :return:
        """

    @abstractmethod
    def bare(self, message: str | Any) -> None:
        """
        Display bare message to the user
        :param message:
        :return:
        """
