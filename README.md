# AI Development Assistant

An intelligent assistant for software development that leverages AI to help with code generation, analysis, testing, and project management.

## Features

- **AI-Assisted Coding**
  - Generate new code files from natural language prompts
  - Edit existing files with AI assistance
  - Refactor code for performance, readability, or structure
  - Auto-develop entire projects from simple prompts

- **Project Management**
  - Create and organize project structures
  - Track project metadata and files
  - Navigate between multiple projects

- **Code Analysis & Documentation**
  - Analyze code quality with detailed metrics
  - Generate documentation in various formats (Markdown, RST, HTML)
  - Explain existing code with detailed breakdowns

- **Testing Support**
  - Generate unit tests automatically
  - Run tests and debug failing tests
  - Automatically fix code to make tests pass

- **Version Control Integration**
  - Git integration for projects
  - Automatic commits for changes
  - Basic Git operations (init, add, commit, status)

- **Template Support**
  - Use and apply project templates
  - Template substitution with parameters

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ai-dev-assistant.git
   cd ai-dev-assistant
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your AI model API settings in `ai_dev_config.json` (create from the template if not exists):
   ```json
   {
     "api_url": "http://localhost:11434/api/generate",
     "default_model": "qwen2.5-coder:14b"
   }
   ```

## Usage

### Command Line Interface

Run the assistant:
```bash
python main.py
```

Enable web interface:
```bash
python main.py --web --port 8080
```

Use a specific model:
```bash
python main.py --model llama3.2:latest
```

### Commands

- `:help` - Show help information
- `:create <filename> <prompt>` - Create a new file from a prompt
- `:edit <filename> <prompt>` - Edit an existing file with AI
- `:context <file1> [file2] ...` - Set context files for the AI
- `:test <test_file>` - Run unit tests
- `:debug <code_file> <test_file>` - Debug code to fix failing tests
- `:analyze <filename>` - Analyze code quality
- `:explain <filename>` - Explain code in a file
- `:auto <prompt>` - Auto-develop a simple project
- `:project create|list|info|set <args>` - Project management
- `:refactor <filename> [type]` - Refactor code
- `:git init|add|commit|status <args>` - Git operations
- `:model [model_name]` - Get or set the active AI model
- `:config get|set|show <args>` - Configuration management

Type any text without a command prefix to chat with the AI assistant.

## Configuration

The system can be configured through `ai_dev_config.json` with the following settings:

- `api_url` - URL of the AI model API
- `working_dir` - Directory for projects
- `default_model` - Default AI model to use
- `models` - Configuration for different AI models
- `log_level` - Logging verbosity
- `git_integration` - Enable/disable Git integration
- `backup_files` - Enable/disable file backups
- And many more options...

## Models

Supported AI models:
- qwen2.5-coder:14b (default)
- llama3.2:latest
- claude3-haiku:latest
- mixtral:latest

## Requirements

- Python 3.7+
- Git (optional, for version control integration)
- Internet connection (for AI model API access)

## License

[MIT License](LICENSE)
