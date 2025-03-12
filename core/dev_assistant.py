#!/usr/bin/env python3

import os
import re
import time
import fnmatch
import shutil
import datetime
import asyncio

import aiofiles
from tqdm import tqdm
from colorama import Fore, Style
from typing import List, Dict, Any
from config.config_manager import config_manager, logger
from core.performance import perf_tracker
from core.conversation import ConversationManager
from core.model_api import ModelAPI
from code.code_handler import CodeHandler
from project.project_manager import project_manager
from git.git_manager import GitManager


class DevAssistant:
    """Main class that orchestrates the development assistant operations."""

    def __init__(self, model: str = config_manager.get("default_model")):
        self.conversation = ConversationManager()
        self.model_api = ModelAPI()
        self.code_handler = CodeHandler()
        self.model = model
        self.context: List[Dict[str, Any]] = []
        self.project_manager = project_manager
        self.current_project = None
        self.git_manager = GitManager() if config_manager.get("git_integration", True) else None

        # Ensure working directory exists
        os.makedirs(config_manager.get("working_dir"), exist_ok=True)

        logger.info(f"DevAssistant initialized with model: {self.model}")

    async def set_model(self, model_name: str) -> str:
        """Set the active model."""
        available_models = config_manager.get("models", {}).keys()
        if model_name in available_models:
            self.model = model_name
            logger.info(f"Model changed to: {model_name}")
            return f"Model set to {model_name}"
        else:
            available = ", ".join(available_models)
            logger.warning(f"Requested model {model_name} not found in configuration")
            return f"Model {model_name} not found in configuration. Available models: {available}"

    async def set_context(self, files: List[str]) -> str:
        """Set files as context for the AI."""
        max_files = config_manager.get("max_context_files", 10)
        if len(files) > max_files:
            logger.warning(f"Context file limit exceeded, using first {max_files} files")
            files = files[:max_files]

        self.context = []
        included_files = []

        for file in files:
            content = await self.code_handler.read_file_content(file)
            if not content.startswith("Error reading"):
                self.context.append({
                    "filename": file,
                    "content": content,
                    "language": os.path.splitext(file)[1][1:] if os.path.splitext(file)[1] else "txt"
                })
                included_files.append(file)

        msg = f"Context set with {len(included_files)} files: {', '.join(included_files)}"
        logger.info(msg)
        perf_tracker.increment_counter("context_files_set", len(included_files))
        return msg

    async def create_from_prompt(self, prompt: str, filename: str) -> str:
        """Create a file from a prompt using the AI model."""
        start_time = perf_tracker.start_timer("create_from_prompt")

        # Format the full prompt with context
        full_prompt = prompt
        if self.context:
            context_str = "\n\n".join([
                f"File: {ctx['filename']}\n```{ctx['language']}\n{ctx['content']}\n```"
                for ctx in self.context
            ])
            full_prompt = f"{prompt}\n\nContext:\n{context_str}"

        # Add the message to conversation history
        self.conversation.add_message("User", full_prompt)

        # Generate response
        response = await self.model_api.generate_response(self.model, self.conversation.get_full_history())
        self.conversation.add_message("Model", response)

        # Extract code
        file_ext = os.path.splitext(filename)[1][1:] if os.path.splitext(filename)[1] else "py"
        codes = await self.code_handler.extract_code(response, language=file_ext)

        # Write code to file
        if codes:
            message = await self.code_handler.write_code_to_file(codes[0], filename)

            # Auto-commit if Git integration is enabled and we're in a project
            if self.git_manager and self.current_project and config_manager.get("git_integration", True):
                in_project_dir = os.path.abspath(filename).startswith(os.path.abspath(self.current_project.directory))
                if in_project_dir:
                    await self.git_manager.add_files(self.current_project.directory, [filename])
                    await self.git_manager.commit(
                        self.current_project.directory,
                        f"Create {os.path.basename(filename)} from prompt"
                    )

            perf_tracker.end_timer("create_from_prompt", start_time)
            return f"{response}\n\n{message}"
        else:
            perf_tracker.end_timer("create_from_prompt", start_time)
            return f"{response}\n\nNo code was found in the response to save to {filename}."

    async def edit_file(self, filename: str, prompt: str) -> str:
        """Edit a file with AI assistance."""
        start_time = perf_tracker.start_timer("edit_file")
        try:
            # Read the current file content
            current_content = await self.code_handler.read_file_content(filename)
            if current_content.startswith("Error reading"):
                return current_content

            # Prepare the prompt with file content and additional context
            file_language = os.path.splitext(filename)[1][1:] or "python"
            full_prompt = f"{prompt}\n\nFile to edit: {filename}\n```{file_language}\n{current_content}\n```"

            if self.context:
                context_str = "\n\n".join([
                    f"Additional file: {ctx['filename']}\n```{ctx['language']}\n{ctx['content']}\n```"
                    for ctx in self.context
                ])
                full_prompt += f"\n\nAdditional context:\n{context_str}"

            # Add the prompt to conversation history
            self.conversation.add_message("User", full_prompt)

            # Generate a response from the model
            response = await self.model_api.generate_response(self.model, self.conversation.get_full_history())
            self.conversation.add_message("Model", response)

            # Extract code from the model's response
            codes = await self.code_handler.extract_code(response, language=file_language)

            if codes:
                message = await self.code_handler.write_code_to_file(codes[0], filename)

                # Auto-commit if Git integration is enabled and the file is in a project
                if self.git_manager and self.current_project and config_manager.get("git_integration", True):
                    in_project_dir = os.path.abspath(filename).startswith(
                        os.path.abspath(self.current_project.directory))
                    if in_project_dir:
                        await self.git_manager.add_files(self.current_project.directory, [filename])
                        await self.git_manager.commit(
                            self.current_project.directory,
                            f"Edit {os.path.basename(filename)} based on prompt"
                        )

                perf_tracker.end_timer("edit_file", start_time)
                return f"{response}\n\n{message}"
            else:
                perf_tracker.end_timer("edit_file", start_time)
                return f"{response}\n\nNo code was found in the response to update {filename}."
        except Exception as e:
            error_msg = f"Error editing file: {e}"
            logger.error(error_msg, exc_info=True)
            perf_tracker.end_timer("edit_file", start_time)
            return error_msg

    async def explain_code(self, filename: str) -> str:
        """Generate a detailed explanation of code in a file."""
        try:
            # Read the file content
            content = await self.code_handler.read_file_content(filename)
            if content.startswith("Error reading"):
                return content

            # Prepare prompt
            prompt = (
                f"Please explain the following code in detail:\n\n"
                f"File: {filename}\n```{os.path.splitext(filename)[1][1:] or 'python'}\n{content}\n```\n\n"
                f"Include explanations of:\n"
                f"1. Overall purpose and functionality\n"
                f"2. How the code is structured\n"
                f"3. Key algorithms and functions\n"
                f"4. Any notable patterns or techniques used\n"
                f"5. Potential improvements or issues"
            )

            # Add to conversation history
            self.conversation.add_message("User", prompt)

            # Generate response
            response = await self.model_api.generate_response(self.model, self.conversation.get_full_history())
            self.conversation.add_message("Model", response)

            return f"Explanation of {filename}:\n\n{response}"

        except Exception as e:
            error_msg = f"Error explaining code: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def generate_tests(self, filename: str) -> str:
        """Generate unit tests for a given file."""
        try:
            # Read the file content
            content = await self.code_handler.read_file_content(filename)
            if content.startswith("Error reading"):
                return content

            # Determine test filename
            base_name = os.path.basename(filename)
            base_dir = os.path.dirname(filename)
            test_name = f"test_{base_name}" if not base_name.startswith("test_") else f"{base_name}_additional.py"
            test_path = os.path.join(base_dir, test_name)

            # Prepare prompt
            prompt = (
                f"Please create comprehensive unit tests for the following code:\n\n"
                f"File: {filename}\n```python\n{content}\n```\n\n"
                f"Generate thorough unit tests using the unittest framework. The tests should:\n"
                f"1. Test all public functions/methods\n"
                f"2. Include edge cases and error handling\n"
                f"3. Use appropriate assertions\n"
                f"4. Follow best practices for test organization\n"
                f"The test file will be saved as {test_name}."
            )

            # Add to conversation history
            self.conversation.add_message("User", prompt)

            # Generate response
            response = await self.model_api.generate_response(self.model, self.conversation.get_full_history())
            self.conversation.add_message("Model", response)

            # Extract code
            codes = await self.code_handler.extract_code(response)

            if codes:
                # Write test code
                message = await self.code_handler.write_code_to_file(codes[0], test_path)

                # Auto-commit if Git integration is enabled and we're in a project
                if self.git_manager and self.current_project and config_manager.get("git_integration", True):
                    in_project_dir = os.path.abspath(test_path).startswith(
                        os.path.abspath(self.current_project.directory))
                    if in_project_dir:
                        await self.git_manager.add_files(self.current_project.directory, [test_path])
                        await self.git_manager.commit(
                            self.current_project.directory,
                            f"Add tests for {os.path.basename(filename)}"
                        )

                return f"Generated tests for {filename}:\n\n{response}\n\n{message}"
            else:
                return f"No test code found in the response.\n\nModel's response:\n{response}"

        except Exception as e:
            error_msg = f"Error generating tests: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def debug_and_fix(self, code_file: str, test_file: str) -> str:
        """Debug and fix code to make tests pass."""
        start_time = perf_tracker.start_timer("debug_and_fix")

        try:
            # Run tests to see if they already pass
            logger.info(f"Running tests for {code_file} with {test_file}")
            test_results = await self.code_handler.run_tests(test_file)

            # Check if tests already pass
            if "Tests passed successfully" in test_results:
                perf_tracker.end_timer("debug_and_fix", start_time)
                return f"All tests passed. No fixes needed.\n\n{test_results}"

            # Get file contents
            code_content = await self.code_handler.read_file_content(code_file)
            test_content = await self.code_handler.read_file_content(test_file)

            # Prepare prompt for fixing the code
            prompt = (
                f"I have a Python file with failing tests. Please fix the code to make the tests pass.\n\n"
                f"Code file ({code_file}):\n```python\n{code_content}\n```\n\n"
                f"Test file ({test_file}):\n```python\n{test_content}\n```\n\n"
                f"Test results:\n{test_results}\n\n"
                f"Please provide the fixed code for {code_file}. Explain your changes."
            )

            # Add to conversation history
            self.conversation.add_message("User", prompt)

            # Generate response
            response = await self.model_api.generate_response(self.model, self.conversation.get_full_history())
            self.conversation.add_message("Model", response)

            # Extract code
            codes = await self.code_handler.extract_code(response)

            if codes:
                # Write the fixed code
                message = await self.code_handler.write_code_to_file(codes[0], code_file)

                # Run tests again to see if the fix worked
                new_test_results = await self.code_handler.run_tests(test_file)

                # Auto-commit if Git integration is enabled and we're in a project
                if self.git_manager and self.current_project and config_manager.get("git_integration", True):
                    in_project_dir = os.path.abspath(code_file).startswith(
                        os.path.abspath(self.current_project.directory))
                    if in_project_dir and "Tests passed successfully" in new_test_results:
                        await self.git_manager.add_files(self.current_project.directory, [code_file])
                        await self.git_manager.commit(
                            self.current_project.directory,
                            f"Fix {os.path.basename(code_file)} to pass tests"
                        )

                result = (
                    f"Original test results:\n{test_results}\n\n"
                    f"Fixed code applied: {message}\n\n"
                    f"New test results:\n{new_test_results}\n\n"
                    f"Model's explanation:\n{response}"
                )
                perf_tracker.end_timer("debug_and_fix", start_time)
                return result
            else:
                perf_tracker.end_timer("debug_and_fix", start_time)
                return f"No code fixes found in the response. Original test results:\n{test_results}\n\nModel's response:\n{response}"

        except Exception as e:
            error_msg = f"Error during debug and fix: {e}"
            logger.error(error_msg, exc_info=True)
            perf_tracker.end_timer("debug_and_fix", start_time)
            return error_msg

    async def generate_documentation_file(self, filename: str, output_format: str = "markdown") -> str:
        """Generate documentation for a code file and save it."""
        try:
            # Read the file content
            content = await self.code_handler.read_file_content(filename)
            if content.startswith("Error reading"):
                return content

            # Get file language
            file_ext = os.path.splitext(filename)[1][1:] or "py"
            language = "python" if file_ext in ["py", "pyw"] else file_ext

            # Generate documentation
            doc_content = await self.code_handler.generate_documentation(content, language, output_format)

            # Create documentation filename
            base_name = os.path.splitext(os.path.basename(filename))[0]
            doc_ext = ".md" if output_format == "markdown" else f".{output_format}"
            doc_filename = os.path.join(os.path.dirname(filename), f"{base_name}_docs{doc_ext}")

            # Write documentation file
            async with aiofiles.open(doc_filename, "w", encoding="utf-8") as f:
                await f.write(doc_content)

            logger.info(f"Documentation generated for {filename} and saved to {doc_filename}")
            return f"Documentation for {filename} generated and saved to {doc_filename}"

        except Exception as e:
            error_msg = f"Error generating documentation: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def analyze_code_quality(self, filename: str) -> str:
        """Analyze the code quality of a file."""
        try:
            # Read the file content
            content = await self.code_handler.read_file_content(filename)
            if content.startswith("Error reading"):
                return content

            # Get file language
            file_ext = os.path.splitext(filename)[1][1:] or "py"
            language = "python" if file_ext in ["py", "pyw"] else file_ext

            # Analyze code quality
            analysis = await self.code_handler.analyze_code_quality(content, language)

            # Format the results
            if "error" in analysis:
                return f"Error analyzing {filename}: {analysis['error']}"

            # Create a formatted report
            report = [f"# Code Quality Analysis for {os.path.basename(filename)}\n"]

            # Summary section
            report.append("## Summary")
            summary = analysis["summary"]
            report.append(f"- **Overall Quality**: {summary['overall_quality']}")
            report.append(f"- **Lines of Code**: {summary['lines_of_code']}")
            report.append(f"- **Functions**: {summary['functions']}")
            report.append(f"- **Classes**: {summary['classes']}")
            report.append(f"- **Style Issues**: {summary['style_issues']}")
            report.append(f"- **Potential Bugs**: {summary['potential_bugs']}")
            report.append(f"- **Imported Modules**: {summary['imported_modules']}")
            report.append("")

            # Complexity metrics
            report.append("## Complexity Metrics")
            complexity = analysis["complexity"]
            report.append(f"- **Average Line Length**: {complexity['avg_line_length']:.2f} characters")

            if complexity.get("functions"):
                report.append("\n### Function Complexity")
                for func_name, func_info in complexity["functions"].items():
                    report.append(f"- **{func_name}**:")
                    report.append(f"  - Line: {func_info['line']}")
                    report.append(f"  - Complexity: {func_info['complexity']}")
                    report.append(f"  - Parameters: {func_info['parameters']}")

            # Style issues
            if analysis["style_issues"]:
                report.append("\n## Style Issues")
                for issue in analysis["style_issues"]:
                    report.append(f"- Line {issue['line']}: {issue['message']}")

            # Potential bugs
            if analysis["potential_bugs"]:
                report.append("\n## Potential Bugs")
                for bug in analysis["potential_bugs"]:
                    report.append(f"- Line {bug['line']}: {bug['message']}")

            # Imports
            if analysis["imports"]:
                report.append("\n## Imports")
                for imp in analysis["imports"]:
                    report.append(f"- {imp}")

            return "\n".join(report)

        except Exception as e:
            error_msg = f"Error analyzing code quality: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def refactor_code(self, filename: str, refactor_type: str = "general") -> str:
        """
        Refactor code based on the specified refactoring type.

        Types include:
        - general: Overall improvement
        - performance: Optimize for speed/memory
        - readability: Improve clarity
        - structure: Better organization
        - patterns: Apply design patterns
        """
        start_time = perf_tracker.start_timer("refactor_code")

        try:
            # Read the current file content
            current_content = await self.code_handler.read_file_content(filename)
            if current_content.startswith("Error reading"):
                return current_content

            # Prepare prompt based on refactor type
            refactor_instructions = {
                "general": "Improve this code for better quality. Apply best practices, fix anti-patterns, and enhance overall structure and style.",
                "performance": "Optimize this code for better performance. Improve algorithms, reduce complexity, and minimize resource usage.",
                "readability": "Improve code readability while preserving functionality. Use better variable names, add comments, and simplify complex expressions.",
                "structure": "Refactor the code organization. Improve function/class structure, use appropriate modules/patterns, and enhance cohesion.",
                "patterns": "Apply appropriate design patterns to improve this code's design. Identify and implement patterns that fit the code's purpose."
            }

            instruction = refactor_instructions.get(refactor_type, refactor_instructions["general"])

            # Build the prompt
            prompt = (
                f"Please refactor the following code. {instruction}\n\n"
                f"File: {filename}\n```{os.path.splitext(filename)[1][1:] or 'python'}\n{current_content}\n```\n\n"
                f"Provide the refactored code with explanations of your changes."
            )

            # Add to conversation history
            self.conversation.add_message("User", prompt)

            # Generate response
            response = await self.model_api.generate_response(self.model, self.conversation.get_full_history())
            self.conversation.add_message("Model", response)

            # Extract code
            file_ext = os.path.splitext(filename)[1][1:] if os.path.splitext(filename)[1] else "py"
            codes = await self.code_handler.extract_code(response, language=file_ext)

            if codes:
                # Create backup of original file
                backup_ext = f".{int(time.time())}.backup"
                backup_filename = f"{filename}{backup_ext}"
                await self.code_handler.write_code_to_file(current_content, backup_filename)

                # Write refactored code
                message = await self.code_handler.write_code_to_file(codes[0], filename)

                # Auto-commit if Git integration is enabled and we're in a project
                if self.git_manager and self.current_project and config_manager.get("git_integration", True):
                    in_project_dir = os.path.abspath(filename).startswith(
                        os.path.abspath(self.current_project.directory))
                    if in_project_dir:
                        await self.git_manager.add_files(self.current_project.directory, [filename])
                        await self.git_manager.commit(
                            self.current_project.directory,
                            f"Refactor {os.path.basename(filename)} for {refactor_type}"
                        )

                perf_tracker.end_timer("refactor_code", start_time)
                return (
                    f"Code refactored for {refactor_type}:\n{response}\n\n"
                    f"{message}\n"
                    f"Original code backed up to {backup_filename}"
                )
            else:
                perf_tracker.end_timer("refactor_code", start_time)
                return f"No refactored code found in the response.\n\nModel's response:\n{response}"

        except Exception as e:
            error_msg = f"Error during code refactoring: {e}"
            logger.error(error_msg, exc_info=True)
            perf_tracker.end_timer("refactor_code", start_time)
            return error_msg

    async def search_code(self, query: str, file_patterns: List[str] = None) -> str:
        """
        Search for code in project files matching the query.

        Args:
            query: Search query
            file_patterns: Optional list of file patterns to search (e.g., ["*.py", "*.md"])

        Returns:
            Search results
        """
        try:
            # Default to Python files if no patterns specified
            if not file_patterns:
                file_patterns = ["*.py"]

            search_dir = os.getcwd()
            if self.current_project:
                search_dir = self.current_project.directory

            results = []
            for pattern in file_patterns:
                for root, _, files in os.walk(search_dir):
                    for file in files:
                        if fnmatch.fnmatch(file, pattern):
                            file_path = os.path.join(root, file)
                            try:
                                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                                    content = await f.read()

                                lines = content.split('\n')
                                for i, line in enumerate(lines, 1):
                                    if query.lower() in line.lower():
                                        rel_path = os.path.relpath(file_path, search_dir)
                                        context_start = max(0, i - 2)
                                        context_end = min(len(lines), i + 2)
                                        context = lines[context_start:context_end]

                                        results.append({
                                            "file": rel_path,
                                            "line": i,
                                            "text": line.strip(),
                                            "context": "\n".join(context),
                                            "match_index": line.lower().find(query.lower())
                                        })
                            except Exception as e:
                                logger.warning(f"Error reading file during search: {file_path}: {e}")

            # Format results
            if not results:
                return f"No matches found for '{query}'"

            output = [f"Search results for '{query}' ({len(results)} matches):"]

            for result in results:
                output.append(f"\n📄 {result['file']}:{result['line']}")
                output.append("```")
                output.append(result['context'])
                output.append("```")

            return "\n".join(output)

        except Exception as e:
            error_msg = f"Error during code search: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def create_project_structure(self, project_name: str, description: str) -> str:
        """
        Create a new project with standard directory structure.

        Args:
            project_name: Name of the project
            description: Description of the project

        Returns:
            Status message
        """
        try:
            # Create the project
            project = await self.project_manager.create_project(project_name, description)
            self.current_project = project

            # Create standard directories
            dirs = [
                "src",
                "tests",
                "docs",
                "data",
                "scripts",
                "examples"
            ]

            for dir_name in dirs:
                os.makedirs(os.path.join(project.directory, dir_name), exist_ok=True)

            # Create basic files
            files = {
                "README.md": f"# {project_name}\n\n{description}\n\n## Installation\n\n## Usage\n\n## License\n",
                "requirements.txt": "# Project dependencies\n",
                ".gitignore": "\n".join([
                    "# Python",
                    "__pycache__/",
                    "*.py[cod]",
                    "*.so",
                    "env/",
                    "venv/",
                    "ENV/",
                    "env.bak/",
                    "venv.bak/",
                    "*.egg-info/",
                    "# IDE",
                    ".vscode/",
                    ".idea/",
                    "# Misc",
                    ".DS_Store",
                    "Thumbs.db"
                ]),
                f"src/{project_name}/__init__.py": f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
{project_name}

{description}
\"\"\"

__version__ = "0.1.0"
"""
            }

            for file_path, content in files.items():
                full_path = os.path.join(project.directory, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                async with aiofiles.open(full_path, 'w', encoding='utf-8') as f:
                    await f.write(content)

            # Initialize Git repository
            if self.git_manager and config_manager.get("git_integration", True):
                await self.git_manager.init_repo(project.directory)
                await self.git_manager.add_files(project.directory)
                await self.git_manager.commit(project.directory, "Initial project structure")

            # Update project metadata
            project.metadata["created_by"] = "AI Dev Assistant"
            project.metadata["structure_type"] = "standard"
            await project.save()

            return (
                f"Project '{project_name}' created successfully in {project.directory}\n"
                f"Created standard directory structure and basic files."
            )

        except Exception as e:
            error_msg = f"Error creating project structure: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def list_templates(self) -> str:
        """List available templates."""
        template_dir = os.path.join(config_manager.get("working_dir"), "templates")
        if not os.path.exists(template_dir):
            return "No templates directory found."

        templates = []
        for item in os.listdir(template_dir):
            item_path = os.path.join(template_dir, item)
            if os.path.isfile(item_path):
                templates.append({"name": item, "type": "file"})
            else:
                templates.append({"name": item, "type": "directory"})

        if not templates:
            return "No templates found."

        result = ["Available Templates:"]
        for template in templates:
            result.append(f"- {template['name']} ({template['type']})")

        return "\n".join(result)

    async def use_template(self, template_name: str, output_dir: str, params: Dict[str, Any] = None) -> str:
        """
        Use a template to generate a new project or file.

        Args:
            template_name: Name of the template to use
            output_dir: Directory to write the output
            params: Parameters to use for template substitution

        Returns:
            Status message
        """
        try:
            # Find the template
            template_dir = os.path.join(config_manager.get("working_dir"), "templates")
            template_path = os.path.join(template_dir, template_name)

            if not os.path.exists(template_path):
                return f"Template '{template_name}' not found in {template_dir}"

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Default parameters
            if params is None:
                params = {}

            default_params = {
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "user": os.getenv("USER", os.getenv("USERNAME", "user")),
                "version": "0.1.0"
            }

            # Merge with default params
            for key, value in default_params.items():
                if key not in params:
                    params[key] = value

            # Process template
            if os.path.isfile(template_path):
                # Single file template
                await self._process_template_file(template_path, output_dir, params)
                return f"Template '{template_name}' applied to {output_dir}"
            else:
                # Directory template
                copied_files = []
                for root, _, files in os.walk(template_path):
                    rel_path = os.path.relpath(root, template_path)
                    target_dir = os.path.join(output_dir, rel_path) if rel_path != "." else output_dir
                    os.makedirs(target_dir, exist_ok=True)

                    for file in files:
                        src_file = os.path.join(root, file)
                        processed = await self._process_template_file(src_file, target_dir, params)
                        copied_files.append(processed)

                return f"Template '{template_name}' applied to {output_dir}\nGenerated {len(copied_files)} files"

        except Exception as e:
            error_msg = f"Error applying template: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def _process_template_file(self, template_file: str, output_dir: str, params: Dict[str, Any]) -> str:
        """Process a single template file."""
        # Read the template content
        async with aiofiles.open(template_file, 'r', encoding='utf-8') as f:
            content = await f.read()

        # Create target filename (may contain template parameters)
        base_name = os.path.basename(template_file)

        # Remove .template extension if present
        if base_name.endswith(".template"):
            base_name = base_name[:-9]

        # Apply parameters to the filename
        for key, value in params.items():
            base_name = base_name.replace(f"{{{{${key}}}}}", str(value))

        target_file = os.path.join(output_dir, base_name)

        # Apply parameters to the content
        for key, value in params.items():
            content = content.replace(f"{{{{${key}}}}}", str(value))

        # Write the processed content
        async with aiofiles.open(target_file, 'w', encoding='utf-8') as f:
            await f.write(content)

        logger.debug(f"Processed template file: {template_file} -> {target_file}")
        return target_file

    async def auto_develop(self, prompt: str, data_files: List[str] = None) -> str:
        """
        Automatically develop a complete project based on a prompt.

        This is an enhanced version of the original auto_develop that uses:
        - Async operations for better performance
        - Project management integration
        - Git version control
        - Progress reporting
        - Better error handling and recovery
        - Code quality checks
        """
        start_time = perf_tracker.start_timer("auto_develop")

        try:
            # Create project name and directory
            project_name = re.sub(r'[^a-zA-Z0-9]', '_', prompt.split()[0].lower())
            # Create a project object
            project = await self.project_manager.create_project(project_name, prompt)
            self.current_project = project
            project_dir = project.directory

            logger.info(f"Auto development started for: '{prompt}' in {project_dir}")

            print(f"{Fore.CYAN}Starting development of project: {Fore.WHITE}{project_name}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Based on prompt: {Fore.WHITE}{prompt}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Directory: {Fore.WHITE}{project_dir}{Style.RESET_ALL}\n")

            # Initialize Git repository
            if self.git_manager and config_manager.get("git_integration", True):
                await self.git_manager.init_repo(project_dir)

            # Process data files if provided
            data_file_info = await self._process_data_files(data_files, project_dir)

            # Track development progress
            results = []

            # Step 1: Generate development plan with progress indicator
            print(f"{Fore.YELLOW}Step 1/7: {Fore.WHITE}Generating development plan...{Style.RESET_ALL}")

            planning_prompt = (
                f"I need to create a Python project based on: '{prompt}'\n\n"
                f"{data_file_info}\n\n"
                f"Please provide a detailed development plan including:\n"
                f"1. List of Python files with brief descriptions\n"
                f"2. Dependencies (with versions)\n"
                f"3. Implementation approach (architecture, design patterns, etc.)\n"
                f"4. Testing strategy\n"
                f"5. Project structure\n\n"
                f"Format the response as a step-by-step plan. Focus on quality, maintainability, and best practices. Do not write code yet."
            )

            self.conversation.add_message("User", planning_prompt)
            plan_response = await self.model_api.generate_response(self.model, self.conversation.get_full_history())
            self.conversation.add_message("Model", plan_response)

            # Parse plan for files
            file_pattern = r"[a-zA-Z0-9_]+\.py"
            potential_files = re.findall(file_pattern, plan_response)
            python_files = list(set(potential_files))
            python_files = [f for f in python_files if not f.startswith(("this.py", "the.py", "a.py"))]

            results.append(f"Development Plan:\n{plan_response}\n")
            results.append(f"Identified files: {', '.join(python_files)}\n")

            # Separate implementation and test files
            implementation_files = [f for f in python_files if not f.startswith("test_")]
            test_files = [f for f in python_files if f.startswith("test_")]

            # Ensure we have test files for each implementation file
            if not test_files and implementation_files:
                test_files = [f"test_{f}" for f in implementation_files]
                results.append(f"Added test files: {', '.join(test_files)}\n")

            # Save development plan
            plan_path = os.path.join(project_dir, "development_plan.md")
            async with aiofiles.open(plan_path, "w", encoding="utf-8") as f:
                await f.write(f"# Development Plan for {project_name}\n\n{plan_response}")

            # Auto-commit plan if Git enabled
            if self.git_manager and config_manager.get("git_integration", True):
                await self.git_manager.add_files(project_dir, [plan_path])
                await self.git_manager.commit(project_dir, "Add development plan")

            # Step 2: Create directory structure
            print(f"{Fore.YELLOW}Step 2/7: {Fore.WHITE}Creating directory structure...{Style.RESET_ALL}")

            dirs = ["src", "tests", "docs", "examples"]
            for d in dirs:
                os.makedirs(os.path.join(project_dir, d), exist_ok=True)

            # Create package structure
            os.makedirs(os.path.join(project_dir, "src", project_name), exist_ok=True)
            async with aiofiles.open(os.path.join(project_dir, "src", project_name, "__init__.py"), "w",
                                     encoding="utf-8") as f:
                await f.write(f"""# {project_name} package
\"\"\"
{prompt}
\"\"\"

__version__ = "0.1.0"
""")

            # Step 3: Create implementation files with progress bar
            print(f"{Fore.YELLOW}Step 3/7: {Fore.WHITE}Creating implementation files...{Style.RESET_ALL}")

            impl_tasks = []
            for file in implementation_files:
                # Determine appropriate directory for the file
                if '/' in file or '\\' in file:
                    file_path = os.path.join(project_dir, file)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                else:
                    file_path = os.path.join(project_dir, "src", project_name, file)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                file_prompt = (
                    f"Create a Python implementation for '{file}' for the project '{prompt}'.\n\n"
                    f"Development plan:\n{plan_response}\n\n"
                    f"{data_file_info}\n\n"
                    f"Write complete, well-documented, production-quality code with:\n"
                    f"1. Comprehensive docstrings (Google style)\n"
                    f"2. Proper error handling and logging\n"
                    f"3. Type hints\n"
                    f"4. Clean, maintainable code following PEP 8\n"
                    f"5. Appropriate design patterns"
                )

                # Add to tasks list for parallel execution
                impl_tasks.append((file, file_path, file_prompt))

            # Execute implementation file creation in parallel
            with tqdm(total=len(impl_tasks), desc="Creating files", unit="file") as pbar:
                for file, file_path, file_prompt in impl_tasks:
                    # Add to conversation
                    self.conversation.add_message("User", file_prompt)
                    file_response = await self.model_api.generate_response(self.model,
                                                                           self.conversation.get_full_history())
                    self.conversation.add_message("Model", file_response)

                    # Extract and write code
                    codes = await self.code_handler.extract_code(file_response)
                    if codes:
                        await self.code_handler.write_code_to_file(codes[0], file_path)
                        results.append(f"Created file: {file}")

                        # Extract summary
                        summary = file_response.split('```')[0] if '```' in file_response else "File created."
                        results.append(f"Summary for {file}:\n{summary}\n")

                    pbar.update(1)

            # Auto-commit implementation files
            if self.git_manager and config_manager.get("git_integration", True):
                await self.git_manager.add_files(project_dir)
                await self.git_manager.commit(project_dir, "Add implementation files")

            # Step 4: Create test files
            print(f"{Fore.YELLOW}Step 4/7: {Fore.WHITE}Creating test files...{Style.RESET_ALL}")

            test_tasks = []
            for test_file in test_files:
                # Determine impl file that this test is for
                impl_file = test_file[5:] if test_file.startswith("test_") else None

                # Only proceed if we have the implementation file
                if impl_file and impl_file in implementation_files:
                    # Determine file paths
                    impl_path = os.path.join(project_dir, "src", project_name, impl_file)
                    test_file_path = os.path.join(project_dir, "tests", test_file)
                    os.makedirs(os.path.dirname(test_file_path), exist_ok=True)

                    # Read implementation content
                    impl_content = await self.code_handler.read_file_content(impl_path)

                    test_prompt = (
                        f"Create a comprehensive test file '{test_file}' for '{impl_file}'.\n\n"
                        f"Implementation code:\n```python\n{impl_content}\n```\n\n"
                        f"{data_file_info}\n\n"
                        f"Write thorough unit tests using the unittest framework with:\n"
                        f"1. Proper test fixtures (setUp/tearDown)\n"
                        f"2. Mocks and patches where appropriate\n"
                        f"3. Comprehensive test cases covering edge cases\n"
                        f"4. Clear test method names describing what's being tested"
                    )

                    # Add to tasks
                    test_tasks.append((test_file, test_file_path, test_prompt))

            # Execute test file creation in parallel
            with tqdm(total=len(test_tasks), desc="Creating tests", unit="file") as pbar:
                for test_file, test_file_path, test_prompt in test_tasks:
                    # Add to conversation
                    self.conversation.add_message("User", test_prompt)
                    test_response = await self.model_api.generate_response(self.model,
                                                                           self.conversation.get_full_history())
                    self.conversation.add_message("Model", test_response)

                    # Extract and write code
                    test_codes = await self.code_handler.extract_code(test_response)
                    if test_codes:
                        await self.code_handler.write_code_to_file(test_codes[0], test_file_path)
                        results.append(f"Created test file: {test_file}")

                    pbar.update(1)

            # Auto-commit test files
            if self.git_manager and config_manager.get("git_integration", True):
                await self.git_manager.add_files(project_dir)
                await self.git_manager.commit(project_dir, "Add test files")

            # Step 5: Run tests and debug if needed
            print(f"{Fore.YELLOW}Step 5/7: {Fore.WHITE}Running tests and fixing issues...{Style.RESET_ALL}")

            debug_tasks = []
            for test_file in test_files:
                test_file_path = os.path.join(project_dir, "tests", test_file)
                impl_file = test_file[5:] if test_file.startswith("test_") else None

                if os.path.exists(test_file_path) and impl_file:
                    impl_file_path = os.path.join(project_dir, "src", project_name, impl_file)
                    debug_tasks.append((test_file, test_file_path, impl_file, impl_file_path))

            # Run tests and fix issues in sequence (debugging is harder to parallelize)
            with tqdm(total=len(debug_tasks), desc="Testing", unit="file") as pbar:
                for test_file, test_file_path, impl_file, impl_file_path in debug_tasks:
                    # Change to project directory for test execution
                    original_dir = os.getcwd()
                    os.chdir(project_dir)

                    try:
                        # Run tests
                        test_results = await self.code_handler.run_tests(test_file_path)
                        results.append(f"Test results for {test_file}:\n{test_results}\n")

                        # Fix if needed
                        if "Tests failed" in test_results or "ERROR" in test_results:
                            results.append(f"Tests failed for {test_file}. Attempting to fix...\n")
                            debug_result = await self.debug_and_fix(impl_file_path, test_file_path)
                            results.append(f"Debug and fix results:\n{debug_result}\n")

                            # Auto-commit fixes if tests now pass
                            if self.git_manager and "Tests passed successfully" in debug_result:
                                await self.git_manager.add_files(project_dir)
                                await self.git_manager.commit(project_dir, f"Fix issues in {impl_file}")
                    finally:
                        os.chdir(original_dir)
                        pbar.update(1)

            # Step 6: Create example script and documentation
            print(f"{Fore.YELLOW}Step 6/7: {Fore.WHITE}Creating examples and documentation...{Style.RESET_ALL}")

            # Create example.py script
            example_path = os.path.join(project_dir, "examples", "example.py")
            os.makedirs(os.path.dirname(example_path), exist_ok=True)

            example_prompt = (
                f"Create an example.py script demonstrating usage of the project '{prompt}'.\n\n"
                f"Files: {', '.join(implementation_files)}\n\n"
                f"{data_file_info}\n\n"
                f"Include detailed examples of main functionality with:\n"
                f"1. Clear documentation and comments\n"
                f"2. Best practices for using the project\n"
                f"3. Any necessary data loading or setup\n"
                f"4. A main() function with command-line argument handling if appropriate"
            )

            self.conversation.add_message("User", example_prompt)
            example_response = await self.model_api.generate_response(self.model,
                                                                      self.conversation.get_full_history())
            self.conversation.add_message("Model", example_response)

            example_codes = await self.code_handler.extract_code(example_response)
            if example_codes:
                await self.code_handler.write_code_to_file(example_codes[0], example_path)
                results.append("Created example.py for usage demonstration")

            # Create documentation files
            docs_dir = os.path.join(project_dir, "docs")

            # Main README.md
            readme_path = os.path.join(project_dir, "README.md")

            readme_prompt = (
                f"Create a comprehensive README.md for the project '{prompt}'.\n\n"
                f"Files: {', '.join(python_files + ['example.py'])}\n\n"
                f"{data_file_info}\n\n"
                f"Include:\n"
                f"1. Badges (PyPI, CI status, etc.)\n"
                f"2. Detailed project description\n"
                f"3. Installation instructions\n"
                f"4. Usage examples\n"
                f"5. Features list\n"
                f"6. Test instructions\n"
                f"7. Project structure\n"
                f"8. API reference\n"
                f"9. Contributing guidelines\n"
                f"10. License information"
            )

            self.conversation.add_message("User", readme_prompt)
            readme_response = await self.model_api.generate_response(self.model,
                                                                     self.conversation.get_full_history())
            self.conversation.add_message("Model", readme_response)

            # Extract markdown content
            if "```markdown" in readme_response and "```" in readme_response:
                markdown_pattern = r"```markdown\s*(.*?)```"
                markdown_matches = re.findall(markdown_pattern, readme_response, re.DOTALL)
                readme_content = markdown_matches[0] if markdown_matches else readme_response
            else:
                readme_content = readme_response

            async with aiofiles.open(readme_path, "w", encoding="utf-8") as f:
                await f.write(readme_content)
            results.append("Created README.md file")

            # API documentation
            api_doc_path = os.path.join(docs_dir, "api.md")
            api_doc_prompt = f"Create API documentation for the project '{prompt}', including all modules, classes, and functions."

            self.conversation.add_message("User", api_doc_prompt)
            api_doc_response = await self.model_api.generate_response(self.model,
                                                                      self.conversation.get_full_history())
            self.conversation.add_message("Model", api_doc_response)

            if "```markdown" in api_doc_response and "```" in api_doc_response:
                markdown_pattern = r"```markdown\s*(.*?)```"
                markdown_matches = re.findall(markdown_pattern, api_doc_response, re.DOTALL)
                api_doc_content = markdown_matches[0] if markdown_matches else api_doc_response
            else:
                api_doc_content = api_doc_response

            async with aiofiles.open(api_doc_path, "w", encoding="utf-8") as f:
                await f.write(api_doc_content)
            results.append("Created API documentation")

            # Step 7: Create package files
            print(f"{Fore.YELLOW}Step 7/7: {Fore.WHITE}Creating package files...{Style.RESET_ALL}")

            # Create setup.py
            setup_path = os.path.join(project_dir, "setup.py")
            setup_prompt = f"Create a setup.py file for the Python package '{project_name}' with appropriate configuration based on the project '{prompt}'."

            self.conversation.add_message("User", setup_prompt)
            setup_response = await self.model_api.generate_response(self.model,
                                                                    self.conversation.get_full_history())
            self.conversation.add_message("Model", setup_response)

            setup_codes = await self.code_handler.extract_code(setup_response)
            if setup_codes:
                await self.code_handler.write_code_to_file(setup_codes[0], setup_path)
                results.append("Created setup.py file")

            # Create requirements.txt
            requirements_path = os.path.join(project_dir, "requirements.txt")
            requirements_prompt = (
                f"Based on the project '{prompt}' and the created files, list all Python dependencies with versions for a requirements.txt file."
            )

            self.conversation.add_message("User", requirements_prompt)
            requirements_response = await self.model_api.generate_response(self.model,
                                                                           self.conversation.get_full_history())
            self.conversation.add_message("Model", requirements_response)

            if "```" in requirements_response:
                req_pattern = r"```(?:text)?\s*(.*?)```"
                req_matches = re.findall(req_pattern, requirements_response, re.DOTALL)
                requirements_content = req_matches[0] if req_matches else ""
            else:
                lines = requirements_response.split("\n")
                req_lines = [line for line in lines if re.match(r"^[a-zA-Z0-9_\-\.]+[=<>~!]?=?", line.strip())]
                requirements_content = "\n".join(req_lines)

            async with aiofiles.open(requirements_path, "w", encoding="utf-8") as f:
                await f.write(requirements_content)
            results.append("Created requirements.txt file")

            # Create LICENSE file
            license_path = os.path.join(project_dir, "LICENSE")
            license_prompt = f"Create an MIT license file for the project '{project_name}'."

            self.conversation.add_message("User", license_prompt)
            license_response = await self.model_api.generate_response(self.model,
                                                                      self.conversation.get_full_history())
            self.conversation.add_message("Model", license_response)

            if "```" in license_response:
                license_pattern = r"```(?:text)?\s*(.*?)```"
                license_matches = re.findall(license_pattern, license_response, re.DOTALL)
                license_content = license_matches[0] if license_matches else license_response
            else:
                license_content = license_response

            async with aiofiles.open(license_path, "w", encoding="utf-8") as f:
                await f.write(license_content)
            results.append("Created LICENSE file")

            # Final Git commit
            if self.git_manager and config_manager.get("git_integration", True):
                await self.git_manager.add_files(project_dir)
                await self.git_manager.commit(project_dir, "Complete project setup")

            # Update project metadata
            await self.current_project.scan_files()
            self.current_project.metadata["auto_developed"] = True
            self.current_project.metadata["development_time"] = time.time() - start_time
            await self.current_project.save()

            # Generate summary
            duration = perf_tracker.end_timer("auto_develop", start_time)

            summary = (
                f"\n{Fore.GREEN}=== Project Development Complete ==={Style.RESET_ALL}\n"
                f"{Fore.CYAN}Project:{Style.RESET_ALL} {prompt}\n"
                f"{Fore.CYAN}Directory:{Style.RESET_ALL} {project_dir}\n"
                f"{Fore.CYAN}Files created:{Style.RESET_ALL} {len(self.current_project.files)}\n"
                f"{Fore.CYAN}Development time:{Style.RESET_ALL} {duration:.2f} seconds\n"
                f"\n{Fore.YELLOW}Access the project in the '{project_dir}' directory.{Style.RESET_ALL}\n"
            )

            # Print final summary with colors
            print(summary)

            return "\n".join(results) + "\n" + summary

        except Exception as e:
            error_msg = f"Error during auto development: {e}"
            logger.error(error_msg, exc_info=True)
            perf_tracker.end_timer("auto_develop", start_time)
            return error_msg

    async def _process_data_files(self, data_files: List[str], project_dir: str) -> str:
        """Process data files for auto development."""
        if not data_files:
            return ""

        data_dir = os.path.join(project_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        data_file_info = ""
        processed_files = []

        # Process each file
        for file in data_files:
            if os.path.exists(file):
                dest_path = os.path.join(data_dir, os.path.basename(file))
                shutil.copy2(file, dest_path)
                processed_files.append(os.path.basename(file))

                # Special handling for CSV files - read a sample
                if file.lower().endswith('.csv'):
                    try:
                        async with aiofiles.open(file, 'r', encoding='utf-8') as f:
                            content = await f.read(2048)  # Read at most 2KB to get headers and a few rows
                            lines = content.split('\n')
                            sample_data = "\n".join(lines[:10])  # Take up to 10 lines
                            data_file_info += f"\nCSV file {os.path.basename(file)} sample data:\n{sample_data}\n"
                    except Exception as e:
                        logger.warning(f"Failed to read sample data from {file}: {e}")
                        data_file_info += f"\nData file: {os.path.basename(file)} (unable to read sample data)\n"
                else:
                    data_file_info += f"\nData file included: {os.path.basename(file)}\n"

                logger.info(f"Copied data file {file} to {dest_path}")
            else:
                logger.warning(f"Data file {file} not found")

        if processed_files:
            data_file_info = f"\nData files provided in './data/': {', '.join(processed_files)}" + data_file_info

        return data_file_info