#!/usr/bin/env python3
"""
Test script to reproduce the keyboard input issue with timeout logic.

This script will help us understand and reproduce the exact conditions
that cause the CLI to become unresponsive.
"""

import asyncio
import subprocess
import sys
import time
from typing import Optional

from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from heare.developer.user_interface import UserInterface
from heare.developer.tools.shell import shell_execute


class TestUserInterface(UserInterface):
    """Test user interface that simulates user behavior."""
    
    def __init__(self, responses=None):
        self.responses = responses or []
        self.response_index = 0
        self.system_messages = []
        
    def handle_assistant_message(self, message: str) -> None:
        print(f"[ASSISTANT] {message}")
        
    def handle_system_message(self, message: str, markdown=True, live=None) -> None:
        print(f"[SYSTEM] {message}")
        self.system_messages.append(message)
        
    def permission_callback(self, action: str, resource: str, sandbox_mode: SandboxMode, action_arguments):
        return True
        
    def permission_rendering_callback(self, action: str, resource: str, action_arguments):
        pass
        
    def handle_tool_use(self, tool_name: str, tool_params):
        print(f"[TOOL] Using {tool_name} with {tool_params}")
        
    def handle_tool_result(self, name: str, result, live=None):
        print(f"[RESULT] {name}: {result}")
        
    async def get_user_input(self, prompt: str = "") -> str:
        print(f"[INPUT PROMPT] {prompt}")
        
        # Simulate the keyboard input issue by checking if we can actually get input
        print("Testing keyboard responsiveness...")
        
        # Try to read from stdin with a timeout
        import select
        
        print("Please type 'K' to kill the process (or wait 5 seconds for timeout):")
        
        # Check if stdin has data available
        ready, _, _ = select.select([sys.stdin], [], [], 5.0)
        
        if ready:
            response = sys.stdin.readline().strip().upper()
            print(f"Got response: {response}")
            return response
        else:
            print("No input received - this indicates the keyboard input issue!")
            return "K"  # Default to kill
    
    def handle_user_input(self, user_input: str) -> str:
        return user_input
        
    def display_token_count(self, *args, **kwargs):
        pass
        
    def display_welcome_message(self):
        print("[WELCOME] Heare Developer CLI Test")
        
    def status(self, message: str, spinner: str = None):
        class DummyContext:
            def __enter__(self):
                print(f"[STATUS] {message}")
                return self
            def __exit__(self, *args):
                pass
        return DummyContext()
        
    def bare(self, message, live=None):
        print(f"[BARE] {message}")


async def test_keyboard_responsiveness():
    """Test that reproduces the keyboard input issue."""
    print("=== Testing CLI Keyboard Responsiveness During Timeout ===")
    
    # Create test context
    ui = TestUserInterface()
    context = AgentContext.create(
        model_spec={},
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=ui,
    )
    
    # Test with a command that will trigger timeout
    print("\n1. Testing normal quick command:")
    result = await shell_execute(context, "echo 'test'")
    print(f"Result: {result[:100]}...")
    
    print("\n2. Testing long-running command that triggers timeout:")
    print("This should trigger the timeout logic and test keyboard responsiveness...")
    
    # Use a command that will definitely timeout
    result = await shell_execute(context, "sleep 10", timeout=2)  
    print(f"Result: {result[:200]}...")
    
    print("\n3. Analyzing system messages:")
    for i, msg in enumerate(ui.system_messages):
        print(f"  Message {i+1}: {msg[:100]}...")


def test_process_stdin_inheritance():
    """Test if background processes are inheriting stdin."""
    print("\n=== Testing Process stdin Inheritance ===")
    
    # Test current behavior
    print("Creating process with current method (may inherit stdin):")
    proc1 = subprocess.Popen(
        "sleep 5",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    print(f"Process 1 PID: {proc1.pid}")
    print(f"Process 1 stdin: {proc1.stdin}")
    
    # Test with stdin explicitly set to DEVNULL
    print("Creating process with stdin=DEVNULL:")
    proc2 = subprocess.Popen(
        "sleep 5", 
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    
    print(f"Process 2 PID: {proc2.pid}")
    print(f"Process 2 stdin: {proc2.stdin}")
    
    # Clean up
    proc1.terminate()
    proc2.terminate()
    proc1.wait()
    proc2.wait()
    
    print("Both processes terminated.")


if __name__ == "__main__":
    print("CLI Keyboard Input Issue Reproduction Test")
    print("=" * 50)
    
    # Test 1: Check process stdin inheritance
    test_process_stdin_inheritance()
    
    # Test 2: Test actual keyboard responsiveness
    print("\nStarting async keyboard responsiveness test...")
    try:
        asyncio.run(test_keyboard_responsiveness())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed.")