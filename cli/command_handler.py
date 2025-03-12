#!/usr/bin/env python3

import os
import shlex
import datetime
from typing import List
from colorama import Fore, Style
from config.config_manager import config_manager, logger
from core.performance import perf_tracker
from core.dev_assistant import DevAssistant

class CommandHandler:
    """Handles command parsing and execution for the CLI interface."""

    def __init__(self, dev_assistant: DevAssistant):
        self.dev_assistant = dev_assistant
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
            ":search": self._search_command,
            ":template": self._template_command,
            ":metrics": self._metrics_command,
            ":config": self._config_command,
            ":model": self._model_command,
            ":clear": self._clear_command,
            ":exit": self._exit_command
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
            (":project", "create|list|info|set <args>", "Project management commands"),
            (":git", "init|add|commit|status <args>", "Git operations"),
            (":search", "<query> [file_pattern]", "Search for code in project"),
            (":template", "list|use <args>", "Work with project templates"),
            (":metrics", "[reset]", "Show performance metrics"),
            (":config", "get|set|show <args>", "Configuration management"),
            (":model", "[model_name]", "Get or set the active AI model"),
            (":clear", "", "Clear the terminal screen"),
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
        """Project management commands."""
        if not args:
            return "Usage: :project create|list|info|set|rename|remove <args>"

        subcmd = args[0]

        if subcmd == "create":
            if len(args) < 2:
                return "Usage: :project create <name> [description]"

            name = args[1]
            description = " ".join(args[2:]) if len(args) > 2 else ""
            return await self.dev_assistant.create_project_structure(name, description)

        elif subcmd == "list":
            projects = await self.dev_assistant.project_manager.list_projects()

            if not projects:
                return "No projects found."

            result = [f"{Fore.CYAN}Available Projects:{Style.RESET_ALL}"]
            for i, proj in enumerate(projects, 1):
                result.append(
                    f"{i}. {Fore.GREEN}{proj['name']}{Style.RESET_ALL} - {proj['description'][:50] + '...' if len(proj['description']) > 50 else proj['description']}")
                result.append(f"   Directory: {proj['directory']}")
                result.append(f"   Files: {proj['file_count']}")

            return "\n".join(result)

        elif subcmd == "info":
            if len(args) < 2 and not self.dev_assistant.current_project:
                return "Usage: :project info <name>\nOr have a current project set."

            if len(args) >= 2:
                project_name = args[1]
                project = await self.dev_assistant.project_manager.get_project(project_name)
                if not project:
                    return f"Project '{project_name}' not found."
            else:
                project = self.dev_assistant.current_project

            await project.scan_files()

            result = [f"{Fore.CYAN}Project: {project.name}{Style.RESET_ALL}"]
            result.append(f"Description: {project.description}")
            result.append(f"Directory: {project.directory}")
            result.append(
                f"Created: {datetime.datetime.fromtimestamp(project.created_at).strftime('%Y-%m-%d %H:%M:%S')}")
            result.append(
                f"Last modified: {datetime.datetime.fromtimestamp(project.last_modified).strftime('%Y-%m-%d %H:%M:%S')}")

            if project.tags:
                result.append(f"Tags: {', '.join(project.tags)}")

            python_files = [f for f, info in project.files.items() if info['is_python']]
            test_files = [f for f, info in project.files.items() if info['is_test']]

            result.append(
                f"\nFiles: {len(project.files)} total, {len(python_files)} Python files, {len(test_files)} test files")

            # Show file tree
            result.append("\nFile structure:")
            file_tree = {}
            for file in sorted(project.files.keys()):
                parts = file.split(os.sep)
                current = file_tree
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        current[part] = True  # Leaf node
                    else:
                        if part not in current:
                            current[part] = {}
                        current = current[part]

            # Print tree
            def print_tree(tree, indent=0, is_last=False, prefix=""):
                items = sorted(tree.items())
                for i, (name, subtree) in enumerate(items):
                    is_last_item = i == len(items) - 1
                    # Print current node
                    result.append(f"{prefix}{'└── ' if is_last_item else '├── '}{name}")
                    # Print children
                    if subtree is not True:  # Not a leaf node
                        new_prefix = prefix + ('    ' if is_last_item else '│   ')
                        print_tree(subtree, indent + 1, is_last_item, new_prefix)

            print_tree(file_tree)

            return "\n".join(result)

        elif subcmd == "set":
            if len(args) < 2:
                return "Usage: :project set <name>"

            project_name = args[1]
            project = await self.dev_assistant.project_manager.get_project(project_name)

            if not project:
                return f"Project '{project_name}' not found."

            self.dev_assistant.current_project = project
            return f"Current project set to '{project_name}'"

        elif subcmd == "rename":
            if len(args) < 3:
                return "Usage: :project rename <old_name> <new_name>"

            old_name = args[1]
            new_name = args[2]

            project = await self.dev_assistant.project_manager.get_project(old_name)
            if not project:
                return f"Project '{old_name}' not found."

            # Store the directory for reference
            directory = project.directory

            # Update the project name
            project.name = new_name
            await project.save()

            # Update the projects dictionary in the manager
            del self.dev_assistant.project_manager.projects[old_name]
            self.dev_assistant.project_manager.projects[new_name] = project

            # If this was the current project, update that reference too
            if self.dev_assistant.current_project and self.dev_assistant.current_project.name == old_name:
                self.dev_assistant.current_project = project

            return f"Project renamed from '{old_name}' to '{new_name}' (directory remains: {directory})"

        elif subcmd == "remove":
            if len(args) < 2:
                return "Usage: :project remove <name> [--delete-files]"

            project_name = args[1]
            delete_files = "--delete-files" in args

            project = await self.dev_assistant.project_manager.get_project(project_name)
            if not project:
                return f"Project '{project_name}' not found."

            directory = project.directory

            # Remove from projects dictionary
            del self.dev_assistant.project_manager.projects[project_name]

            # If this was the current project, clear that reference
            if self.dev_assistant.current_project and self.dev_assistant.current_project.name == project_name:
                self.dev_assistant.current_project = None

            # Optionally delete the files
            if delete_files:
                import shutil
                try:
                    shutil.rmtree(directory)
                    return f"Project '{project_name}' removed and all files deleted from {directory}"
                except Exception as e:
                    return f"Project '{project_name}' removed from tracking, but error deleting files: {e}"

            return f"Project '{project_name}' removed from tracking. Files remain at {directory}"

        else:
            return f"Unknown project subcommand: {subcmd}\nAvailable: create, list, info, set"

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

    async def _exit_command(self, args: List[str]) -> str:
        """Exit the application."""
        return ":exit"