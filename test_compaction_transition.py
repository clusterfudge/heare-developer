#!/usr/bin/env python3
"""
Test script to verify the compaction transition functionality.
"""

import os
import sys
from uuid import uuid4
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heare.developer.compacter import ConversationCompacter, CompactionTransition
from heare.developer.context import AgentContext
from heare.developer.models import get_model
from heare.developer.sandbox import SandboxMode
from heare.developer.user_interface import UserInterface
from heare.developer.memory import MemoryManager
from anthropic.types import MessageParam


def create_test_context_with_long_history():
    """Create a test context with a long conversation history."""
    
    # Mock user interface
    mock_ui = Mock(spec=UserInterface)
    mock_ui.handle_system_message = Mock()
    
    # Mock sandbox with proper methods
    mock_sandbox = Mock()
    mock_sandbox.get_directory_listing.return_value = []  # Return empty list
    mock_sandbox.mode = SandboxMode.ALLOW_ALL
    
    # Create agent context
    context = AgentContext(
        session_id=str(uuid4()),
        parent_session_id=None,
        model_spec=get_model("sonnet"),
        sandbox=mock_sandbox,
        user_interface=mock_ui,
        usage=[],
        memory_manager=MemoryManager(),
        _chat_history=[],
        _tool_result_buffer=[]
    )
    
    # Add a long conversation that should trigger compaction
    long_text = "This is a very long conversation. " * 1000  # Make it long enough
    
    for i in range(20):  # Add multiple exchanges
        context.chat_history.append({
            "role": "user", 
            "content": [{"type": "text", "text": f"User message {i}: {long_text}"}]
        })
        context.chat_history.append({
            "role": "assistant", 
            "content": [{"type": "text", "text": f"Assistant response {i}: {long_text}"}]
        })
    
    return context


def test_compaction_transition():
    """Test that compaction transition works correctly."""
    print("Testing compaction transition functionality...")
    
    # Create test context
    context = create_test_context_with_long_history()
    original_session_id = context.session_id
    original_message_count = len(context.chat_history)
    
    print(f"Original session ID: {original_session_id[:8]}")
    print(f"Original message count: {original_message_count}")
    
    # Create compacter and test transition
    compacter = ConversationCompacter()
    model_name = "claude-3-5-sonnet-latest"
    
    # Mock the API call for summary generation and token counting
    with patch.object(compacter, 'client') as mock_client, \
         patch.object(compacter, 'count_tokens') as mock_count_tokens:
        
        # Mock token counting to return a high value (triggering compaction)
        mock_count_tokens.return_value = 150000  # High enough to trigger compaction
        
        # Mock the API response for summary generation
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "This is a test summary of the conversation."
        mock_client.messages.create.return_value = mock_response
        
        # Test the transition directly since we're mocking token counts
        transition = compacter.compact_and_transition(context, model_name)
        
        if transition:
            print(f"Compaction successful!")
            print(f"New session ID: {transition.new_session_id[:8]}")
            print(f"Original session ID: {transition.original_session_id[:8]}")
            print(f"Compacted message count: {len(transition.compacted_messages)}")
            print(f"Compaction ratio: {transition.summary.compaction_ratio:.3f}")
            
            # Verify the transition data
            assert transition.original_session_id == original_session_id
            assert transition.new_session_id != original_session_id
            assert len(transition.compacted_messages) < original_message_count
            assert transition.summary.original_message_count == original_message_count
            
            print("✅ All assertions passed!")
            return True
        else:
            print("❌ No transition was created")
            return False


if __name__ == "__main__":
    try:
        success = test_compaction_transition()
        if success:
            print("\n🎉 Compaction transition test completed successfully!")
        else:
            print("\n❌ Compaction transition test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)