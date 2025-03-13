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
            ":model": self._model_command,
            ":clear": self._clear_command,
            ":dialogue": self._dialogue_command,
            ":web": self._web_command,
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
        """Project management commands."""
        if not args:
            return "Usage: :project create|list|info|set|rename|remove|analyze|debug|improve <args>"

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

        elif subcmd == "analyze":

            if len(args) < 2 and not self.dev_assistant.current_project:
                return "Usage: :project analyze <name>\nOr have a current project set."

            # Get the project to analyze

            if len(args) >= 2:

                project_name = args[1]

                project = await self.dev_assistant.project_manager.get_project(project_name)

                if not project:
                    return f"Project '{project_name}' not found."

            else:

                project = self.dev_assistant.current_project

            # Make sure we have the latest file listing

            await project.scan_files()

            print(f"{Fore.CYAN}Analyzing project: {project.name}{Style.RESET_ALL}")

            print(f"Directory: {project.directory}")

            # Find Python files to analyze

            python_files = [

                os.path.join(project.directory, f)

                for f, info in project.files.items()

                if info.get('is_python', False) and not info.get('is_test', False)

            ]

            if not python_files:
                return "No Python files found to analyze."

            print(f"Found {len(python_files)} Python files to analyze.")

            # Analysis results

            results = []

            issues_count = 0

            lines_total = 0

            # Analyze each file

            for file_path in python_files:

                rel_path = os.path.relpath(file_path, project.directory)

                print(f"Analyzing {rel_path}... ", end="", flush=True)

                # Read file content

                content = await self.dev_assistant.code_handler.read_file_content(file_path)

                if content.startswith("Error reading"):
                    print(f"{Fore.RED}Error{Style.RESET_ALL}")

                    results.append(f"Error reading {rel_path}")

                    continue

                # Analyze the code

                analysis = await self.dev_assistant.code_handler.analyze_code_quality(content)

                if "error" in analysis:
                    print(f"{Fore.RED}Error{Style.RESET_ALL}")

                    results.append(f"Error analyzing {rel_path}: {analysis['error']}")

                    continue

                # Count issues

                file_issues = len(analysis["style_issues"]) + len(analysis["potential_bugs"])

                issues_count += file_issues

                lines_total += analysis["complexity"]["lines_of_code"]

                # Print result indicator

                if file_issues == 0:

                    print(f"{Fore.GREEN}Good{Style.RESET_ALL}")

                elif file_issues < 5:

                    print(f"{Fore.YELLOW}Some issues{Style.RESET_ALL}")

                else:

                    print(f"{Fore.RED}Issues found{Style.RESET_ALL}")

                # Add file summary to results

                results.append(f"File: {rel_path}")

                results.append(f"  - Lines: {analysis['complexity']['lines_of_code']}")

                results.append(f"  - Functions: {analysis['complexity']['function_count']}")

                results.append(f"  - Classes: {analysis['complexity']['class_count']}")

                results.append(f"  - Style issues: {len(analysis['style_issues'])}")

                results.append(f"  - Potential bugs: {len(analysis['potential_bugs'])}")

                results.append(f"  - Overall quality: {analysis['summary']['overall_quality']}")

                results.append("")

            # Overall project metrics

            results.insert(0, f"\n{Fore.CYAN}Project Analysis: {project.name}{Style.RESET_ALL}")

            results.insert(1, f"Total Python files: {len(python_files)}")

            results.insert(2, f"Total lines of code: {lines_total}")

            results.insert(3, f"Total issues found: {issues_count}")

            results.insert(4, "")

            # Quality score (simple calculation)

            if lines_total > 0:

                quality_ratio = issues_count / lines_total

                if quality_ratio < 0.01:

                    quality = "Excellent"

                elif quality_ratio < 0.05:

                    quality = "Good"

                elif quality_ratio < 0.1:

                    quality = "Needs improvement"

                else:

                    quality = "Poor"

            else:

                quality = "Unknown"

            results.insert(5, f"Overall code quality: {quality}")

            results.insert(6, "")

            # Create a summary report file

            report_file = os.path.join(project.directory, "code_analysis_report.md")

            async with aiofiles.open(report_file, 'w', encoding='utf-8') as f:

                await f.write(f"# Code Analysis Report for {project.name}\n\n")

                await f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                await f.write(f"## Summary\n\n")

                await f.write(f"- Total Python files: {len(python_files)}\n")

                await f.write(f"- Total lines of code: {lines_total}\n")

                await f.write(f"- Total issues found: {issues_count}\n")

                await f.write(f"- Overall code quality: {quality}\n\n")

                await f.write(f"## Files Analysis\n\n")

                for file_path in python_files:

                    rel_path = os.path.relpath(file_path, project.directory)

                    content = await self.dev_assistant.code_handler.read_file_content(file_path)

                    if content.startswith("Error reading"):
                        await f.write(f"### {rel_path}\n\nError reading file\n\n")

                        continue

                    analysis = await self.dev_assistant.code_handler.analyze_code_quality(content)

                    if "error" in analysis:
                        await f.write(f"### {rel_path}\n\nError analyzing: {analysis['error']}\n\n")

                        continue

                    await f.write(f"### {rel_path}\n\n")

                    await f.write(f"- Lines of code: {analysis['complexity']['lines_of_code']}\n")

                    await f.write(f"- Functions: {analysis['complexity']['function_count']}\n")

                    await f.write(f"- Classes: {analysis['complexity']['class_count']}\n")

                    await f.write(f"- Overall quality: {analysis['summary']['overall_quality']}\n\n")

                    if analysis["style_issues"]:

                        await f.write("#### Style Issues\n\n")

                        for issue in analysis["style_issues"]:
                            await f.write(f"- Line {issue['line']}: {issue['message']}\n")

                        await f.write("\n")

                    if analysis["potential_bugs"]:

                        await f.write("#### Potential Bugs\n\n")

                        for bug in analysis["potential_bugs"]:
                            await f.write(f"- Line {bug['line']}: {bug['message']}\n")

                        await f.write("\n")

            results.append(f"Detailed analysis report saved to: {report_file}")

            return "\n".join(results)

        elif subcmd == "debug":
            if len(args) < 2 and not self.dev_assistant.current_project:
                return "Usage: :project debug <project_name> [file_path] [--verbose]\nOr have a current project set."

            # Get the project
            if len(args) >= 2 and args[1] not in ["--verbose"]:
                if os.path.exists(args[1]):  # Check if the second arg is a file path
                    project = self.dev_assistant.current_project
                    file_path = args[1]
                    verbose_flag = "--verbose" in args
                else:  # It's a project name
                    project_name = args[1]
                    project = await self.dev_assistant.project_manager.get_project(project_name)
                    if not project:
                        return f"Project '{project_name}' not found."
                    file_path = args[2] if len(args) > 2 and args[2] not in ["--verbose"] else None
                    verbose_flag = "--verbose" in args
            else:
                project = self.dev_assistant.current_project
                file_path = None
                verbose_flag = "--verbose" in args

            if not project:
                return "No project specified or selected."

            # Refresh project files
            await project.scan_files()

            # Starting the debug report
            results = [f"{Fore.CYAN}Project Debug Report: {project.name}{Style.RESET_ALL}"]
            results.append(f"Directory: {project.directory}")
            results.append(f"Files: {len(project.files)}")
            results.append("")

            # Debug specific file or all files
            if file_path:
                # Full path if it's relative
                if not os.path.isabs(file_path):
                    full_path = os.path.join(project.directory, file_path)
                else:
                    full_path = file_path

                if not os.path.exists(full_path):
                    return f"File not found: {file_path}"

                # Read file content
                content = await self.dev_assistant.code_handler.read_file_content(full_path)
                if content.startswith("Error reading"):
                    return f"Error reading file: {file_path}"

                # Get file extension and determine language
                ext = os.path.splitext(file_path)[1][1:].lower()
                language = "python" if ext in ["py", "pyw"] else ext

                results.append(f"{Fore.YELLOW}Analyzing file: {os.path.basename(file_path)}{Style.RESET_ALL}")

                # Start with basic file info
                file_size = os.path.getsize(full_path)
                mod_time = os.path.getmtime(full_path)
                results.append(f"Size: {file_size:,} bytes")
                results.append(
                    f"Last modified: {datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')}")
                results.append("")

                if language == "python":
                    # Analyze Python code
                    analysis = await self.dev_assistant.code_handler.analyze_code_quality(content)

                    if "error" in analysis:
                        results.append(f"Error analyzing code: {analysis['error']}")
                    else:
                        results.append(f"Lines of code: {analysis['complexity']['lines_of_code']}")
                        results.append(f"Functions: {analysis['complexity']['function_count']}")
                        results.append(f"Classes: {analysis['complexity']['class_count']}")
                        results.append(f"Quality rating: {analysis['summary']['overall_quality']}")
                        results.append("")

                        # Show style issues
                        if analysis["style_issues"]:
                            results.append(f"{Fore.YELLOW}Style Issues:{Style.RESET_ALL}")
                            for issue in analysis["style_issues"][:10]:  # Limit to first 10
                                results.append(f"  Line {issue['line']}: {issue['message']}")
                            if len(analysis["style_issues"]) > 10:
                                results.append(f"  ... and {len(analysis['style_issues']) - 10} more issues.")
                            results.append("")

                        # Show potential bugs
                        if analysis["potential_bugs"]:
                            results.append(f"{Fore.RED}Potential Bugs:{Style.RESET_ALL}")
                            for bug in analysis["potential_bugs"]:
                                results.append(f"  Line {bug['line']}: {bug['message']}")
                            results.append("")

                        # Run the file if it's executable and verbose mode is on
                        if verbose_flag and language == "python":
                            results.append(f"{Fore.YELLOW}Executing file (test run):{Style.RESET_ALL}")
                            try:
                                exec_result = await self.dev_assistant.code_handler.execute_python_code(content,
                                                                                                        timeout=10)
                                results.append(exec_result)
                            except Exception as e:
                                results.append(f"Execution failed: {e}")
                            results.append("")
                else:
                    # Basic analysis for non-Python files
                    results.append(f"File type: {language} (detailed analysis not available)")
                    results.append(f"Content preview (first 10 lines):")
                    lines = content.split('\n')[:10]
                    for line in lines:
                        results.append(f"  {line}")
                    if len(content.split('\n')) > 10:
                        results.append("  ...")

            else:
                # Debug the entire project
                python_files = [f for f, info in project.files.items() if info.get('is_python', False)]
                test_files = [f for f, info in project.files.items() if info.get('is_test', False)]

                results.append(f"{Fore.YELLOW}Project Structure:{Style.RESET_ALL}")
                results.append(f"Python files: {len(python_files)}")
                results.append(f"Test files: {len(test_files)}")

                # Check for standard directories
                std_dirs = ["src", "tests", "docs", "examples"]
                for d in std_dirs:
                    if os.path.exists(os.path.join(project.directory, d)):
                        results.append(f"✓ Contains {d}/ directory")
                    else:
                        results.append(f"✗ Missing {d}/ directory")

                # Check for important files
                imp_files = ["README.md", "requirements.txt", "setup.py", ".gitignore"]
                for f in imp_files:
                    if any(file.endswith(f) for file in project.files.keys()):
                        results.append(f"✓ Contains {f}")
                    else:
                        results.append(f"✗ Missing {f}")

                # Code quality stats if we have Python files
                if python_files:
                    results.append("")
                    results.append(f"{Fore.YELLOW}Code Quality Overview:{Style.RESET_ALL}")

                    total_lines = 0
                    total_issues = 0
                    file_scores = []

                    for py_file in python_files[:10]:  # Limit to first 10 for performance
                        full_path = os.path.join(project.directory, py_file)
                        content = await self.dev_assistant.code_handler.read_file_content(full_path)
                        if not content.startswith("Error"):
                            analysis = await self.dev_assistant.code_handler.analyze_code_quality(content)
                            if "error" not in analysis:
                                lines = analysis["complexity"]["lines_of_code"]
                                issues = len(analysis["style_issues"]) + len(analysis["potential_bugs"])
                                total_lines += lines
                                total_issues += issues
                                file_scores.append((py_file, lines, issues))

                    if total_lines > 0:
                        results.append(f"Total lines analyzed: {total_lines}")
                        results.append(
                            f"Issues found: {total_issues} ({total_issues / total_lines * 100:.1f} per 100 lines)")

                        # List files with most issues
                        if file_scores:
                            results.append("")
                            results.append("Files with most issues:")
                            for file, lines, issues in sorted(file_scores, key=lambda x: x[2] / max(x[1], 1),
                                                              reverse=True)[:3]:
                                results.append(
                                    f"  {file}: {issues} issues in {lines} lines ({issues / lines * 100:.1f}% issue rate)")

                    # Check for test coverage
                    if test_files:
                        results.append("")
                        results.append(f"{Fore.YELLOW}Test Coverage:{Style.RESET_ALL}")

                        impl_files = set(f.replace("test_", "") for f in python_files if not f.startswith("test_"))
                        test_for = set(f[5:] for f in test_files if f.startswith("test_"))

                        covered = impl_files.intersection(test_for)
                        uncovered = impl_files - test_for

                        if impl_files:
                            coverage_pct = len(covered) / len(impl_files) * 100
                            results.append(
                                f"Test coverage: {coverage_pct:.1f}% ({len(covered)}/{len(impl_files)} files)")

                            if uncovered and len(uncovered) <= 5:
                                results.append("Files without tests:")
                                for f in uncovered:
                                    results.append(f"  {f}")

            # Generate detailed report file if verbose
            if verbose_flag:
                report_path = os.path.join(project.directory, "project_debug_report.txt")
                # Clean ANSI color codes for file output
                clean_results = [re.sub(r'\x1b\[[0-9;]*m', '', line) for line in results]

                async with aiofiles.open(report_path, 'w', encoding='utf-8') as f:
                    await f.write("\n".join(clean_results))

                results.append("")
                results.append(f"Detailed debug report saved to: {report_path}")

            return "\n".join(results)


        elif subcmd == "improve":

            if len(args) < 2 and not self.dev_assistant.current_project:
                return "Usage: :project improve <project_name> [--implement-suggestions] [--auto]"

            # Get the project

            if len(args) >= 2 and not args[1].startswith("--"):

                project_name = args[1]

                project = await self.dev_assistant.project_manager.get_project(project_name)

                if not project:
                    return f"Project '{project_name}' not found."

            else:

                project = self.dev_assistant.current_project

            if not project:
                return "No project specified or selected."

            implement_suggestions = "--implement-suggestions" in args

            auto_implement = "--auto" in args

            # Refresh project files

            await project.scan_files()

            results = [f"{Fore.CYAN}Project Improvement Suggestions: {project.name}{Style.RESET_ALL}"]

            results.append(f"Directory: {project.directory}")

            results.append("")

            # Analyze project structure

            results.append(f"{Fore.YELLOW}Project Structure Improvements:{Style.RESET_ALL}")

            structure_improvements = []

            # Check for standard directories

            for std_dir in ["src", "tests", "docs", "examples"]:

                if not os.path.exists(os.path.join(project.directory, std_dir)):
                    structure_improvements.append(f"Create a '{std_dir}/' directory for better organization")

            # Check for important files

            important_files = [

                ("README.md", "project documentation",
                 "# {project_name}\n\nAdd your project description here.\n\n## Installation\n\n## Usage\n\n## License\n"),

                ("requirements.txt", "dependencies", "# Project dependencies\n"),

                ("setup.py", "package installation", f"""#!/usr/bin/env python3

        from setuptools import setup, find_packages


        setup(

            name="{project.name}",

            version="0.1.0",

            description="A project created with AI Dev Assistant",

            author="Developer",

            packages=find_packages(),

            install_requires=[],

        )

        """),

                (".gitignore", "version control exclusions", """# Python

        __pycache__/

        *.py[cod]

        *$py.class

        *.so

        .Python

        build/

        develop-eggs/

        dist/

        downloads/

        eggs/

        .eggs/

        lib/

        lib64/

        parts/

        sdist/

        var/

        wheels/

        *.egg-info/

        .installed.cfg

        *.egg

        MANIFEST


        # Virtual Environment

        venv/

        env/

        ENV/


        # IDE

        .idea/

        .vscode/

        *.swp

        *.swo


        # OS

        .DS_Store

        Thumbs.db

        """),

                ("LICENSE", "licensing information", """MIT License


        Copyright (c) 2025


        Permission is hereby granted, free of charge, to any person obtaining a copy

        of this software and associated documentation files (the "Software"), to deal

        in the Software without restriction, including without limitation the rights

        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell

        copies of the Software, and to permit persons to whom the Software is

        furnished to do so, subject to the following conditions:


        The above copyright notice and this permission notice shall be included in all

        copies or substantial portions of the Software.


        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR

        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,

        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE

        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER

        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,

        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE

        SOFTWARE.

        """)

            ]

            for imp_file, desc, template in important_files:

                if not any(file.endswith(imp_file) for file in project.files.keys()):
                    structure_improvements.append(f"Add {imp_file} for {desc}")

            # Display structure improvements

            if structure_improvements:

                for i, improvement in enumerate(structure_improvements, 1):
                    results.append(f"{i}. {improvement}")

            else:

                results.append("✓ Project structure follows best practices")

            # Auto-implement structure improvements if requested

            if auto_implement and structure_improvements:

                results.append("")

                results.append(f"{Fore.GREEN}Automatically implementing structure improvements...{Style.RESET_ALL}")

                # Create standard directories

                for std_dir in ["src", "tests", "docs", "examples"]:

                    dir_path = os.path.join(project.directory, std_dir)

                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)

                        results.append(f"✓ Created directory: {std_dir}/")

                # Create important files with templates

                for imp_file, desc, template in important_files:

                    file_exists = any(file.endswith(imp_file) for file in project.files.keys())

                    if not file_exists:
                        file_path = os.path.join(project.directory, imp_file)

                        # Format template with project name

                        content = template.format(project_name=project.name)

                        # Write file

                        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                            await f.write(content)

                        results.append(f"✓ Created file: {imp_file}")

            # Analyze code quality

            python_files = [f for f, info in project.files.items() if info.get('is_python', False)]

            if python_files:

                results.append("")

                results.append(f"{Fore.YELLOW}Code Quality Improvements:{Style.RESET_ALL}")

                code_improvements = []

                file_issues = {}

                files_to_improve = []

                # Analyze Python files

                for py_file in python_files[:10]:  # Limit to first 10 for performance

                    full_path = os.path.join(project.directory, py_file)

                    content = await self.dev_assistant.code_handler.read_file_content(full_path)

                    if not content.startswith("Error"):

                        analysis = await self.dev_assistant.code_handler.analyze_code_quality(content)

                        if "error" not in analysis:

                            issues = []

                            # Check common issues

                            style_count = len(analysis["style_issues"])

                            bug_count = len(analysis["potential_bugs"])

                            if style_count > 0:
                                issues.append(f"{style_count} style issues")

                            if bug_count > 0:
                                issues.append(f"{bug_count} potential bugs")

                            # Check for complex functions

                            complex_funcs = []

                            for func_name, func_info in analysis["complexity"].get("functions", {}).items():

                                if func_info.get("complexity", 0) > 8:
                                    complex_funcs.append(func_name)

                            if complex_funcs:
                                issues.append(f"{len(complex_funcs)} complex functions")

                            if issues:
                                file_issues[py_file] = issues

                                files_to_improve.append((py_file, full_path, content, analysis))

                # Generate code improvement suggestions

                if file_issues:

                    # Find files with most issues

                    worst_files = sorted(file_issues.items(), key=lambda x: len(x[1]), reverse=True)[:3]

                    for file_path, issues in worst_files:
                        code_improvements.append(f"Refactor {file_path} to address {', '.join(issues)}")

                    # Add general suggestions based on patterns

                    test_files = [f for f, info in project.files.items() if info.get('is_test', False)]

                    implementation_files = [f for f in python_files if not any(t.endswith(f) for t in test_files)]

                    if len(test_files) < len(implementation_files) // 2:

                        code_improvements.append("Increase test coverage by adding more unit tests")

                        # Identify files without tests

                        for impl_file in implementation_files:

                            base_name = os.path.basename(impl_file)

                            test_name = f"test_{base_name}"

                            has_test = any(os.path.basename(t) == test_name for t in test_files)

                            if not has_test:
                                code_improvements.append(f"Create tests for {impl_file}")

                    for i, improvement in enumerate(code_improvements, 1):
                        results.append(f"{i}. {improvement}")

                else:

                    results.append("✓ Code quality is good in analyzed files")

                # Auto-implement code improvements if requested

                if auto_implement and files_to_improve:

                    results.append("")

                    results.append(f"{Fore.GREEN}Automatically improving code quality...{Style.RESET_ALL}")

                    # Take top 3 files with most issues to improve

                    files_to_improve.sort(key=lambda x: len(x[3]["style_issues"]) + len(x[3]["potential_bugs"]),
                                          reverse=True)

                    for rel_path, full_path, content, analysis in files_to_improve[:3]:

                        results.append(f"Improving {rel_path}...")

                        # Generate prompt for improving the file

                        prompt = f"Refactor and improve the following Python code in {rel_path}. Fix these issues:\n\n"

                        if analysis["style_issues"]:

                            prompt += "Style issues:\n"

                            for issue in analysis["style_issues"][:5]:  # Limit to first 5

                                prompt += f"- Line {issue['line']}: {issue['message']}\n"

                        if analysis["potential_bugs"]:

                            prompt += "Potential bugs:\n"

                            for bug in analysis["potential_bugs"]:
                                prompt += f"- Line {bug['line']}: {bug['message']}\n"

                        # Add complexity issues

                        complex_funcs = []

                        for func_name, func_info in analysis["complexity"].get("functions", {}).items():

                            if func_info.get("complexity", 0) > 8:
                                complex_funcs.append((func_name, func_info))

                        if complex_funcs:

                            prompt += "Complex functions to simplify:\n"

                            for func_name, func_info in complex_funcs:
                                prompt += f"- {func_name} (line {func_info['line']}, complexity: {func_info['complexity']})\n"

                        prompt += f"\nHere's the original code:\n```python\n{content}\n```\n\n"

                        prompt += "Please provide a complete refactored version of this file with improved code quality, better documentation, and fixed issues."

                        # Get AI refactored version

                        self.dev_assistant.conversation.add_message("User", prompt)

                        refactor_response = await self.dev_assistant.model_api.generate_response(

                            self.dev_assistant.model,

                            self.dev_assistant.conversation.get_full_history()

                        )

                        self.dev_assistant.conversation.add_message("Model", refactor_response)

                        # Extract code blocks

                        refactored_code = None

                        for block in re.findall(r"```(?:python)?\s*(.*?)```", refactor_response, re.DOTALL):

                            if len(block.strip()) > 50:  # Only use substantial code blocks

                                refactored_code = block

                                break

                        if refactored_code:

                            # Create backup

                            backup_dir = os.path.join(project.directory, "backups")

                            os.makedirs(backup_dir, exist_ok=True)

                            backup_file = os.path.join(backup_dir,
                                                       f"{os.path.basename(full_path)}.{int(time.time())}.bak")

                            # Copy original to backup
                            import shutil
                            shutil.copy2(full_path, backup_file)

                            # Write improved code

                            async with aiofiles.open(full_path, 'w', encoding='utf-8') as f:

                                await f.write(refactored_code)

                            results.append(f"✓ Refactored {rel_path} (original backed up)")

                        else:

                            results.append(f"✗ Failed to refactor {rel_path}")

                    # Auto-generate missing tests

                    if "Increase test coverage" in " ".join(code_improvements):

                        results.append("")

                        results.append("Generating missing unit tests...")

                        for impl_file in implementation_files[:2]:  # Limit to first 2

                            base_name = os.path.basename(impl_file)

                            test_name = f"test_{base_name}"

                            if not any(os.path.basename(t) == test_name for t in test_files):

                                impl_path = os.path.join(project.directory, impl_file)

                                impl_content = await self.dev_assistant.code_handler.read_file_content(impl_path)

                                # Create test file

                                test_dir = os.path.join(project.directory, "tests")

                                os.makedirs(test_dir, exist_ok=True)

                                test_path = os.path.join(test_dir, test_name)

                                # Generate test code

                                test_prompt = f"Create a comprehensive unit test file for this Python module:\n\n```python\n{impl_content}\n```\n\n"

                                test_prompt += "The test should use unittest framework, cover all public methods, and include appropriate assertions."

                                self.dev_assistant.conversation.add_message("User", test_prompt)

                                test_response = await self.dev_assistant.model_api.generate_response(

                                    self.dev_assistant.model,

                                    self.dev_assistant.conversation.get_full_history()

                                )

                                self.dev_assistant.conversation.add_message("Model", test_response)

                                # Extract test code

                                test_code = None

                                for block in re.findall(r"```(?:python)?\s*(.*?)```", test_response, re.DOTALL):

                                    if len(block.strip()) > 50 and "unittest" in block:  # Basic check for test code

                                        test_code = block

                                        break

                                if test_code:

                                    async with aiofiles.open(test_path, 'w', encoding='utf-8') as f:

                                        await f.write(test_code)

                                    results.append(f"✓ Created test file: {test_name}")

                                else:

                                    results.append(f"✗ Failed to generate test for {impl_file}")

                    # Update the project files list after changes

                    await project.scan_files()

            # Generate improvement plan if requested

            if implement_suggestions and not auto_implement:

                results.append("")

                results.append(f"{Fore.YELLOW}Improvement Plan:{Style.RESET_ALL}")

                # Prepare prompt for AI to generate improvement plan

                prompt = f"Generate an improvement plan for project '{project.name}' with the following issues:\n\n"

                if structure_improvements:

                    prompt += "Structure improvements needed:\n"

                    for imp in structure_improvements:
                        prompt += f"- {imp}\n"

                    prompt += "\n"

                if 'code_improvements' in locals() and code_improvements:

                    prompt += "Code improvements needed:\n"

                    for imp in code_improvements:
                        prompt += f"- {imp}\n"

                    prompt += "\n"

                prompt += "Please provide a step-by-step plan to implement these improvements."

                # Get AI response

                self.dev_assistant.conversation.add_message("User", prompt)

                plan_response = await self.dev_assistant.model_api.generate_response(

                    self.dev_assistant.model,

                    self.dev_assistant.conversation.get_full_history()

                )

                self.dev_assistant.conversation.add_message("Model", plan_response)

                # Save improvement plan to file

                plan_path = os.path.join(project.directory, "improvement_plan.md")

                async with aiofiles.open(plan_path, 'w', encoding='utf-8') as f:

                    await f.write(f"# Improvement Plan for {project.name}\n\n")

                    await f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                    await f.write(plan_response)

                results.append(plan_response)

                results.append("")

                results.append(f"Improvement plan saved to: {plan_path}")

            # If auto-implemented, update usage info

            if auto_implement:

                results.append("")

                results.append(f"{Fore.GREEN}Auto-improvements completed for project: {project.name}{Style.RESET_ALL}")

                # Add summary

                implemented = []

                if structure_improvements:
                    implemented.append(f"- Created missing directories and files")

                if 'files_to_improve' in locals() and files_to_improve:
                    implemented.append(f"- Refactored {min(len(files_to_improve), 3)} files with code quality issues")

                if 'implementation_files' in locals() and len(test_files) < len(implementation_files) // 2:
                    implemented.append(f"- Generated unit tests for missing test coverage")

                if implemented:

                    results.append("Improvements implemented:")

                    for imp in implemented:
                        results.append(imp)

            return "\n".join(results)

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