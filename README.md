# Heare Developer CLI

Heare Developer CLI is a powerful and interactive coding assistant that leverages Anthropic's Claude AI models to help developers with various tasks. It provides a sandbox environment where you can perform file operations, execute bash commands, and interact with an AI assistant for coding-related queries and tasks.

## Key Features

1. **Interactive AI Assistant**: Engage with Claude AI models for coding assistance, explanations, and problem-solving.
2. **Sandbox Environment**: Safely perform file operations and execute commands within a controlled environment.
3. **File Management**: Read, write, and list files/directories within the sandbox.
4. **Bash Command Execution**: Run bash commands with some restrictions for security.
5. **Permission Management**: Control access to files and directories with granular permissions.
6. **Tool Integration**: Use built-in tools for various tasks.
7. **Syntax Highlighting**: Enjoy syntax highlighting for a better user experience.
8. **Chat History**: Maintain and review chat history for context preservation.
9. **Token Usage Tracking**: Monitor token usage and associated costs for each interaction.
10. **Multiple AI Models**: Choose from different Claude AI models.
11. **Customizable Sandbox Mode**: Set different sandbox modes for file operations.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-repo/heare-developer-cli.git
   cd heare-developer-cli
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Anthropic API key:
   - Create a `.env` file in the project root.
   - Add your Anthropic API key: `ANTHROPIC_API_KEY=your_api_key_here`

## Usage

To start the Heare Developer CLI, run:

```
python -m heare.developer.cli [sandbox_path]
```

Optional arguments:
- `sandbox_path`: Specify the path to initialize the sandbox (default is the current directory).
- `--model`: Choose the Claude AI model to use (default is 'sonnet-3.5'). Available options: opus, sonnet, sonnet-3.5, haiku.
- `--summary-cache`: Specify the path for the summary cache (default is ~/.cache/heare.summary_cache).
- `--sandbox-mode`: Set the sandbox mode for file operations. Choices are: REMEMBER_PER_RESOURCE, FORGET_IMMEDIATELY, REMEMBER_FOREVER.

Once the CLI is running, you can:

1. Ask questions or request assistance from the AI.
2. Use built-in tools for various operations (specific commands may vary, refer to the CLI output for available tools).
3. Enter multi-line input by starting with '{' on a new line, entering your content, and ending with '}' on a new line.

## Examples

1. Ask for coding help:
   ```
   > Can you explain how to use list comprehensions in Python?
   ```

2. Use a built-in tool (example may vary based on available tools):
   ```
   > !add myfile.py
   ```

3. Request file content:
   ```
   > Can you show me the contents of myfile.py?
   ```

4. Execute a bash command (if available):
   ```
   > !exec ls -l
   ```

5. Enter multi-line input:
   ```
   > {
   Here's my multi-line
   input for the AI
   assistant to process.
   }
   ```

## Contributing

Contributions to the Heare Developer CLI are welcome! Please follow these steps:

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your fork
5. Submit a pull request

## License

[Insert your chosen license here]

## Acknowledgements

- This project uses the Anthropic Claude AI models for natural language processing.
- Special thanks to all contributors and users of the Heare Developer CLI.