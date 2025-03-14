# project_command_handler.py
from typing import List
from colorama import Fore, Style
import datetime
import os
import re
import aiofiles

class ProjectCommandHandler:
    def __init__(self, dev_assistant):
        self.dev_assistant = dev_assistant

    async def execute(self, args: List[str]) -> str:
        if not args:
            return "Usage: :project create|list|info|set|rename|remove|analyze|debug|improve <args>"
        subcmd = args[0]
        dispatch = {
            "create": self.create_project,
            "list": self.list_projects,
            "info": self.project_info,
            "set": self.set_project,
            "rename": self.rename_project,
            "remove": self.remove_project,
            "analyze": self.analyze_project,
            "debug": self.debug_project,
            "improve": self.improve_project,
        }
        handler = dispatch.get(subcmd)
        if not handler:
            return f"Unknown project subcommand: {subcmd}"
        return await handler(args[1:])

    async def create_project(self, args: List[str]) -> str:
        if len(args) < 1:
            return "Usage: :project create <name> [description]"
        name = args[0]
        description = " ".join(args[1:]) if len(args) > 1 else ""
        return await self.dev_assistant.create_project_structure(name, description)

    async def list_projects(self, args: List[str]) -> str:
        projects = await self.dev_assistant.project_manager.list_projects()
        if not projects:
            return "No projects found."
        result = [f"{Fore.CYAN}Available Projects:{Style.RESET_ALL}"]
        for i, proj in enumerate(projects, 1):
            desc = proj['description'] if len(proj['description']) <= 50 else proj['description'][:50] + '...'
            result.append(f"{i}. {Fore.GREEN}{proj['name']}{Style.RESET_ALL} - {desc}")
            result.append(f"   Directory: {proj['directory']}")
            result.append(f"   Files: {proj.get('file_count', 'N/A')}")
        return "\n".join(result)

    async def project_info(self, args: List[str]) -> str:
        # Retrieve project either by name or use current project if no argument provided
        if len(args) >= 1:
            project_name = args[0]
            project = await self.dev_assistant.project_manager.get_project(project_name)
            if not project:
                return f"Project '{project_name}' not found."
        else:
            project = self.dev_assistant.current_project
            if not project:
                return "No project specified or selected."

        await project.scan_files()  # Update file listing

        result = [f"{Fore.CYAN}Project: {project.name}{Style.RESET_ALL}",
                  f"Description: {project.description}",
                  f"Directory: {project.directory}",
                  f"Created: {datetime.datetime.fromtimestamp(project.created_at).strftime('%Y-%m-%d %H:%M:%S')}",
                  f"Last modified: {datetime.datetime.fromtimestamp(project.last_modified).strftime('%Y-%m-%d %H:%M:%S')}"]
        if project.tags:
            result.append(f"Tags: {', '.join(project.tags)}")
        # (Include additional formatting such as file counts and tree display as needed)
        return "\n".join(result)

    async def set_project(self, args: List[str]) -> str:
        if len(args) < 1:
            return "Usage: :project set <name>"
        project_name = args[0]
        project = await self.dev_assistant.project_manager.get_project(project_name)
        if not project:
            return f"Project '{project_name}' not found."
        self.dev_assistant.current_project = project
        return f"Current project set to '{project_name}'"

    async def rename_project(self, args: List[str]) -> str:
        if len(args) < 2:
            return "Usage: :project rename <old_name> <new_name>"
        old_name = args[0]
        new_name = args[1]
        project = await self.dev_assistant.project_manager.get_project(old_name)
        if not project:
            return f"Project '{old_name}' not found."
        directory = project.directory
        project.name = new_name
        await project.save()
        # Update tracking in project manager
        del self.dev_assistant.project_manager.projects[old_name]
        self.dev_assistant.project_manager.projects[new_name] = project
        if self.dev_assistant.current_project and self.dev_assistant.current_project.name == old_name:
            self.dev_assistant.current_project = project
        return f"Project renamed from '{old_name}' to '{new_name}' (directory remains: {directory})"

    async def remove_project(self, args: List[str]) -> str:
        if len(args) < 1:
            return "Usage: :project remove <name> [--delete-files]"
        project_name = args[0]
        delete_files = "--delete-files" in args
        project = await self.dev_assistant.project_manager.get_project(project_name)
        if not project:
            return f"Project '{project_name}' not found."
        directory = project.directory
        del self.dev_assistant.project_manager.projects[project_name]
        if self.dev_assistant.current_project and self.dev_assistant.current_project.name == project_name:
            self.dev_assistant.current_project = None
        if delete_files:
            try:
                import shutil
                shutil.rmtree(directory)
                return f"Project '{project_name}' removed and all files deleted from {directory}"
            except Exception as e:
                return f"Project '{project_name}' removed from tracking, but error deleting files: {e}"
        return f"Project '{project_name}' removed from tracking. Files remain at {directory}"

    async def analyze_project(self, args: List[str]) -> str:
        # Include the existing project analysis code from _project_command "analyze" branch here
        # (You may refactor further to extract helpers if needed)
        # For brevity, we outline the steps:
        #   - Determine the project (by name or current project)
        #   - Refresh file listing via project.scan_files()
        #   - Loop through Python files, perform analysis, and format results
        return "Project analysis not yet implemented in the refactoring sample."

    async def debug_project(self, args: List[str]) -> str:
        # Extract and refactor the debug-specific logic from _project_command "debug" branch
        return "Project debug not yet implemented in the refactoring sample."

    async def improve_project(self, args: List[str]) -> str:
        # Extract and refactor the improvement-specific logic from _project_command "improve" branch
        return "Project improvement not yet implemented in the refactoring sample."
