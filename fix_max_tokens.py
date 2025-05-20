def fix_max_tokens_continuation():
    """
    When a max_tokens event happens, we need to do the following:

    1. Remove the final message from the chat history (don't append it as an assistant msg)
    2. Put any content from the final message into the tool result buffer instead
    3. Add the continuation prompt to the tool result buffer

    This ensures that if we're in the middle of a tool_use block, we don't break the flow.
    """
    # This code would be in the max_tokens branch of agent.py

    # The key part where we need to change the code:
    """
    # Current implementation:
    elif final_message.stop_reason == "max_tokens":
        user_interface.handle_assistant_message(
            "[bold yellow]Hit max tokens. I'll continue from where I left off...[/bold yellow]"
        )

        # Add a continuation prompt to the tool result buffer
        continuation_prompt = {
            "type": "text",
            "text": "Please continue from where you left off.",
        }
        agent_context.tool_result_buffer.append(continuation_prompt)
    """

    # Proposed implementation:
    """
    elif final_message.stop_reason == "max_tokens":
        user_interface.handle_assistant_message(
            "[bold yellow]Hit max tokens. I'll continue from where I left off...[/bold yellow]"
        )
        
        # Don't add the partial message to chat history (remove it if necessary)
        if agent_context.chat_history and agent_context.chat_history[-1]["role"] == "assistant":
            agent_context.chat_history.pop()
            
        # Add the partial message content to the tool result buffer
        final_content = final_message.content
        if isinstance(final_content, list):
            for message in final_content:
                if isinstance(message, TextBlock):
                    # Add text blocks to the tool result buffer
                    if message.text.strip():
                        agent_context.tool_result_buffer.append(
                            {"type": "text", "text": message.text.strip()}
                        )
                elif getattr(message, "type", None) == "tool_use":
                    # Add partial tool_use blocks as text to avoid API errors
                    tool_name = getattr(message, "name", "unknown_tool")
                    tool_input = getattr(message, "input", {})
                    tool_text = f"Partial tool use detected: {tool_name} with input: {tool_input}"
                    agent_context.tool_result_buffer.append(
                        {"type": "text", "text": tool_text}
                    )
        else:
            # If it's a string, add it directly
            agent_context.tool_result_buffer.append(
                {"type": "text", "text": final_content}
            )
            
        # Add a continuation prompt to the tool result buffer
        continuation_prompt = {
            "type": "text",
            "text": "Please continue from where you left off. If you were in the middle of a tool use, please complete it.",
        }
        agent_context.tool_result_buffer.append(continuation_prompt)
    """

    # This approach should fix the issue with tool_use blocks by:
    # 1. Not breaking the context of being in a tool_use block
    # 2. Preserving the partial message as part of the user's next input
    # 3. Explicitly asking the model to complete any unfinished tool use

    return "Generated fix for max tokens continuation that addresses the reviewer's concern"
