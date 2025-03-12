#!/usr/bin/env python3

import os
import re
import time
import datetime
from typing import Dict, List, Any, Optional

from config.config_manager import config_manager, logger
from project.project import Project
from git.git_manager import GitManager


class ProjectManager:
    """Manages multiple development projects."""

    def __init__(self, base_dir: str = config_manager.get("working_dir")):
        self.base_dir = base_dir
        self.projects: Dict[str, Project] = {}
        self.git_manager = GitManager() if config_manager.get("git_integration", True) else None
        logger.info(f"ProjectManager initialized with base directory: {base_dir}")

    async def scan_projects(self) -> None:
        """Scan for existing projects in the base directory."""
        try:
            self.projects = {}

            for item in os.listdir(self.base_dir):
                dir_path = os.path.join(self.base_dir, item)
                if os.path.isdir(dir_path) and not item.startswith("."):
                    project = await Project.load(dir_path)
                    self.projects[project.name] = project

            logger.info(f"Scanned {len(self.projects)} projects")
        except Exception as e:
            logger.error(f"Error scanning projects: {e}")

    async def create_project(self, name: str, description: str = "", tags: List[str] = None) -> Project:
        """Create a new project."""
        name = name.strip()
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)

        if not safe_name:
            safe_name = f"project_{int(time.time())}"

        # Create a unique directory name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{safe_name}_{timestamp}"
        dir_path = os.path.join(self.base_dir, dir_name)

        # Create the project
        project = Project(name, dir_path)
        project.description = description
        project.tags = tags or []
        await project.save()

        # Initialize Git if enabled
        if self.git_manager and config_manager.get("git_integration", True):
            await self.git_manager.init_repo(dir_path)

        self.projects[name] = project
        logger.info(f"Created new project: {name} in {dir_path}")

        return project

    async def get_project(self, name: str) -> Optional[Project]:
        """Get a project by name."""
        return self.projects.get(name)

    async def get_project_by_directory(self, directory: str) -> Optional[Project]:
        """Get a project by its directory."""
        dir_path = os.path.abspath(directory)
        for project in self.projects.values():
            if os.path.abspath(project.directory) == dir_path:
                return project
        return None

    async def get_or_create_project(self, name: str, description: str = "", tags: List[str] = None) -> Project:
        """Get a project or create it if it doesn't exist."""
        project = await self.get_project(name)
        if project:
            return project

        return await self.create_project(name, description, tags)

    async def list_projects(self) -> List[Dict[str, Any]]:
        """Get a list of all projects."""
        return [project.to_dict() for project in self.projects.values()]

    async def auto_commit(self, project: Project, commit_message: str = None) -> str:
        """Automatically commit changes to a project's repository."""
        if not self.git_manager or not config_manager.get("git_integration", True):
            return "Git integration is disabled."

        if not commit_message:
            commit_message = f"Auto commit at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Add all files
        add_result = await self.git_manager.add_files(project.directory)

        # Commit changes
        if "Failed" not in add_result:
            commit_result = await self.git_manager.commit(project.directory, commit_message)
            logger.info(f"Auto-committed changes to project {project.name}")
            return commit_result
        else:
            logger.warning(f"Failed to add files for auto-commit in project {project.name}")
            return add_result


# Initialize the global project manager instance
project_manager = ProjectManager()