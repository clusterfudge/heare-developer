#!/usr/bin/env python3
"""
Tool Loop Demo - Cycles through various tools to demonstrate functionality
"""

import time
import random


def main():
    print("🚀 Starting Tool Loop Demo")
    print("=" * 50)

    # Loop counter
    loop_count = 0
    max_loops = 10

    while loop_count < max_loops:
        loop_count += 1
        print(f"\n🔄 Loop {loop_count}/{max_loops}")
        print("-" * 30)

        # Random delay between 1-3 seconds
        delay = random.uniform(1, 3)
        time.sleep(delay)

        # Simulate different tool operations
        tools = [
            "file_operations",
            "memory_operations",
            "python_execution",
            "shell_commands",
            "web_search",
            "calendar_check",
            "todo_management",
        ]

        current_tool = random.choice(tools)
        print(f"📱 Running: {current_tool}")

        # Simulate tool execution time
        exec_time = random.uniform(0.5, 2.0)
        time.sleep(exec_time)

        # Random success/failure
        success = random.choice([True, True, True, False])  # 75% success rate

        if success:
            print(f"✅ {current_tool} completed successfully")
        else:
            print(f"❌ {current_tool} failed - retrying next loop")

        print(f"⏱️  Execution time: {exec_time:.2f}s")

    print(f"\n🎉 Tool loop demo completed after {loop_count} iterations!")
    print("=" * 50)


if __name__ == "__main__":
    main()
