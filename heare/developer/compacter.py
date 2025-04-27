#!/usr/bin/env python3
"""
Conversation compaction module for Heare Developer.

This module provides functionality to compact long conversations by summarizing them
and starting a new conversation when they exceed certain token limits.
"""

import os
import json
from typing import List, Tuple
from dataclasses import dataclass
import anthropic
from anthropic.types import MessageParam
from dotenv import load_dotenv

# Constants for token limits
DEFAULT_TOKEN_THRESHOLD = 100000  # Example threshold, adjust based on actual needs


@dataclass
class CompactionSummary:
    """Summary of a compacted conversation."""

    original_message_count: int
    original_token_count: int
    summary_token_count: int
    compaction_ratio: float
    summary: str


class ConversationCompacter:
    """Handles the compaction of long conversations into summaries."""

    def __init__(self, token_threshold: int = DEFAULT_TOKEN_THRESHOLD, client=None):
        """Initialize the conversation compacter.

        Args:
            token_threshold: Maximum number of tokens before compaction is triggered
            client: Anthropic client instance (optional, for testing)
        """
        self.token_threshold = token_threshold

        if client:
            self.client = client
        else:
            load_dotenv()
            self.api_key = os.getenv("ANTHROPIC_API_KEY")

            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            self.client = anthropic.Client(api_key=self.api_key)

    def count_tokens(self, messages: List[MessageParam], model: str) -> int:
        """Count tokens in a conversation using Anthropic's token counting API.

        Args:
            messages: List of messages in the conversation
            model: Model name to use for token counting

        Returns:
            int: Number of tokens in the conversation
        """
        # Convert messages to a string representation
        messages_str = self._messages_to_string(messages)

        # Call Anthropic's token counting API
        try:
            response = self.client.count_tokens(model=model, prompt=messages_str)
            return response.token_count
        except Exception as e:
            print(f"Error counting tokens: {e}")
            # Fallback to an estimate if API call fails
            return self._estimate_token_count(messages_str)

    def _messages_to_string(self, messages: List[MessageParam]) -> str:
        """Convert message objects to a string representation.

        Args:
            messages: List of messages in the conversation

        Returns:
            str: String representation of the messages
        """
        conversation_str = ""

        for message in messages:
            role = message.get("role", "unknown")

            # Process content based on its type
            content = message.get("content", "")
            if isinstance(content, str):
                content_str = content
            elif isinstance(content, list):
                # Extract text from content blocks
                content_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if "text" in item:
                            content_parts.append(item["text"])
                        elif item.get("type") == "tool_use":
                            tool_name = item.get("name", "unnamed_tool")
                            input_str = json.dumps(item.get("input", {}))
                            content_parts.append(
                                f"[Tool Use: {tool_name}]\n{input_str}"
                            )
                        elif item.get("type") == "tool_result":
                            content_parts.append(
                                f"[Tool Result]\n{item.get('content', '')}"
                            )
                content_str = "\n".join(content_parts)
            else:
                content_str = str(content)

            conversation_str += f"{role}: {content_str}\n\n"

        return conversation_str

    def _estimate_token_count(self, text: str) -> int:
        """Estimate token count as a fallback when API call fails.

        This is a very rough estimate and should only be used as a fallback.

        Args:
            text: Text to estimate token count for

        Returns:
            int: Estimated token count
        """
        # A rough estimate based on GPT tokenization (words / 0.75)
        words = len(text.split())
        return int(words / 0.75)

    def should_compact(self, messages: List[MessageParam], model: str) -> bool:
        """Check if a conversation should be compacted.

        Args:
            messages: List of messages in the conversation
            model: Model name to use for token counting

        Returns:
            bool: True if the conversation should be compacted
        """
        token_count = self.count_tokens(messages, model)
        return token_count > self.token_threshold

    def generate_summary(
        self, messages: List[MessageParam], model: str
    ) -> CompactionSummary:
        """Generate a summary of the conversation.

        Args:
            messages: List of messages in the conversation
            model: Model name to use for token counting

        Returns:
            CompactionSummary: Summary of the compacted conversation
        """
        # Get original token count
        original_token_count = self.count_tokens(messages, model)
        original_message_count = len(messages)

        # Convert messages to a string for the summarization prompt
        conversation_str = self._messages_to_string(messages)

        # Create summarization prompt
        system_prompt = """
        Summarize the following conversation for continuity.
        Include:
        1. Key points and decisions
        2. Current state of development/discussion
        3. Any outstanding questions or tasks
        4. The most recent context that future messages will reference
        
        Be comprehensive yet concise. The summary will be used to start a new conversation 
        that continues where this one left off.
        """

        # Generate summary using Claude
        response = self.client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": conversation_str}],
            max_tokens=4000,
        )

        summary = response.content[0].text
        summary_token_count = self.count_tokens(
            [{"role": "system", "content": summary}], model
        )
        compaction_ratio = float(summary_token_count) / float(original_token_count)

        return CompactionSummary(
            original_message_count=original_message_count,
            original_token_count=original_token_count,
            summary_token_count=summary_token_count,
            compaction_ratio=compaction_ratio,
            summary=summary,
        )

    def compact_conversation(
        self, messages: List[MessageParam], model: str
    ) -> Tuple[List[MessageParam], CompactionSummary]:
        """Compact a conversation by summarizing it and creating a new conversation.

        Args:
            messages: List of messages in the conversation
            model: Model name to use for token counting

        Returns:
            Tuple containing:
                - List of MessageParam: New compacted conversation
                - CompactionSummary: Summary information about the compaction
        """
        if not self.should_compact(messages, model):
            return messages, None

        # Generate summary
        summary = self.generate_summary(messages, model)

        # Create a new conversation with the summary as the system message
        new_messages = [
            {
                "role": "system",
                "content": (
                    f"### Conversation Summary (Compacted from {summary.original_message_count} previous messages)\n\n"
                    f"{summary.summary}\n\n"
                    f"Continue the conversation from this point."
                ),
            }
        ]

        # Optionally, retain the most recent few messages for immediate context
        # This is configurable - here we're adding the last user/assistant exchange
        if len(messages) >= 2:
            new_messages.extend(messages[-2:])

        return new_messages, summary
