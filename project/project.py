#!/usr/bin/env python3

import os
import time
import json
import aiofiles
from typing import Dict, Any, List

from config.config_manager import logger


class Project:
    """Represents a development project with files and settings."""

    def __init__(self, name: str, directory: str):
        self.name = name
        self.directory = directory
        self.files: Dict[str, Dict[str, Any]] = {}
        self.description = ""
        self.created_at = time.time()
        self.last_modified = time.time()
        self.tags: List[str] = []
        self.metadata: Dict[str, Any] = {}
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Project initialized: {name} in {directory}")

    async def scan_files(self) -> None:
        """Scan the project directory for files."""
        self.files = {}

        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.startswith(".") or "__pycache__" in root:
                    continue

                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, self.directory)

                try:
                    stat = os.stat(path)
                    self.files[rel_path] = {
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "extension": os.path.splitext(file)[1][1:],
                        "is_python": file.endswith(".py"),
                        "is_test": file.startswith("test_") or file.endswith("_test.py")
                    }
                except Exception as e:
                    logger.error(f"Error scanning file {path}: {e}")

        logger.info(f"Scanned {len(self.files)} files in project {self.name}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary representation."""
        return {
            "name": self.name,
            "directory": self.directory,
            "description": self.description,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "file_count": len(self.files),
            "tags": self.tags,
            "metadata": self.metadata
        }

    @classmethod
    async def load(cls, directory: str) -> 'Project':
        """Load a project from a directory."""
        project_file = os.path.join(directory, ".project.json")
        name = os.path.basename(directory)

        project = cls(name, directory)

        try:
            if os.path.exists(project_file):
                async with aiofiles.open(project_file, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    project.name = data.get("name", name)
                    project.description = data.get("description", "")
                    project.created_at = data.get("created_at", time.time())
                    project.last_modified = data.get("last_modified", time.time())
                    project.tags = data.get("tags", [])
                    project.metadata = data.get("metadata", {})
        except Exception as e:
            logger.error(f"Error loading project from {directory}: {e}")

        await project.scan_files()
        return project

    async def save(self) -> None:
        """Save project metadata to a file."""
        project_file = os.path.join(self.directory, ".project.json")

        try:
            self.last_modified = time.time()
            data = {
                "name": self.name,
                "description": self.description,
                "created_at": self.created_at,
                "last_modified": self.last_modified,
                "tags": self.tags,
                "metadata": self.metadata
            }

            async with aiofiles.open(project_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2))

            logger.info(f"Project {self.name} metadata saved")
        except Exception as e:
            logger.error(f"Error saving project metadata: {e}")