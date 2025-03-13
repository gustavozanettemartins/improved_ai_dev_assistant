#!/usr/bin/env python3

import os
import re
import shutil
import time
import argparse
from typing import List, Dict, Any, Tuple, Optional


class CodeMigrator:
    """Utility for migrating hardcoded values to configuration settings."""

    def __init__(self, backup_dir: str = None):
        """
        Initialize the migrator.

        Args:
            backup_dir: Directory to store backups of modified files
        """
        self.backup_dir = backup_dir or "migration_backups"
        os.makedirs(self.backup_dir, exist_ok=True)

        # Patterns to search for
        self.patterns = {
            # Backup directory
            r'backup_dir\s*=\s*os\.path\.join\((.*?),\s*"backups"\)': {
                'description': 'Backup directory name',
                'replacement': 'backup_config = config_manager.get("file_operations.backup", {})\n'
                               'backup_dir_name = backup_config.get("directory_name", "backups")\n'
                               'backup_dir = os.path.join({}, backup_dir_name)'
            },

            # Backup filename
            r'backup_file\s*=\s*os\.path\.join\(backup_dir,\s*f"{[^}]+}\.{int\(time\.time\(\)\)}\.bak"\)': {
                'description': 'Backup filename pattern',
                'replacement': 'naming_pattern = backup_config.get("naming_pattern", "{filename}.{timestamp}.bak")\n'
                               'backup_file = os.path.join(backup_dir, naming_pattern.format(filename={}, timestamp=int(time.time())))'
            },

            # Timeout values
            r'(await\s+[^.]+\.run_tests\([^,]+)(?:,\s*timeout\s*=\s*(\d+))?(\))': {
                'description': 'Test execution timeout',
                'replacement': 'execution_config = config_manager.get("execution", {})\n'
                               'timeouts = execution_config.get("timeouts", {})\n'
                               'timeout = timeouts.get("test_execution", {timeout})\n'
                               '{prefix}, timeout=timeout{suffix}'
            },

            # Git commit messages
            r'(await\s+self\.git_manager\.commit\([^,]+,\s*)f"([^"]+)"(\))': {
                'description': 'Git commit message',
                'replacement': 'git_config = config_manager.get("git", {})\n'
                               'commit_messages = git_config.get("commit_messages", {})\n'
                               'commit_msg = commit_messages.get("{key}", "{msg}").format({fmt})\n'
                               '{prefix}commit_msg{suffix}'
            },

            # Standard directories
            r'dirs\s*=\s*\[((?:\s*"[^"]+",?)+)\s*\]': {
                'description': 'Standard directories',
                'replacement': 'project_structure = config_manager.get("project_structure", {})\n'
                               'dirs = project_structure.get("standard_directories", [{dirs}])'
            },
        }

    def backup_file(self, file_path: str) -> str:
        """
        Create a backup of a file.

        Args:
            file_path: Path to the file to backup

        Returns:
            Path to the backup file
        """
        # Create a backup filename with timestamp
        backup_name = f"{os.path.basename(file_path)}.{int(time.time())}.bak"
        backup_path = os.path.join(self.backup_dir, backup_name)

        # Copy the file
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")

        return backup_path

    def identify_hardcoded_values(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Identify hardcoded values in a file based on patterns.

        Args:
            file_path: Path to the file to analyze

        Returns:
            List of dictionaries with information about identified hardcoded values
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        results = []

        for pattern, info in self.patterns.items():
            matches = re.finditer(pattern, content)
            for match in matches:
                results.append({
                    'pattern': pattern,
                    'description': info['description'],
                    'match': match.group(0),
                    'start': match.start(),
                    'end': match.end(),
                    'groups': match.groups(),
                    'info': info
                })

        # Sort by position in file
        results.sort(key=lambda x: x['start'])
        return results

    def generate_replacement(self, match_info: Dict[str, Any]) -> str:
        """
        Generate replacement code for a matched pattern.

        Args:
            match_info: Information about the matched pattern

        Returns:
            Replacement code
        """
        description = match_info['info']['description'].lower()
        groups = match_info['groups']
        replacement_template = match_info['info']['replacement']

        if 'test execution timeout' in description:
            # Handle test execution timeout
            prefix = groups[0]
            timeout = groups[1] or '60'  # Default to 60 if not specified
            suffix = groups[2]

            return replacement_template.format(
                prefix=prefix,
                timeout=timeout,
                suffix=suffix
            )

        elif 'git commit message' in description:
            # Handle git commit messages
            prefix = groups[0]
            msg = groups[1]
            suffix = groups[2]

            # Determine the commit message key based on the message content
            key = "create_file"
            fmt = "filename=os.path.basename(filename)"

            if "edit" in msg.lower():
                key = "edit_file"
            elif "test" in msg.lower():
                key = "add_tests"
            elif "fix" in msg.lower():
                key = "fix_code"
            elif "refactor" in msg.lower():
                key = "refactor"
                fmt = "filename=os.path.basename(filename), refactor_type=refactor_type"

            return replacement_template.format(
                prefix=prefix,
                key=key,
                msg=msg,
                fmt=fmt,
                suffix=suffix
            )

        elif 'standard directories' in description:
            # Handle standard directories
            dirs_str = groups[0].strip() if groups else ""
            # Use named parameter for formatting
            formatted_str = replacement_template.replace("{dirs}", dirs_str)
            return formatted_str

        elif 'backup directory name' in description:
            # Handle backup directory name
            path_expr = groups[0].strip() if groups and len(groups) > 0 else ""
            # Use direct string replacement to avoid formatting issues
            formatted_str = replacement_template.replace("{}", path_expr)
            return formatted_str

        elif 'backup filename pattern' in description:
            # Extract the filename part from the f-string
            filename_part = ""
            if 'match' in match_info:
                filename_match = re.search(r'f"{([^}]+)}', match_info['match'])
                if filename_match:
                    filename_part = filename_match.group(1)

            # Use direct string replacement instead of format
            formatted_str = replacement_template.replace("{}", filename_part)
            return formatted_str

        # Default: return the original match text if we can't handle it
        return match_info['match']

    def migrate_file(self, file_path: str, dry_run: bool = False) -> Tuple[int, str]:
        """
        Migrate hardcoded values in a file to configuration settings.

        Args:
            file_path: Path to the file to migrate
            dry_run: If True, don't actually modify the file

        Returns:
            Tuple of (number of changes, modified content)
        """
        # First identify hardcoded values
        hardcoded_values = self.identify_hardcoded_values(file_path)

        if not hardcoded_values:
            print(f"No hardcoded values found in {file_path}")
            return 0, ""

        print(f"Found {len(hardcoded_values)} hardcoded values in {file_path}")
        for i, value in enumerate(hardcoded_values):
            print(f"  {i + 1}. {value['description']}: {value['match'][:60]}...")

        # Create a backup
        if not dry_run:
            self.backup_file(file_path)

        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Apply the replacements in reverse order to avoid messing up positions
        modified_content = content
        changes = 0

        for value in reversed(hardcoded_values):
            try:
                replacement = self.generate_replacement(value)

                # Replace the matched text with the replacement
                modified_content = (
                        modified_content[:value['start']] +
                        replacement +
                        modified_content[value['end']:]
                )
                changes += 1
            except Exception as e:
                print(f"Error processing '{value['description']}': {e}")

        # Write the modified content back to the file
        if not dry_run and changes > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            print(f"Applied {changes} migrations to {file_path}")

        return changes, modified_content

    def batch_migrate(self, directory: str, file_pattern: str = "*.py", dry_run: bool = False) -> Dict[str, int]:
        """
        Migrate hardcoded values in multiple files.

        Args:
            directory: Directory to search for files
            file_pattern: Pattern for matching files
            dry_run: If True, don't actually modify the files

        Returns:
            Dictionary mapping file paths to number of changes made
        """
        import glob

        results = {}
        for file_path in glob.glob(os.path.join(directory, "**", file_pattern), recursive=True):
            # Skip the migration script itself
            if os.path.basename(file_path) == os.path.basename(__file__):
                continue

            changes, _ = self.migrate_file(file_path, dry_run)
            results[file_path] = changes

        return results


def main():
    """CLI entry point for the migration utility."""
    parser = argparse.ArgumentParser(description="Migrate hardcoded values to configuration settings")
    parser.add_argument("--file", help="Path to a file to migrate")
    parser.add_argument("--dir", help="Directory to search for files to migrate")
    parser.add_argument("--pattern", default="*.py", help="File pattern to match (default: *.py)")
    parser.add_argument("--backup-dir", help="Directory to store backups")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually modify files")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for more verbose output")

    args = parser.parse_args()

    migrator = CodeMigrator(backup_dir=args.backup_dir)

    if args.file:
        # Migrate a single file
        changes, _ = migrator.migrate_file(args.file, args.dry_run)
        print(f"Made {changes} changes to {args.file}")
    elif args.dir:
        # Batch migrate files in a directory
        results = migrator.batch_migrate(args.dir, args.pattern, args.dry_run)
        total_changes = sum(results.values())
        print(f"Made {total_changes} changes across {len(results)} files")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()