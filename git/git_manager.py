#!/usr/bin/env python3

import asyncio
import subprocess
import os
import aiofiles
from typing import List

from config.config_manager import logger


class GitManager:
    """Manages Git operations for projects."""

    def __init__(self):
        self.has_git = self._check_git_installed()
        if self.has_git:
            logger.info("Git support initialized")
        else:
            logger.warning("Git not found on the system, Git integration disabled")

    def _check_git_installed(self) -> bool:
        """Check if Git is installed on the system."""
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    async def init_repo(self, project_dir: str) -> str:
        """Initialize a Git repository in the specified directory."""
        if not self.has_git:
            return "Git is not installed on the system."

        try:
            process = await asyncio.create_subprocess_exec(
                "git", "init",
                cwd=project_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Create .gitignore
                gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
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
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/
env/

# IDE files
.idea/
.vscode/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db

# Project specific
backups/
logs/
"""
                gitignore_path = os.path.join(project_dir, ".gitignore")
                async with aiofiles.open(gitignore_path, 'w') as f:
                    await f.write(gitignore_content)

                logger.info(f"Git repository initialized in {project_dir}")
                return f"Git repository initialized in {project_dir}\n{stdout.decode().strip()}"
            else:
                error = stderr.decode().strip()
                logger.error(f"Git init failed: {error}")
                return f"Git initialization failed: {error}"

        except Exception as e:
            logger.error(f"Error in git init: {e}")
            return f"Error initializing Git repository: {e}"

    async def add_files(self, project_dir: str, patterns: List[str] = None) -> str:
        """Add files to Git staging area."""
        if not self.has_git:
            return "Git is not installed on the system."

        if not patterns:
            patterns = ["."]  # Add all files by default

        try:
            results = []
            for pattern in patterns:
                process = await asyncio.create_subprocess_exec(
                    "git", "add", pattern,
                    cwd=project_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error = stderr.decode().strip()
                    results.append(f"Failed to add {pattern}: {error}")
                    logger.error(f"Git add failed for {pattern}: {error}")
                else:
                    results.append(f"Added {pattern} to staging area")

            if all("Failed" not in result for result in results):
                logger.info(f"Files added to Git staging area in {project_dir}")
                return "Files successfully added to Git staging area"
            else:
                return "\n".join(results)

        except Exception as e:
            logger.error(f"Error in git add: {e}")
            return f"Error adding files to Git repository: {e}"

    async def commit(self, project_dir: str, message: str) -> str:
        """Commit changes to the Git repository."""
        if not self.has_git:
            return "Git is not installed on the system."

        try:
            process = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", message,
                cwd=project_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Changes committed in {project_dir}: {message}")
                return f"Changes committed: {stdout.decode().strip()}"
            else:
                error = stderr.decode().strip()
                logger.error(f"Git commit failed: {error}")
                return f"Commit failed: {error}"

        except Exception as e:
            logger.error(f"Error in git commit: {e}")
            return f"Error committing changes: {e}"

    async def status(self, project_dir: str) -> str:
        """Get the status of the Git repository."""
        if not self.has_git:
            return "Git is not installed on the system."

        try:
            process = await asyncio.create_subprocess_exec(
                "git", "status",
                cwd=project_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                error = stderr.decode().strip()
                logger.error(f"Git status failed: {error}")
                return f"Git status failed: {error}"

        except Exception as e:
            logger.error(f"Error in git status: {e}")
            return f"Error getting Git status: {e}"

    async def create_branch(self, project_dir: str, branch_name: str) -> str:
        """Create a new Git branch."""
        if not self.has_git:
            return "Git is not installed on the system."

        try:
            process = await asyncio.create_subprocess_exec(
                "git", "checkout", "-b", branch_name,
                cwd=project_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Created branch {branch_name} in {project_dir}")
                return f"Branch '{branch_name}' created: {stdout.decode().strip()}"
            else:
                error = stderr.decode().strip()
                logger.error(f"Git branch creation failed: {error}")
                return f"Branch creation failed: {error}"

        except Exception as e:
            logger.error(f"Error creating Git branch: {e}")
            return f"Error creating Git branch: {e}"