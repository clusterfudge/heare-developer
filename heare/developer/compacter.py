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

# Default threshold ratio of model's context window to trigger compaction
DEFAULT_COMPACTION_THRESHOLD_RATIO = 0.85  # Trigger compaction at 85% of context window


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

    def __init__(
        self, threshold_ratio: float = DEFAULT_COMPACTION_THRESHOLD_RATIO, client=None
    ):
        """Initialize the conversation compacter.

        Args:
            threshold_ratio: Ratio of model's context window to trigger compaction
            client: Anthropic client instance (optional, for testing)
        """
        self.threshold_ratio = threshold_ratio

        # Get model context window information
        from heare.developer.models import MODEL_MAP

        self.model_context_windows = {
            model_data["title"]: model_data.get("context_window", 100000)
            for model, model_data in MODEL_MAP.items()
        }

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
        # Use for_summary=False to ensure we include file mentions in the token count
        messages_str = self._messages_to_string(messages, for_summary=False)

        # Call Anthropic's token counting API
        try:
            # New method for token counting in the updated Anthropic SDK
            response = self.client.messages.count_tokens(
                model=model, messages=[{"role": "user", "content": messages_str}]
            )
            # Check if response contains either 'token_count' or 'tokens' attribute
            if hasattr(response, "token_count"):
                return response.token_count
            elif hasattr(response, "tokens"):
                return response.tokens
            else:
                # Access the dictionary form to handle API changes
                response_dict = (
                    response if isinstance(response, dict) else response.__dict__
                )
                if "token_count" in response_dict:
                    return response_dict["token_count"]
                elif "tokens" in response_dict:
                    return response_dict["tokens"]
                elif "input_tokens" in response_dict:
                    return response_dict["input_tokens"]
                else:
                    print(f"Token count not found in response: {response}")
                    return self._estimate_token_count(messages_str)
        except Exception as e:
            print(f"Error counting tokens: {e}")
            # Fallback to an estimate if API call fails
            return self._estimate_token_count(messages_str)

    def _messages_to_string(
        self, messages: List[MessageParam], for_summary: bool = False
    ) -> str:
        """Convert message objects to a string representation.

        Args:
            messages: List of messages in the conversation
            for_summary: If True, filter out content elements containing mentioned_file blocks

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
                            text = item["text"]
                            # If processing for summary, skip content blocks containing mentioned_file
                            if for_summary and "<mentioned_file" in text:
                                try:
                                    # Extract the path attribute from the mentioned_file tag
                                    import re

                                    match = re.search(
                                        r"<mentioned_file path=([^ >]+)", text
                                    )
                                    if match:
                                        file_path = match.group(1)
                                        content_parts.append(
                                            f"[Referenced file: {file_path}]"
                                        )
                                    else:
                                        content_parts.append("[Referenced file]")
                                except Exception:
                                    content_parts.append("[Referenced file]")
                            else:
                                content_parts.append(text)
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

        # Get context window size for this model, default to 100k if not found
        context_window = self.model_context_windows.get(model, 100000)

        # Calculate threshold based on context window and threshold ratio
        token_threshold = int(context_window * self.threshold_ratio)

        return token_count > token_threshold

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
        # Get original token count (including file mentions)
        original_token_count = self.count_tokens(messages, model)
        original_message_count = len(messages)

        # Convert messages to a string for the summarization prompt
        # This will exclude file content blocks from the summary
        conversation_str = self._messages_to_string(messages, for_summary=True)

        # Create summarization prompt
        system_prompt = """
        Summarize the following conversation for continuity.
        Include:
        1. Key points and decisions
        2. Current state of development/discussion
        3. Any outstanding questions or tasks
        4. The most recent context that future messages will reference
        
        Note: File references like [Referenced file: path] indicate files that were mentioned in the conversation.
        Acknowledge these references where relevant but don't spend time describing file contents.
        
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
