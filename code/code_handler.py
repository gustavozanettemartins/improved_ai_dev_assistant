#!/usr/bin/env python3

import os
import re
import shutil
import tempfile
import asyncio
import sys
import time
import ast
import shlex
import aiofiles
from typing import List, Dict, Any

from config.config_manager import config_manager, logger
from core.performance import perf_tracker


class CodeHandler:
    """Handles code extraction, file operations, and test execution."""

    @staticmethod
    async def extract_code(response: str, language: str = "python") -> List[str]:
        """
        Extract code blocks of a specific language from text.
        Supports multiple code block formats with or without language tags.
        """
        try:
            patterns = [
                # Regular markdown code blocks
                rf"```{language}\s*(.*?)```",
                # Generic code blocks that might be our language
                r"```\s*(.*?)```",
                # HTML style code blocks
                rf"<pre><code.*?>{language}(.*?)</code></pre>",
                # XML style code blocks (some LLMs use these)
                rf"<code language=['\"]?{language}['\"]?>(.*?)</code>"
            ]

            codes = []
            for pattern in patterns:
                matches = re.findall(pattern, response, re.DOTALL)
                codes.extend(matches)

            # If we didn't find any language-specific blocks, look for unmarked code blocks
            if not codes and language == "python":
                # Look for Python-like indentation patterns
                matches = re.findall(
                    r"(?:^|\n)(?:def|class|import|from|if|for|while|try|with)(?:\s+.+?:(?:\n(?:\s+.+\n)+))", response)
                if matches:
                    codes.extend(matches)

            # Clean up extracted code
            cleaned_codes = []
            for code in codes:
                # Trim whitespace and ensure consistent newlines
                cleaned = code.strip()
                if cleaned:
                    cleaned_codes.append(cleaned)

            perf_tracker.increment_counter("code_blocks_extracted", len(cleaned_codes))
            return cleaned_codes
        except Exception as e:
            logger.error(f"Error extracting code: {e}")
            return []

    @staticmethod
    async def write_code_to_file(code: str, filename: str, create_backup: bool = True) -> str:
        """Write code to a file with optional backup."""
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            # Create backup if file exists and backup is enabled
            if os.path.exists(filename) and create_backup and config_manager.get("backup_files", True):
                backup_dir = os.path.join(os.path.dirname(filename), "backups")
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = os.path.join(
                    backup_dir,
                    f"{os.path.basename(filename)}.{int(time.time())}.bak"
                )
                shutil.copy2(filename, backup_file)
                logger.debug(f"Created backup at {backup_file}")

            async with aiofiles.open(filename, "w", encoding="utf-8") as f:
                await f.write(code)

            logger.info(f"Code written to {filename}")
            perf_tracker.increment_counter("files_written")
            return f"Code written to {filename}."
        except Exception as e:
            error_msg = f"Error writing to {filename}: {e}"
            logger.error(error_msg)
            return error_msg

    @staticmethod
    async def read_file_content(filename: str) -> str:
        """Read content from a file."""
        try:
            async with aiofiles.open(filename, "r", encoding="utf-8") as f:
                content = await f.read()

            logger.info(f"Read content from {filename}")
            perf_tracker.increment_counter("files_read")
            return content
        except Exception as e:
            error_msg = f"Error reading {filename}: {e}"
            logger.error(error_msg)
            return error_msg

    @staticmethod
    async def move_file(source: str, destination: str) -> str:
        """Move a file from source to destination."""
        try:
            dest_dir = os.path.dirname(destination)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)

            # Create backup if destination exists
            if os.path.exists(destination) and config_manager.get("backup_files", True):
                backup_dir = os.path.join(os.path.dirname(destination), "backups")
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = os.path.join(
                    backup_dir,
                    f"{os.path.basename(destination)}.{int(time.time())}.bak"
                )
                shutil.copy2(destination, backup_file)

            shutil.move(source, destination)
            logger.info(f"Moved file from {source} to {destination}")
            perf_tracker.increment_counter("files_moved")
            return f"Moved file from {source} to {destination}."
        except Exception as e:
            error_msg = f"Error moving file: {e}"
            logger.error(error_msg)
            return error_msg

    @staticmethod
    async def execute_python_code(code: str, timeout: int = 30, safe_mode: bool = True) -> str:
        """
        Execute Python code in a controlled environment with timeout and safety restrictions.

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds
            safe_mode: If True, use restricted execution environment

        Returns:
            String containing execution results or error messages
        """
        # Create a unique temporary file for the code
        fd, temp_path = tempfile.mkstemp(suffix='.py', prefix='ai_dev_exec_')
        os.close(fd)

        try:
            # Extract potential pip install commands and separate them
            lines = code.splitlines()
            pip_commands = []
            code_lines = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("pip install") or stripped.startswith("!pip install"):
                    pip_commands.append(stripped.replace("!pip", "pip"))
                else:
                    code_lines.append(line)

            # Process pip install commands if any
            install_output = []
            if pip_commands:
                for cmd in pip_commands:
                    cmd_parts = shlex.split(cmd)
                    if len(cmd_parts) >= 3:
                        module_indices = [i for i, part in enumerate(cmd_parts) if part == "install"]
                        if module_indices:
                            module_index = module_indices[0]
                            if module_index + 1 < len(cmd_parts):
                                modules = cmd_parts[module_index + 1:]
                                try:
                                    if safe_mode:
                                        install_output.append(
                                            f"🔒 Safe mode: Package installation of {' '.join(modules)} skipped")
                                    else:
                                        result = await asyncio.create_subprocess_exec(
                                            sys.executable, "-m", "pip", "install", *modules,
                                            stdout=asyncio.subprocess.PIPE,
                                            stderr=asyncio.subprocess.PIPE
                                        )
                                        stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=60)
                                        install_output.append(
                                            f"Installed {' '.join(modules)}:\n"
                                            f"{stdout.decode().strip()}\n{stderr.decode().strip()}"
                                        )
                                except asyncio.TimeoutError:
                                    install_output.append(f"⚠️ Package installation for {' '.join(modules)} timed out")
                                except Exception as e:
                                    install_output.append(f"⚠️ Error during installation: {e}")

            # Write the python code to the temporary file
            final_code = "\n".join(code_lines)

            # Add sandbox restrictions if in safe mode
            if safe_mode:
                # Add restricted builtins context
                restricted_header = """
import builtins
import os
import sys
import importlib
from functools import wraps

# Block potentially dangerous functions
_blocked_attributes = [
    'system', 'popen', 'spawn', 'exec', 'eval', 'rmdir', 'remove', 'unlink',
    'rmtree', 'open.__defaults__', 'fork', 'execve'
]

# Create restricted versions of modules
class RestrictedModule:
    def __init__(self, real_module, blocked_attrs):
        self._real_module = real_module
        self._blocked_attrs = blocked_attrs

    def __getattr__(self, name):
        if name in self._blocked_attrs:
            raise PermissionError(f"Access to {name} is restricted for security")
        return getattr(self._real_module, name)

# Restrict os module
_original_os = os
os = RestrictedModule(os, _blocked_attributes)  # noqa
sys.modules['os'] = os

# Restrict subprocess module
sys.modules['subprocess'] = None

# Custom print to capture output
_original_print = print
_output_buffer = []

@wraps(_original_print)
def _safe_print(*args, **kwargs):
    # Replace file parameter with our capturing mechanism
    kwargs.pop('file', None)
    s = " ".join(str(arg) for arg in args)
    _output_buffer.append(s)
    _original_print(s, **kwargs)

print = _safe_print  # noqa

# Prevent importing restricted modules
_original_import = builtins.__import__

@wraps(_original_import)
def _safe_import(name, *args, **kwargs):
    restricted_modules = [
        'subprocess', 'multiprocessing', 'socket', 'shutil'
    ]
    if name in restricted_modules:
        raise ImportError(f"Import of {name} is restricted for security")
    return _original_import(name, *args, **kwargs)

builtins.__import__ = _safe_import

# Add traceback for debugging
import traceback
"""
                final_code = restricted_header + "\n\n" + final_code + "\n\n" + """
# Print any uncaught exceptions
try:
    # Your code runs above this
    pass
except Exception as e:
    print(f"Error: {e}")
    print(traceback.format_exc())
finally:
    # This will be used to retrieve the output
    if '_output_buffer' in locals():
        print("\\n".join(_output_buffer))
"""

            # Write the code to the temp file
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                await f.write(final_code)

            # Execute in a separate process with timeout
            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout_str = stdout.decode(errors='replace').strip() if stdout else ""
                stderr_str = stderr.decode(errors='replace').strip() if stderr else ""

                # Process the output
                if process.returncode != 0:
                    error_output = f"Execution failed with code {process.returncode}:\n{stderr_str}"
                    if safe_mode:
                        error_output = error_output.replace(temp_path, "<script>")
                    return "\n".join(install_output + [error_output])

                output = stdout_str
                if stderr_str:
                    output += f"\n\n--- Warnings/Errors ---\n{stderr_str}"

                if safe_mode:
                    output = output.replace(temp_path, "<script>")

                return "\n".join(install_output + [output])

            except asyncio.TimeoutError:
                # Force terminate the process
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    process.kill()

                return "\n".join(install_output + [f"⚠️ Execution timed out after {timeout} seconds"])

        except Exception as e:
            logger.error(f"Error during code execution: {str(e)}", exc_info=True)
            return f"Error during code execution: {str(e)}"
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                logger.error(f"Error removing temporary file {temp_path}: {e}")

    @staticmethod
    async def run_tests(test_file: str, verbosity: int = 2, timeout: int = 60) -> str:
        """Run unit tests with improved output handling and timeout."""
        try:
            # Ensure test file exists
            if not os.path.exists(test_file):
                return f"Test file {test_file} does not exist."

            # Run tests in a separate process
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "unittest", test_file, f"-v{verbosity}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout_str = stdout.decode(errors='replace').strip() if stdout else ""
                stderr_str = stderr.decode(errors='replace').strip() if stderr else ""

                # Format the output
                if process.returncode == 0:
                    result = f"✅ Tests passed successfully:\n{stdout_str}"
                else:
                    result = f"❌ Tests failed:\n{stdout_str}\n\n{stderr_str}"

                logger.info(f"Tests executed from {test_file}, return code: {process.returncode}")
                return result

            except asyncio.TimeoutError:
                # Force terminate the process
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    process.kill()

                return f"⚠️ Test execution timed out after {timeout} seconds"

        except Exception as e:
            error_msg = f"Error running tests: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    @staticmethod
    async def analyze_code_quality(code: str, language: str = "python") -> Dict[str, Any]:
        """
        Analyze code quality using various metrics.

        For Python, this includes:
        - Code complexity (using ast module)
        - Style issues (PEP8 approximation)
        - Potential bugs/anti-patterns
        - Import analysis

        Returns a dictionary with analysis results.
        """
        if language != "python":
            return {"error": f"Code quality analysis not supported for {language} yet"}

        result = {
            "complexity": {},
            "style_issues": [],
            "potential_bugs": [],
            "imports": [],
            "summary": {}
        }

        try:
            # Parse the code
            tree = ast.parse(code)

            # Analyze imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for name in node.names:
                            imports.append(f"{node.module}.{name.name}")

            result["imports"] = sorted(imports)

            # Count function and class definitions
            function_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

            # Calculate complexity metrics
            lines = len(code.splitlines())
            complexity = {
                "lines_of_code": lines,
                "function_count": function_count,
                "class_count": class_count,
                "avg_line_length": sum(len(line) for line in code.splitlines()) / max(lines, 1)
            }

            # Function complexity (counting branches as a simple metric)
            functions = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Count branches (if, for, while, etc.)
                    branches = 0
                    for child in ast.walk(node):
                        if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                            branches += 1

                    # Count parameters
                    params = len(node.args.args)

                    functions[node.name] = {
                        "complexity": branches,
                        "parameters": params,
                        "line": node.lineno
                    }

            complexity["functions"] = functions
            result["complexity"] = complexity

            # Basic style checking
            lines = code.splitlines()
            for i, line in enumerate(lines, 1):
                # Check line length (PEP8 recommends 79 characters)
                if len(line) > 100:
                    result["style_issues"].append({
                        "line": i,
                        "type": "line_length",
                        "message": f"Line too long ({len(line)} > 100 characters)"
                    })

                # Check indentation (should be multiples of 4 for Python)
                if line.strip() and (len(line) - len(line.lstrip())) % 4 != 0:
                    result["style_issues"].append({
                        "line": i,
                        "type": "indentation",
                        "message": "Indentation should be a multiple of 4 spaces"
                    })

                # Check for trailing whitespace
                if line.rstrip() != line:
                    result["style_issues"].append({
                        "line": i,
                        "type": "trailing_whitespace",
                        "message": "Line has trailing whitespace"
                    })

            # Check for potential bugs and anti-patterns
            for node in ast.walk(tree):
                # Check for bare except
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    result["potential_bugs"].append({
                        "line": node.lineno,
                        "type": "bare_except",
                        "message": "Use of bare 'except:' (consider catching specific exceptions)"
                    })

                # Check for mutable default arguments
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            result["potential_bugs"].append({
                                "line": node.lineno,
                                "type": "mutable_default",
                                "message": f"Function '{node.name}' uses mutable default argument"
                            })

            # Generate summary
            result["summary"] = {
                "lines_of_code": complexity["lines_of_code"],
                "functions": function_count,
                "classes": class_count,
                "style_issues": len(result["style_issues"]),
                "potential_bugs": len(result["potential_bugs"]),
                "imported_modules": len(result["imports"]),
                "overall_quality": "Good" if len(result["potential_bugs"]) == 0 and len(result["style_issues"]) < 5 else
                "Moderate" if len(result["potential_bugs"]) < 3 and len(result["style_issues"]) < 15 else
                "Needs improvement"
            }

            return result

        except SyntaxError as e:
            # Return syntax error information
            return {
                "error": "Syntax error in code",
                "details": str(e),
                "line": e.lineno,
                "offset": e.offset
            }
        except Exception as e:
            logger.error(f"Error analyzing code quality: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    async def generate_documentation(code: str, language: str = "python", doc_format: str = "markdown") -> str:
        """
        Generate documentation from code.

        Args:
            code: Source code to document
            language: Programming language
            doc_format: Output format (markdown, rst, html)

        Returns:
            Generated documentation as a string
        """
        if language != "python":
            return f"Documentation generation not yet supported for {language}"

        try:
            tree = ast.parse(code)

            # Extract module docstring
            module_doc = ast.get_docstring(tree) or "No module documentation"

            # Extract classes and their methods
            classes = {}
            functions = []

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_doc = ast.get_docstring(node) or "No class documentation"
                    methods = {}

                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_doc = ast.get_docstring(item) or "No method documentation"
                            params = [arg.arg for arg in item.args.args if arg.arg != 'self']
                            methods[item.name] = {
                                "doc": method_doc,
                                "params": params,
                                "line": item.lineno
                            }

                    classes[node.name] = {
                        "doc": class_doc,
                        "methods": methods,
                        "line": node.lineno
                    }

                elif isinstance(node, ast.FunctionDef):
                    func_doc = ast.get_docstring(node) or "No function documentation"
                    params = [arg.arg for arg in node.args.args]
                    functions.append({
                        "name": node.name,
                        "doc": func_doc,
                        "params": params,
                        "line": node.lineno
                    })

            # Generate documentation based on format
            if doc_format == "markdown":
                return CodeHandler._generate_markdown_docs(module_doc, classes, functions)
            elif doc_format == "rst":
                return CodeHandler._generate_rst_docs(module_doc, classes, functions)
            elif doc_format == "html":
                return CodeHandler._generate_html_docs(module_doc, classes, functions)
            else:
                return f"Unsupported documentation format: {doc_format}"

        except SyntaxError as e:
            return f"Syntax error in code: {e}"
        except Exception as e:
            logger.error(f"Error generating documentation: {e}", exc_info=True)
            return f"Error generating documentation: {e}"

    @staticmethod
    def _generate_markdown_docs(module_doc: str, classes: Dict[str, Any], functions: List[Dict[str, Any]]) -> str:
        """Generate Markdown documentation."""
        lines = ["# Module Documentation\n", module_doc, "\n"]

        if functions:
            lines.append("\n## Functions\n")
            for func in functions:
                lines.append(f"### `{func['name']}({', '.join(func['params'])})`\n")
                lines.append(f"*Line: {func['line']}*\n")
                lines.append(func['doc'])
                lines.append("\n")

        if classes:
            lines.append("\n## Classes\n")
            for class_name, class_info in classes.items():
                lines.append(f"### `{class_name}`\n")
                lines.append(f"*Line: {class_info['line']}*\n")
                lines.append(class_info['doc'])
                lines.append("\n")

                if class_info['methods']:
                    lines.append("\n#### Methods\n")
                    for method_name, method_info in class_info['methods'].items():
                        params_str = ', '.join(
                            ['self'] + method_info['params']) if method_name != '__init__' else ', '.join(
                            ['self'] + method_info['params'])
                        lines.append(f"##### `{method_name}({params_str})`\n")
                        lines.append(f"*Line: {method_info['line']}*\n")
                        lines.append(method_info['doc'])
                        lines.append("\n")

        return "\n".join(lines)

    @staticmethod
    def _generate_rst_docs(module_doc: str, classes: Dict[str, Any], functions: List[Dict[str, Any]]) -> str:
        """Generate reStructuredText documentation."""
        lines = ["Module Documentation", "===================", "", module_doc, ""]

        if functions:
            lines.append("\nFunctions", "---------", "")
            for func in functions:
                lines.append(f"{func['name']}({', '.join(func['params'])})")
                lines.append("~" * (len(func['name']) + len(', '.join(func['params'])) + 2))
                lines.append(f"*Line: {func['line']}*")
                lines.append("")
                lines.append(func['doc'])
                lines.append("")

        if classes:
            lines.append("\nClasses", "-------", "")
            for class_name, class_info in classes.items():
                lines.append(f"{class_name}")
                lines.append("~" * len(class_name))
                lines.append(f"*Line: {class_info['line']}*")
                lines.append("")
                lines.append(class_info['doc'])
                lines.append("")

                if class_info['methods']:
                    lines.append("\nMethods:")
                    lines.append("")
                    for method_name, method_info in class_info['methods'].items():
                        params_str = ', '.join(
                            ['self'] + method_info['params']) if method_name != '__init__' else ', '.join(
                            ['self'] + method_info['params'])
                        lines.append(f"{method_name}({params_str})")
                        lines.append("^" * (len(method_name) + len(params_str) + 2))
                        lines.append(f"*Line: {method_info['line']}*")
                        lines.append("")
                        lines.append(method_info['doc'])
                        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _generate_html_docs(module_doc: str, classes: Dict[str, Any], functions: List[Dict[str, Any]]) -> str:
        """Generate HTML documentation."""
        html = ["<!DOCTYPE html>", "<html>", "<head>",
                "<title>Module Documentation</title>",
                "<style>",
                "body { font-family: Arial, sans-serif; margin: 20px; }",
                "h1, h2, h3, h4 { color: #333366; }",
                "code { background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; }",
                ".method { margin-left: 20px; }",
                ".line-info { color: #666; font-style: italic; font-size: 0.9em; }",
                "</style>",
                "</head>",
                "<body>",
                "<h1>Module Documentation</h1>",
                f"<p>{module_doc}</p>"]

        if functions:
            html.append("<h2>Functions</h2>")
            for func in functions:
                html.append(f"<h3><code>{func['name']}({', '.join(func['params'])})</code></h3>")
                html.append(f"<p class='line-info'>Line: {func['line']}</p>")
                html.append(f"<p>{func['doc']}</p>")

        if classes:
            html.append("<h2>Classes</h2>")
            for class_name, class_info in classes.items():
                html.append(f"<h3><code>{class_name}</code></h3>")
                html.append(f"<p class='line-info'>Line: {class_info['line']}</p>")
                html.append(f"<p>{class_info['doc']}</p>")

                if class_info['methods']:
                    html.append("<h4>Methods</h4>")
                    for method_name, method_info in class_info['methods'].items():
                        params_str = ', '.join(
                            ['self'] + method_info['params']) if method_name != '__init__' else ', '.join(
                            ['self'] + method_info['params'])
                        html.append("<div class='method'>")
                        html.append(f"<h4><code>{method_name}({params_str})</code></h4>")
                        html.append(f"<p class='line-info'>Line: {method_info['line']}</p>")
                        html.append(f"<p>{method_info['doc']}</p>")
                        html.append("</div>")

        html.extend(["</body>", "</html>"])
        return "\n".join(html)