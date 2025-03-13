#!/usr/bin/env python3
import logging
import os
import json
import aiofiles
from typing import List
from colorama import Fore, Style

from config.config_manager import config_manager, logger
from utils.web_search import WebSearchHandler


class WebCommands:
    """Handles web-related commands in the CLI."""

    def __init__(self, web_search_handler: WebSearchHandler = None):
        """
        Initialize the WebCommands handler.

        Args:
            web_search_handler: Initialized WebSearchHandler instance or None to create a new one
        """
        self.search_handler = web_search_handler or WebSearchHandler()
        self.default_num_results = 5
        self.search_history_file = os.path.join(config_manager.get("working_dir"), "search_history.json")
        self.search_history = self._load_search_history()
        logger.info("WebCommands initialized")

    def _load_search_history(self) -> List[dict]:
        """Load search history from file."""
        try:
            if os.path.exists(self.search_history_file):
                with open(self.search_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading search history: {e}")
            return []

    async def _save_search_history(self) -> None:
        """Save search history to file."""
        try:
            # Limit history size
            max_history = config_manager.get("max_search_history", 100)
            if len(self.search_history) > max_history:
                self.search_history = self.search_history[-max_history:]

            async with aiofiles.open(self.search_history_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.search_history, indent=2))
        except Exception as e:
            logger.error(f"Error saving search history: {e}")

    async def web_search(self, args: List[str]) -> str:
        """
        Perform a web search.

        Args:
            args: Search arguments [query] [num_results]

        Returns:
            Formatted search results
        """
        if not args:
            return "Usage: :web search <query> [num_results]\nExample: :web search python development 5"

        # Parse arguments
        query = " ".join(args)
        num_results = self.default_num_results

        # Check if last argument is a number (num_results)
        if args[-1].isdigit():
            num_results = int(args[-1])
            query = " ".join(args[:-1])

        # Perform the search
        results = await self.search_handler.search(query, num_results)

        if not results:
            return f"{Fore.RED}No results found or error occurred during search.{Style.RESET_ALL}"

        # Format results
        formatted_results = [f"{Fore.CYAN}Search results for: {Fore.WHITE}{query}{Style.RESET_ALL}"]

        for i, result in enumerate(results, 1):
            formatted_results.append(f"\n{Fore.GREEN}{i}. {Fore.YELLOW}{result['title']}{Style.RESET_ALL}")
            formatted_results.append(f"   {Fore.BLUE}{result['url']}{Style.RESET_ALL}")
            formatted_results.append(f"   {result['snippet']}")

        # Add to history
        self.search_history.append({
            "query": query,
            "engine": self.search_handler.engine,
            "results_count": len(results),
            "timestamp": import_time_module_and_get_time()
        })
        await self._save_search_history()

        return "\n".join(formatted_results)

    async def set_search_engine(self, args: List[str]) -> str:
        """
        Set the search engine to use.

        Args:
            args: Engine arguments [engine_name]

        Returns:
            Status message
        """
        if not args:
            return f"Current search engine: {self.search_handler.engine}\nUsage: :web engine <engine>\nAvailable engines: google, bing, duckduckgo (or ddg)"

        engine = args[0].lower()
        success = await self.search_handler.set_engine(engine)

        if success:
            return f"{Fore.GREEN}Search engine set to: {self.search_handler.engine}{Style.RESET_ALL}"
        else:
            return f"{Fore.RED}Invalid search engine: {engine}\nAvailable engines: google, bing, duckduckgo (or ddg){Style.RESET_ALL}"

    async def show_search_history(self, args: List[str]) -> str:
        """
        Show search history.

        Args:
            args: History arguments [limit]

        Returns:
            Formatted search history
        """
        if not self.search_history:
            return "No search history found."

        # Default limit
        limit = 10

        # Parse limit argument
        if args and args[0].isdigit():
            limit = int(args[0])

        # Format history
        history = self.search_history[-limit:]

        formatted_history = [
            f"{Fore.CYAN}Recent search history (showing {len(history)} of {len(self.search_history)}){Style.RESET_ALL}"]

        for i, entry in enumerate(history, 1):
            timestamp = format_timestamp(entry.get("timestamp", 0))
            formatted_history.append(
                f"{i}. {Fore.GREEN}{entry['query']}{Style.RESET_ALL} - {entry['engine']} - {entry['results_count']} results - {timestamp}")

        return "\n".join(formatted_history)

    async def clear_search_history(self, args: List[str]) -> str:
        """
        Clear search history.

        Returns:
            Status message
        """
        self.search_history = []
        await self._save_search_history()
        return f"{Fore.GREEN}Search history cleared.{Style.RESET_ALL}"

    async def debug_web_search(self, args: List[str]) -> str:
        """
        Debug web search issues.

        Args:
            args: Command arguments

        Returns:
            Debug information
        """
        if not args:
            return "Usage: :web debug <query>"

        query = " ".join(args)
        debug_info = ["Web Search Debug Information:"]

        try:
            # Test session creation
            debug_info.append("Testing search session...")
            session = await self.search_handler._ensure_session()
            debug_info.append("✓ Session created successfully")

            # Test network connectivity
            debug_info.append("\nTesting network connectivity...")
            try:
                async with session.get("https://www.google.com", timeout=10) as response:
                    if response.status == 200:
                        debug_info.append(f"✓ Connected to Google (status: {response.status})")
                    else:
                        debug_info.append(f"✗ Google returned status code: {response.status}")
            except Exception as e:
                debug_info.append(f"✗ Cannot connect to Google: {e}")

            # Check dependencies
            debug_info.append("\nChecking dependencies:")
            try:
                import aiohttp
                debug_info.append("✓ aiohttp is installed")
            except ImportError:
                debug_info.append("✗ aiohttp is NOT installed")

            try:
                import bs4
                debug_info.append("✓ BeautifulSoup (bs4) is installed")
            except ImportError:
                debug_info.append("✗ BeautifulSoup (bs4) is NOT installed")

            # Attempt search with detailed logging
            debug_info.append(f"\nAttempting search for query: '{query}'")
            try:
                # Temporarily increase logging level
                original_level = logger.level
                logger.setLevel(logging.DEBUG)

                # Execute search
                results = await self.search_handler.search(query, 1)

                # Restore logging level
                logger.setLevel(original_level)

                if results:
                    debug_info.append(f"✓ Search returned {len(results)} results")
                    debug_info.append("\nSample result:")
                    debug_info.append(f"  Title: {results[0]['title']}")
                    debug_info.append(f"  URL: {results[0]['url']}")
                    debug_info.append(f"  Snippet: {results[0]['snippet'][:100]}...")
                else:
                    debug_info.append("✗ Search returned no results")

            except Exception as e:
                debug_info.append(f"✗ Search failed with error: {e}")
                import traceback
                debug_info.append(traceback.format_exc())

            return "\n".join(debug_info)

        except Exception as e:
            return f"Debug process failed: {e}"

    async def handle_command(self, args: List[str]) -> str:
        """
        Main command handler for web commands.

        Args:
            args: Command arguments

        Returns:
            Command result
        """
        if not args:
            return "Usage: :web <subcommand> [options]\nAvailable subcommands: search, engine, history, clear_history, debug"

        subcommand = args[0].lower()

        if subcommand == "search":
            return await self.web_search(args[1:])
        elif subcommand == "engine":
            return await self.set_search_engine(args[1:])
        elif subcommand == "history":
            return await self.show_search_history(args[1:])
        elif subcommand == "clear_history" or subcommand == "clear":
            return await self.clear_search_history(args[1:])
        elif subcommand == "debug":
            return await self.debug_web_search(args[1:])
        else:
            return f"{Fore.RED}Unknown web subcommand: {subcommand}{Style.RESET_ALL}\nAvailable subcommands: search, engine, history, clear_history, debug"


# Helper functions

def import_time_module_and_get_time():
    """Import time module and return current time to avoid circular imports."""
    import time
    return time.time()


def format_timestamp(timestamp):
    """Format a Unix timestamp into a readable string."""
    import datetime
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")