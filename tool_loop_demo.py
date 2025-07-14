#!/usr/bin/env python3
"""
Tool Loop Demo - Demonstrates various tools in a continuous loop
"""

import time
import random
from datetime import datetime


def demo_tools():
    """Run various tools in a loop for demonstration"""

    tools_to_demo = [
        "python_repl",
        "shell_execute",
        "list_directory",
        "calendar_list_events",
        "memory_operations",
        "file_operations",
    ]

    print("🚀 Starting tool loop demonstration...")
    print("=" * 50)

    for i in range(10):  # Run 10 iterations
        print(f"\n🔄 Loop iteration {i + 1}/10")
        print("-" * 30)

        # Random delay between 1-3 seconds
        delay = random.uniform(1, 3)
        print(f"⏱️  Waiting {delay:.1f} seconds...")
        time.sleep(delay)

        # Pick a random tool to demonstrate
        tool = random.choice(tools_to_demo)
        print(f"🔧 Running tool: {tool}")

        if tool == "python_repl":
            # Demonstrate Python REPL
            yield (
                "python_repl",
                {
                    "code": """
import random
import math

# Generate some random data
numbers = [random.randint(1, 100) for _ in range(10)]
print(f"Generated numbers: {numbers}")
print(f"Sum: {sum(numbers)}")
print(f"Average: {sum(numbers)/len(numbers):.2f}")
print(f"Max: {max(numbers)}")
print(f"Min: {min(numbers)}")

# Some math operations
angle = random.uniform(0, math.pi)
print(f"Random angle: {angle:.3f} radians")
print(f"Sin: {math.sin(angle):.3f}")
print(f"Cos: {math.cos(angle):.3f}")
"""
                },
            )

        elif tool == "shell_execute":
            # Demonstrate shell commands
            commands = [
                "date",
                "whoami",
                "pwd",
                "ls -la | head -10",
                "df -h",
                "free -h",
            ]
            cmd = random.choice(commands)
            yield ("shell_execute", {"command": cmd})

        elif tool == "list_directory":
            # Demonstrate directory listing
            dirs = [".", "./heare", "./tests", "./docs"]
            directory = random.choice(dirs)
            yield ("list_directory", {"path": directory})

        elif tool == "calendar_list_events":
            # Demonstrate calendar (might fail if not set up, but that's ok)
            yield ("calendar_list_events", {"days": 7})

        elif tool == "memory_operations":
            # Demonstrate memory operations
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            memory_path = f"tool_demo/loop_iteration_{i+1}_{timestamp}"
            content = f"Loop iteration {i+1} at {datetime.now().isoformat()}"
            yield ("write_memory_entry", {"path": memory_path, "content": content})

        elif tool == "file_operations":
            # Demonstrate file operations
            filename = f"demo_file_{i+1}.txt"
            content = (
                f"Demo file created at {datetime.now().isoformat()}\nIteration: {i+1}\n"
            )
            yield ("write_file", {"path": filename, "content": content})

        print(f"✅ Completed tool: {tool}")


if __name__ == "__main__":
    demo_tools()
