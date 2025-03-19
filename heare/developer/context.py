import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from anthropic.types import Usage

from heare.developer.sandbox import Sandbox, SandboxMode
from heare.developer.user_interface import UserInterface
from pydantic import BaseModel


class PydanticJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BaseModel):
            # For Pydantic v2
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            # For Pydantic v1
            return obj.dict()
        return super().default(obj)


class ModelSpec(TypedDict):
    title: str
    pricing: dict[str, float]
    cache_pricing: dict[str, float]
    max_tokens: int


@dataclass
class AgentContext:
    parent_session_id: str | None
    session_id: str
    model_spec: ModelSpec
    sandbox: Sandbox
    user_interface: UserInterface
    usage: list[tuple[Any, Any]]

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
            session_id=str(uuid4()),
            parent_session_id=None,
            model_spec=model_spec,
            sandbox=sandbox,
            user_interface=user_interface,
            usage=[],
        )

    def with_user_interface(self, user_interface: UserInterface) -> "AgentContext":
        return AgentContext(
            session_id=str(uuid4()),
            parent_session_id=self.session_id,
            model_spec=self.model_spec,
            sandbox=self.sandbox,
            user_interface=user_interface,
            usage=self.usage,
        )

    def _report_usage(self, usage: Usage, model_spec: ModelSpec):
        self.usage.append((usage, model_spec))

    def report_usage(self, usage: Usage, model_spec: ModelSpec | None = None):
        self._report_usage(usage, model_spec or self.model_spec)

    def usage_summary(self) -> dict[str, Any]:
        usage_summary = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "cached_tokens": 0,
            "model_breakdown": {},
        }

        for usage_entry, model_spec in self.usage:
            model_name = model_spec["title"]
            pricing = model_spec["pricing"]
            cache_pricing = model_spec["cache_pricing"]

            input_tokens = usage_entry.input_tokens
            output_tokens = usage_entry.output_tokens
            cache_creation_input_tokens = usage_entry.cache_creation_input_tokens
            cache_read_input_tokens = usage_entry.cache_read_input_tokens

            usage_summary["total_input_tokens"] += input_tokens
            usage_summary["total_output_tokens"] += output_tokens
            usage_summary["cached_tokens"] += cache_read_input_tokens

            total_cost = (
                input_tokens * pricing["input"]
                + output_tokens * pricing["output"]
                + cache_pricing["read"] * cache_read_input_tokens
                + cache_pricing["write"] * cache_creation_input_tokens
            )

            if model_name not in usage_summary["model_breakdown"]:
                usage_summary["model_breakdown"][model_name] = {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                    "cached_tokens": 0,
                    "token_breakdown": {},
                }

            model_breakdown = usage_summary["model_breakdown"][model_name]
            model_breakdown["total_input_tokens"] += input_tokens
            model_breakdown["total_output_tokens"] += output_tokens
            model_breakdown["cached_tokens"] += cache_read_input_tokens

            model_breakdown["total_cost"] += total_cost

            usage_summary["total_cost"] += total_cost

        usage_summary["total_cost"] /= 1_000_000

        return usage_summary

    def flush(self, chat_history):
        """Save the agent context and chat history to a file.

        For root contexts (parent_session_id is None), saves to:
            ~/.hdev/history/{session_id}/root.json

        For sub-agent contexts (parent_session_id is not None), saves to:
            ~/.hdev/history/{parent_session_id}/{session_id}.json

        Args:
            chat_history: The chat history to save
        """
        if not chat_history:
            return

        # Base history directory
        history_dir = Path.home() / ".hdev" / "history"

        # For root contexts, use their own session_id
        # For sub-agent contexts, use the parent_session_id
        context_dir = (
            self.parent_session_id if self.parent_session_id else self.session_id
        )
        history_dir = history_dir / context_dir

        # Create the directory if it doesn't exist
        history_dir.mkdir(parents=True, exist_ok=True)

        # Filename is root.json for root contexts, or {session_id}.json for sub-agent contexts
        filename = (
            "root.json" if self.parent_session_id is None else f"{self.session_id}.json"
        )
        history_file = history_dir / filename

        # Prepare the data to save
        context_data = {
            "session_id": self.session_id,
            "parent_session_id": self.parent_session_id,
            "model_spec": self.model_spec,
            "usage": self.usage,
            "messages": chat_history,
        }

        # Write the data to the file
        with open(history_file, "w") as f:
            json.dump(context_data, f, indent=2, cls=PydanticJSONEncoder)
