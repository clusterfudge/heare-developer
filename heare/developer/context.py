import os
from dataclasses import dataclass
from typing import Any

from heare.developer.sandbox import Sandbox, SandboxMode
from heare.developer.user_interface import UserInterface


@dataclass(frozen=True)
class AgentContext:
    model_spec: dict[str, Any]
    sandbox: Sandbox
    user_interface: UserInterface

    @staticmethod
    def create(
        model_spec: dict[str, Any],
        sandbox_mode: SandboxMode,
        sandbox_contents: list[str],
        user_interface: UserInterface,
    ) -> "AgentContext":
        sandbox = Sandbox(
            sandbox_contents[0] if sandbox_contents else os.getcwd(),
            mode=sandbox_mode,
            permission_check_callback=user_interface.permission_callback,
            permission_check_rendering_callback=user_interface.permission_rendering_callback,
        )

        return AgentContext(
            model_spec=model_spec, sandbox=sandbox, user_interface=user_interface
        )

    def with_user_interface(self, user_interface: UserInterface) -> "AgentContext":
        return AgentContext(
            model_spec=self.model_spec,
            sandbox=self.sandbox,
            user_interface=user_interface,
        )
