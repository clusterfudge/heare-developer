# Heare Developer CLI

Heare Developer CLI is a powerful and interactive coding assistant that leverages Anthropic's Claude AI models to help developers with various tasks. It provides a sandbox environment where you can perform file operations, execute bash commands, and interact with an AI assistant for coding-related queries and tasks.

## Key Features

1. **Advanced AI Models**: Access to Claude 3 models (Opus, Sonnet, Sonnet-3.5, Haiku) for varied needs and performance levels
2. **Intelligent File Handling**: Smart file mention system using @ syntax for referencing files
3. **Sandbox Environment**: Configurable sandbox modes for controlled file operations
4. **Tool Integration**: Built-in tools for file and system operations, including Plane.so API integration for task management
5. **Command Auto-completion**: Intelligent command and path completion
6. **Multi-line Input Support**: Easy handling of multi-line code and text input
7. **Token Usage Tracking**: Real-time monitoring of token usage and associated costs
8. **Rate Limiting Protection**: Built-in rate limit handling with exponential backoff
9. **Permission Management**: Granular control over file and system operations
10. **Rich Command History**: Searchable command history with auto-suggestions

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/clusterfudge/heare-developer.git
   cd heare-developer
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Anthropic API key:
   ```
   export ANTHROPIC_API_KEY=your_api_key_here
   ```
   Or create a `.env` file containing:
   ```
   ANTHROPIC_API_KEY=your_api_key_here
   ```

4. (Optional) Set up your Plane.so API key for task management:
   ```
   export PLANE_API_KEY=your_plane_api_key_here
   ```
   Or create a `~/.plane-secret` file containing just your API key.

## Usage

Basic usage:
```bash
python -m heare.developer.cli [sandbox_path]
```

### Command Line Options

- `sandbox_path`: Path to initialize the sandbox (default: current directory)
- `--model`: Choose the Claude AI model (default: sonnet-3.5)
  - Available options: opus, sonnet, sonnet-3.5, haiku
- `--summary-cache`: Specify path for summary cache (default: ~/.cache/heare.summary_cache)
- `--sandbox-mode`: Set sandbox mode for file operations
  - Options: REMEMBER_PER_RESOURCE, FORGET_IMMEDIATELY, REMEMBER_FOREVER
- `--prompt`: Provide initial prompt (prefix with @ to read from file)

### Interactive Features

1. **File References**:
   Use @ syntax to reference files in your messages:
   ```
   > Can you explain the code in @src/main.py?
   ```

2. **Multi-line Input**:
   ```
   > {
   Here's my multi-line
   input that can include
   code or text
   }
   ```

3. **Command Auto-completion**:
   - Press Tab to auto-complete commands and file paths
   - @ followed by partial path triggers file path completion

4. **Available Commands**:
   - `/quit` or `/exit`: Exit the CLI
   - `/restart`: Clear chat history and start over
   - Various tool-specific commands (shown on startup)

5. **Plane.so Integration**:
   - Manage tasks, issues, and projects directly through the CLI
   - List workspaces, projects, and issues
   - Create, update, and link issues
   - Add comments and create subtasks
   - See `docs/plane_tools_examples.md` for detailed usage examples

### Sandbox Modes

- `REMEMBER_PER_RESOURCE`: Remember permissions per resource (default)
- `FORGET_IMMEDIATELY`: Ask for permission each time
- `REMEMBER_FOREVER`: Remember all permissions

## Development

The project follows a modular architecture:

- `heare/developer/`: Core CLI and developer tools
- `heare/pm/`: Project management functionality (WIP)
- `tests/`: Test suite

To contribute:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

[Insert your chosen license here]

## Acknowledgements

This project uses:
- Anthropic's Claude AI models
- Rich for terminal UI
- Prompt Toolkit for command line interface
- Various other open source packages (see requirements.txt)
3. **Available Commands**:
   - `/quit` or `/exit`: Exit the CLI
   - `/restart`: Clear chat history and start over
   - Various tool-specific commands (shown on startup)

4. **Plane.so Integration**:
   - Manage tasks, issues, and projects directly through the CLI
   - List workspaces, projects, and issues
   - Create, update, and link issues
   - Add comments and create subtasks
   - See `docs/plane_tools_examples.md` for detailed usage examples