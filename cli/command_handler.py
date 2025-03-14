#!/usr/bin/env python3
import asyncio
import os
import re
import shlex
import datetime
from typing import List
import time
import shutil
import aiofiles
from colorama import Fore, Style
from config.config_manager import config_manager, logger
from core.performance import perf_tracker
from core.dev_assistant import DevAssistant
from utils.web_search import WebSearchHandler
from cli.web_commands import WebCommands
from project import ProjectCommandHandler

class CommandHandler:
    """Handles command parsing and execution for the CLI interface."""

    def __init__(self, dev_assistant: DevAssistant):
        self.dev_assistant = dev_assistant
        try:
            self.web_search_handler = WebSearchHandler()
            self.web_commands = WebCommands(self.web_search_handler)
            logger.info("Web commands initialized")
        except Exception as e:
            logger.error(f"Failed to initialize web search: {e}")
            self.web_search_handler = None
            self.web_commands = None

        self.commands = {
            ":help": self._help_command,
            ":context": self._context_command,
            ":create": self._create_command,
            ":edit": self._edit_command,
            ":move": self._move_command,
            ":test": self._test_command,
            ":debug": self._debug_command,
            ":exec": self._exec_command,
            ":auto": self._auto_command,
            ":develop": self._develop_command,
            ":explain": self._explain_command,
            ":refactor": self._refactor_command,
            ":analyze": self._analyze_command,
            ":docs": self._docs_command,
            ":generate-tests": self._generate_tests_command,
            ":project": self._project_command,
            ":git": self._git_command,
            # ":search": self._search_command,
            ":template": self._template_command,
            ":metrics": self._metrics_command,
            ":config": self._config_command,
            ":show-config": self._config_show_command,
            ":model": self._model_command,
            ":clear": self._clear_command,
            ":dialogue": self._dialogue_command,
            ":web": self._web_command,
            ":explain-url": self._explain_url_command,
            ":search": self._search_shortcut,
            ":exit": self._exit_command,
        }
        logger.info("CommandHandler initialized")

    def parse_command(self, user_input: str) -> List[str]:
        """Parse user input into command arguments."""
        # If input doesn't start with a command prefix, treat it as plain conversation
        if not user_input.startswith(':'):
            return [user_input]

        try:
            return shlex.split(user_input)
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            return user_input.split()

    async def _explain_url_command(self, args: List[str]) -> str:
        if not args:
            return "Usage: :explain_url <url>\nExample: :explain_url https://example.com"

        url = args[0]
        # Fetch and clean the webpage content
        content = await self.dev_assistant.fetch_url_content(url)
        if content.startswith("Error"):
            return content

        # Prepare a prompt instructing the model to explain the content
        prompt = f"Please provide a detailed explanation of the following webpage content:\n\n{content}"
        explanation = await self.dev_assistant.model_api.generate_response(self.dev_assistant.model, prompt)
        return explanation

    async def handle_command(self, command_args: List[str]) -> str:
        """Handle a parsed command."""
        if not command_args:
            return "No command provided."

        command = command_args[0]

        # Handle exit command directly
        if command.lower() == "exit":
            return ":exit"

        # Check if command exists
        handler = self.commands.get(command)
        if handler:
            try:
                return await handler(command_args[1:])
            except Exception as e:
                logger.error(f"Error executing command {command}: {e}", exc_info=True)
                return f"Error executing command {command}: {e}"
        else:
            # Treat as conversation if not a recognized command
            return None

    async def _help_command(self, args: List[str]) -> str:
        """Show help information."""
        if args and args[0] in self.commands:
            # Show help for specific command
            command = args[0]
            doc = self.commands[command].__doc__ or "No documentation available."

            # Get signature for the command
            sig = None
            if command == ":help":
                sig = ":help [command]"
            elif command == ":context":
                sig = ":context <file1> [file2] ..."
            elif command == ":create":
                sig = ":create <filename> <prompt>"
            elif command == ":edit":
                sig = ":edit <filename> <prompt>"
            elif command == ":move":
                sig = ":move <source> <destination>"
            elif command == ":test":
                sig = ":test <test_file>"
            elif command == ":debug":
                sig = ":debug <code_file> <test_file>"
            elif command == ":exec":
                sig = ":exec <code>"
            elif command == ":auto":
                sig = ":auto <prompt>"
            elif command == ":develop":
                sig = ":develop <prompt> [file1 file2 ...]"
            elif command == ":explain":
                sig = ":explain <filename>"
            elif command == ":refactor":
                sig = ":refactor <filename> [type]"
            elif command == ":analyze":
                sig = ":analyze <filename>"
            elif command == ":docs":
                sig = ":docs <filename> [format]"
            elif command == ":generate-tests":
                sig = ":generate-tests <filename>"
            elif command == ":project":
                sig = ":project create|list|info|set <args>"
            elif command == ":git":
                sig = ":git init|add|commit|status <args>"
            elif command == ":search":
                sig = ":search <query> [file_pattern]"
            elif command == ":template":
                sig = ":template list|use <args>"
            elif command == ":metrics":
                sig = ":metrics [reset]"
            elif command == ":config":
                sig = ":config get|set|show <args>"
            elif command == ":model":
                sig = ":model [model_name]"
            elif command == ":clear":
                sig = ":clear"
            elif command == ":exit":
                sig = ":exit"

            return f"{Fore.CYAN}{sig}{Style.RESET_ALL}\n{doc}"

        # Show general help
        help_text = f"{Fore.CYAN}AI Development Assistant v{config_manager.get('version', '2.0.0')}{Style.RESET_ALL}\n\n"
        help_text += f"{Fore.YELLOW}Available Commands:{Style.RESET_ALL}\n"

        commands = [
            (":help", "[command]", "Show help information"),
            (":context", "<file1> [file2] ...", "Set context files for the AI"),
            (":create", "<filename> <prompt>", "Create a new file from a prompt"),
            (":edit", "<filename> <prompt>", "Edit an existing file with AI assistance"),
            (":move", "<source> <destination>", "Move/rename a file"),
            (":test", "<test_file>", "Run unit tests"),
            (":debug", "<code_file> <test_file>", "Debug code to fix failing tests"),
            (":exec", "<code>", "Execute Python code"),
            (":auto", "<prompt>", "Auto-develop a simple project"),
            (":develop", "<prompt> [file1 file2 ...]", "Develop a project with data files"),
            (":explain", "<filename>", "Explain code in a file"),
            (":refactor", "<filename> [type]",
             "Refactor code (types: general, performance, readability, structure, patterns)"),
            (":analyze", "<filename>", "Analyze code quality"),
            (":docs", "<filename> [format]", "Generate documentation (formats: markdown, rst, html)"),
            (":generate-tests", "<filename>", "Generate unit tests for a file"),
            (":project", "create|list|info|set|rename|remove|analyze|debug|improve <args>", "Project management commands"),
            (":git", "init|add|commit|status <args>", "Git operations"),
            (":search", "<query> [file_pattern]", "Search for code in project"),
            (":template", "list|use <args>", "Work with project templates"),
            (":metrics", "[reset]", "Show performance metrics"),
            (":config", "get|set|show <args>", "Configuration management"),
            (":model", "[model_name]", "Get or set the active AI model"),
            (":clear", "", "Clear the terminal screen"),
            (":dialogue", "<model1> <model2> <topic> [--turns=N] [--verbose]",
             "Create a dialogue between two AI models"),
            (":exit", "", "Exit the application")
        ]

        # Calculate column widths
        cmd_width = max(len(cmd[0]) for cmd in commands) + 2
        args_width = max(len(cmd[1]) for cmd in commands) + 2

        # Format commands
        for cmd, args, desc in commands:
            help_text += f"  {Fore.GREEN}{cmd:<{cmd_width}}{Style.RESET_ALL}{args:<{args_width}}{desc}\n"

        help_text += f"\n{Fore.YELLOW}Type any text without a command prefix to chat with the AI.{Style.RESET_ALL}"
        return help_text

    async def _context_command(self, args: List[str]) -> str:
        """Set context files for the AI."""
        if not args:
            return "Usage: :context <file1> [file2] ...\nProvide at least one file to set as context."

        return await self.dev_assistant.set_context(args)

    async def _create_command(self, args: List[str]) -> str:
        """Create a new file from a prompt."""
        if len(args) < 2:
            return "Usage: :create <filename> <prompt>\nProvide a filename and prompt."

        filename = args[0]
        prompt = " ".join(args[1:])
        return await self.dev_assistant.create_from_prompt(prompt, filename)

    async def _edit_command(self, args: List[str]) -> str:
        """Edit an existing file with AI assistance."""
        if len(args) < 2:
            return "Usage: :edit <filename> <prompt>\nProvide a filename and prompt."

        filename = args[0]
        prompt = " ".join(args[1:])
        return await self.dev_assistant.edit_file(filename, prompt)

    async def _move_command(self, args: List[str]) -> str:
        """Move/rename a file."""
        if len(args) != 2:
            return "Usage: :move <source> <destination>\nProvide source and destination paths."

        source = args[0]
        destination = args[1]
        return await self.dev_assistant.code_handler.move_file(source, destination)

    async def _test_command(self, args: List[str]) -> str:
        """Run unit tests."""
        if len(args) != 1:
            return "Usage: :test <test_file>\nProvide a test file to run."

        test_file = args[0]
        return await self.dev_assistant.code_handler.run_tests(test_file)

    async def _debug_command(self, args: List[str]) -> str:
        """Debug code to fix failing tests."""
        if len(args) != 2:
            return "Usage: :debug <code_file> <test_file>\nProvide both code and test files."

        code_file = args[0]
        test_file = args[1]
        return await self.dev_assistant.debug_and_fix(code_file, test_file)

    async def _exec_command(self, args: List[str]) -> str:
        """Execute Python code."""
        if not args:
            return "Usage: :exec <code>\nProvide Python code to execute."

        code = " ".join(args)
        return await self.dev_assistant.code_handler.execute_python_code(code)

    async def _auto_command(self, args: List[str]) -> str:
        """Auto-develop a simple project."""
        if not args:
            return "Usage: :auto <prompt>\nProvide a prompt describing the project."

        prompt = " ".join(args)
        return await self.dev_assistant.auto_develop(prompt)

    async def _develop_command(self, args: List[str]) -> str:
        """Develop a project with data files."""
        if not args:
            return "Usage: :develop <prompt> [file1 file2 ...]\nProvide a prompt and optional data files."

        prompt = args[0]
        data_files = args[1:] if len(args) > 1 else []
        return await self.dev_assistant.auto_develop(prompt, data_files)

    async def _explain_command(self, args: List[str]) -> str:
        """Explain code in a file."""
        if len(args) != 1:
            return "Usage: :explain <filename>\nProvide a file to explain."

        filename = args[0]
        return await self.dev_assistant.explain_code(filename)

    async def _refactor_command(self, args: List[str]) -> str:
        """Refactor code."""
        if not args:
            return "Usage: :refactor <filename> [type]\nTypes: general, performance, readability, structure, patterns"

        filename = args[0]
        refactor_type = args[1] if len(args) > 1 else "general"
        valid_types = ["general", "performance", "readability", "structure", "patterns"]

        if refactor_type not in valid_types:
            return f"Invalid refactor type: {refactor_type}\nValid types: {', '.join(valid_types)}"

        return await self.dev_assistant.refactor_code(filename, refactor_type)

    async def _analyze_command(self, args: List[str]) -> str:
        """Analyze code quality."""
        if len(args) != 1:
            return "Usage: :analyze <filename>\nProvide a file to analyze."

        filename = args[0]
        return await self.dev_assistant.analyze_code_quality(filename)

    async def _docs_command(self, args: List[str]) -> str:
        """Generate documentation."""
        if not args:
            return "Usage: :docs <filename> [format]\nFormats: markdown, rst, html (default: markdown)"

        filename = args[0]
        doc_format = args[1] if len(args) > 1 else "markdown"
        valid_formats = ["markdown", "rst", "html"]

        if doc_format not in valid_formats:
            return f"Invalid documentation format: {doc_format}\nValid formats: {', '.join(valid_formats)}"

        return await self.dev_assistant.generate_documentation_file(filename, doc_format)

    async def _generate_tests_command(self, args: List[str]) -> str:
        """Generate unit tests for a file."""
        if len(args) != 1:
            return "Usage: :generate-tests <filename>\nProvide a file to generate tests for."

        filename = args[0]
        return await self.dev_assistant.generate_tests(filename)

    async def _project_command(self, args: List[str]) -> str:
        project_handler = ProjectCommandHandler(self.dev_assistant)
        return await project_handler.execute(args)

    async def _git_command(self, args: List[str]) -> str:
        """Git operations."""
        if not self.dev_assistant.git_manager or not self.dev_assistant.git_manager.has_git:
            return "Git integration is not available. Please ensure Git is installed."

        if not args:
            return "Usage: :git init|add|commit|status <args>"

        subcmd = args[0]

        # Check if we have a current project
        if not self.dev_assistant.current_project:
            return "No active project. Use :project set <name> to select a project first."

        project_dir = self.dev_assistant.current_project.directory

        if subcmd == "init":
            return await self.dev_assistant.git_manager.init_repo(project_dir)

        elif subcmd == "add":
            if len(args) > 1:
                files = args[1:]
                return await self.dev_assistant.git_manager.add_files(project_dir, files)
            else:
                return await self.dev_assistant.git_manager.add_files(project_dir)

        elif subcmd == "commit":
            if len(args) < 2:
                return "Usage: :git commit <message>"

            message = " ".join(args[1:])
            return await self.dev_assistant.git_manager.commit(project_dir, message)

        elif subcmd == "status":
            return await self.dev_assistant.git_manager.status(project_dir)

        else:
            return f"Unknown git subcommand: {subcmd}\nAvailable: init, add, commit, status"

    async def _search_command(self, args: List[str]) -> str:
        """Search for code in project."""
        if not args:
            return "Usage: :search <query> [file_pattern]"

        query = args[0]
        file_patterns = args[1:] if len(args) > 1 else None

        return await self.dev_assistant.search_code(query, file_patterns)

    async def _template_command(self, args: List[str]) -> str:
        """Work with project templates."""
        if not args:
            return "Usage: :template list|use <args>"

        subcmd = args[0]

        if subcmd == "list":
            return await self.dev_assistant.list_templates()

        elif subcmd == "use":
            if len(args) < 3:
                return "Usage: :template use <template_name> <output_dir> [param1=value1 param2=value2 ...]"

            template_name = args[1]
            output_dir = args[2]

            # Parse optional parameters
            params = {}
            for param in args[3:]:
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value

            return await self.dev_assistant.use_template(template_name, output_dir, params)

        else:
            return f"Unknown template subcommand: {subcmd}\nAvailable: list, use"

    async def _metrics_command(self, args: List[str]) -> str:
        """Show performance metrics."""
        if args and args[0] == "reset":
            perf_tracker.reset()
            return "Performance metrics reset."

        perf_tracker.print_summary()
        return ""  # Already printed via the tracker

    async def _config_command(self, args: List[str]) -> str:
        """Configuration management."""
        if not args:
            return "Usage: :config get|set|show <args>"

        subcmd = args[0]

        if subcmd == "get":
            if len(args) < 2:
                return "Usage: :config get <key>"

            key = args[1]
            value = config_manager.get(key, "Key not found")
            return f"{key} = {value}"

        elif subcmd == "set":
            if len(args) < 3:
                return "Usage: :config set <key> <value>"

            key = args[1]
            value = args[2]

            # Try to convert value to appropriate type
            try:
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)
                elif value.replace(".", "", 1).isdigit():
                    value = float(value)
            except:
                pass  # Keep as string if conversion fails

            config_manager.set(key, value)
            config_manager.save_config()
            return f"Configuration updated: {key} = {value}"

        elif subcmd == "show":
            config_manager.print_config()
            return ""  # Already printed via the config manager

        else:
            return f"Unknown config subcommand: {subcmd}\nAvailable: get, set, show"

    async def _model_command(self, args: List[str]) -> str:
        """Get or set the active AI model."""
        if not args:
            available_models = ", ".join(config_manager.get("models", {}).keys())
            return f"Current model: {self.dev_assistant.model}\nAvailable models: {available_models}"

        model_name = args[0]
        return await self.dev_assistant.set_model(model_name)

    async def _clear_command(self, args: List[str]) -> str:
        """Clear the terminal screen."""
        # Use system-appropriate clear command
        os.system('cls' if os.name == 'nt' else 'clear')
        return ""

    async def _dialogue_command(self, args: List[str]) -> str:
        """Facilitate a dialogue between multiple AI models."""
        if len(args) < 3:
            return "Usage: :dialogue <model1> <model2> [model3] [model4] [...] <topic> [--turns=N] [--verbose]"

        # Parse arguments
        models = []
        topic_parts = []
        turns = 3  # Default number of turns
        verbose = False

        # Parse all arguments
        i = 0
        available_models = config_manager.get("models", {}).keys()

        # First collect models until we hit something that's not a model
        while i < len(args) and args[i] in available_models:
            models.append(args[i])
            i += 1

        # Need at least 2 models
        if len(models) < 2:
            return f"Please specify at least 2 valid models. Available models: {', '.join(available_models)}"

        # Parse remaining arguments
        while i < len(args):
            if args[i].startswith("--"):
                # Handle parameters
                if args[i].startswith("--turns="):
                    try:
                        turns = int(args[i].split("=")[1])
                    except ValueError:
                        return f"Invalid value for turns: {args[i]}"
                elif args[i] == "--verbose":
                    verbose = True
            else:
                topic_parts.append(args[i])
            i += 1

        topic = " ".join(topic_parts)
        if not topic:
            return "Please provide a topic for the dialogue."

        # Display information
        print(f"{Fore.CYAN}Starting dialogue between {len(models)} models on: {topic}{Style.RESET_ALL}")
        print(f"Models: {', '.join(models)}")
        print(f"Number of turns per model: {turns}")

        # Initialize dialogue context
        dialogue = [f"This is a dialogue between {len(models)} AI assistants on the topic: {topic}"]

        # Initialize model API
        model_api = self.dev_assistant.model_api

        # Start the conversation
        turn_counter = 1
        total_turns = turns * len(models)

        for turn in range(1, total_turns + 1):
            # Determine which model's turn it is (round-robin)
            current_model_index = (turn - 1) % len(models)
            current_model = models[current_model_index]

            # Create the prompt for the current model
            if turn == 1:
                # First model starts the conversation
                prompt = f"You are participating in a dialogue with {len(models) - 1} other AI assistants on the topic: {topic}. You are the first to speak. Please start the conversation with an interesting perspective or question on this topic."
            else:
                # Build conversational context with clear speaker identification
                # Limit history to last few turns to avoid context overflow
                max_context_turns = min(len(models) * 2, len(dialogue) - 1)  # Keep at least 2 rounds or all available
                recent_dialogue = dialogue[:1] + dialogue[-max_context_turns:]

                dialogue_history = "\n\n".join(recent_dialogue)

                # Create a more informative prompt that explains the conversation context
                prompt = f"""You are participating in a dialogue with {len(models) - 1} other AI assistants on the topic: {topic}.

    You are the model "{current_model}". Please respond to the previous messages in a thoughtful and engaging way.

    Here's the conversation so far:

    {dialogue_history}

    It's now your turn to contribute to this dialogue. Please provide your perspective or response to what has been discussed. Keep your response concise, under 250 words.
    """

            # Show which model is responding
            model_turn = (turn - 1) // len(models) + 1
            print(f"\n{Fore.YELLOW}[Round {model_turn}, {current_model}]{Style.RESET_ALL}")

            # Show thinking indicator
            if not verbose:
                print("Thinking... ", end="", flush=True)

            # Generate response with retry mechanism
            max_retries = 3
            response = None
            retry_count = 0

            while response is None and retry_count < max_retries:
                try:
                    if verbose:
                        # Use streaming for verbose mode
                        response_chunks = []

                        async def handle_chunk(chunk):
                            response_chunks.append(chunk)
                            print(chunk, end="", flush=True)

                        response = await model_api.stream_response(current_model, prompt, handle_chunk)
                    else:
                        # Use regular generation for non-verbose mode
                        response = await model_api.generate_response(current_model, prompt)
                        if response:
                            print("Done!")
                            print(response)

                except Exception as e:
                    error_str = str(e)
                    retry_count += 1

                    if "Chunk too big" in error_str:
                        # If context is too large, reduce it further
                        print(
                            f"\n{Fore.RED}Error: Context too large. Retrying with smaller context... ({retry_count}/{max_retries}){Style.RESET_ALL}")
                        # Cut the dialogue history in half for next attempt
                        max_context_turns = max_context_turns // 2
                        if max_context_turns < 1:
                            max_context_turns = 1  # Minimum of one turn

                        # Simplify the prompt for the retry
                        recent_dialogue = dialogue[:1] + dialogue[-max_context_turns:]
                        dialogue_history = "\n\n".join(recent_dialogue)
                        prompt = f"""You are model "{current_model}" in a dialogue about "{topic}".
    Recent messages:
    {dialogue_history}

    Your turn to respond (briefly, under 150 words):"""
                    else:
                        print(f"\n{Fore.RED}Error: {e}. Retrying... ({retry_count}/{max_retries}){Style.RESET_ALL}")
                        await asyncio.sleep(1)  # Brief pause before retry

            # If all retries failed, use a fallback response
            if response is None:
                response = f"[I apologize, but I encountered a technical issue and couldn't generate a proper response for the dialogue. Let's continue the conversation.]"
                print(
                    f"\n{Fore.RED}Failed to get response after {max_retries} attempts. Using fallback response.{Style.RESET_ALL}")

            # Add the response to the dialogue
            dialogue.append(f"[{current_model}]: {response}")

            # Brief pause between turns to allow for reading
            if turn < total_turns:
                await asyncio.sleep(0.5)

        # Save the dialogue to a file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sanitize model names for filename
        safe_models = "-".join([model.replace(":", "-").replace("/", "-").replace("\\", "-").split(':')[0][:10]
                                for model in models])

        # Truncate if too long
        if len(safe_models) > 50:
            safe_models = safe_models[:50] + "-etc"

        filename = f"dialogue_{len(models)}models_{safe_models}_{timestamp}.md"

        # Get the current project directory or use working directory
        if self.dev_assistant.current_project:
            output_dir = os.path.join(self.dev_assistant.current_project.directory, "dialogues")
        else:
            output_dir = os.path.join(config_manager.get("working_dir"), "dialogues")

        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(f"# Dialogue between {len(models)} models on '{topic}'\n\n")
            await f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            await f.write(f"Models participating: {', '.join(models)}\n\n")

            for i, entry in enumerate(dialogue[1:], 1):  # Skip the initial instruction
                if "]: " in entry:  # Make sure it has the expected format
                    model_name = entry.split("]: ")[0][1:]
                    message = entry.split("]: ", 1)[1]

                    round_num = (i - 1) // len(models) + 1
                    model_index = (i - 1) % len(models) + 1

                    await f.write(f"## Round {round_num} - Model {model_index}: {model_name}\n\n")
                    await f.write(f"{message}\n\n")
                else:
                    await f.write(f"## Entry {i}\n\n{entry}\n\n")

        return f"\n{Fore.GREEN}Dialogue completed!{Style.RESET_ALL}\nSaved to: {filepath}"

    async def _web_command(self, args: List[str]) -> str:
        """Execute web operations."""
        # Initialize web commands on-demand if not already done
        if not hasattr(self, 'web_commands'):
            self._init_web_components()

            # Set a more reliable default search engine
            await self.web_commands.set_search_engine(["duckduckgo"])

        return await self.web_commands.handle_command(args)

    async def _search_shortcut(self, args: List[str]) -> str:
        """Shortcut for web search."""
        if not args:
            return "Usage: :search <query> [num_results]"

        # Initialize web commands on-demand if not already done
        if not hasattr(self, 'web_commands'):
            self._init_web_components()

        return await self.web_commands.web_search(args)

    def _init_web_components(self):
        """Initialize web search components on demand."""
        try:
            from utils.web_search import WebSearchHandler
            from cli.web_commands import WebCommands

            self.web_search_handler = WebSearchHandler()
            self.web_commands = WebCommands(self.web_search_handler)
            logger.info("Web commands initialized on-demand")
        except ImportError as e:
            logger.error(f"Failed to import web search modules: {e}")
            raise ImportError(f"Web search functionality requires additional modules: {e}")

    async def _config_show_command(self, args: List[str]) -> str:
        """Show current configuration settings."""
        config_manager.print_config()
        return "Configuration displayed above."

    async def _exit_command(self, args: List[str]) -> str:
        """Exit the application with proper cleanup."""
        # Clean up web search sessions if they exist
        if hasattr(self, 'web_commands') and hasattr(self.web_commands, 'search_handler'):
            try:
                await self.web_commands.search_handler.close()
                logger.info("Web search session closed successfully")
            except Exception as e:
                logger.error(f"Error closing web search session: {e}")

        return ":exit"