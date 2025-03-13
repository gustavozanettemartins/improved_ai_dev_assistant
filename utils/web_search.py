import aiohttp
import asyncio
import re
import json
import urllib.parse
import random
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from config.config_manager import config_manager, logger
from core.performance import perf_tracker


class WebSearchHandler:
    """Handles web search operations using different search engines."""

    def __init__(self, engine: str = "duckduckgo"):  # Default to DuckDuckGo as it's more scraper-friendly
        """
        Initialize the WebSearchHandler.

        Args:
            engine: Search engine to use ('google', 'bing', 'duckduckgo')
        """
        self.engine = engine.lower()
        self.session = None

        # Rotate between different common user agents to seem more natural
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
        ]
        self.current_user_agent = random.choice(self.user_agents)
        logger.info(f"WebSearchHandler initialized with engine: {self.engine}")

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure aiohttp session exists with browser-like headers."""
        if self.session is None or self.session.closed:
            # Create random browser-like headers
            headers = {
                "User-Agent": self.current_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.google.com/",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1"
            }
            # Note: Using a context manager for proper cleanup
            self.session = aiohttp.ClientSession(headers=headers)
            logger.debug("Created new aiohttp ClientSession")
        return self.session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            try:
                await self.session.close()
                logger.debug("Closed aiohttp ClientSession")

                # Give the event loop a moment to actually close connections
                await asyncio.sleep(0.1)

                # Set to None to ensure we know it's closed
                self.session = None
            except Exception as e:
                logger.error(f"Error closing aiohttp session: {e}")

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Perform a web search with fallback to different engines.

        Args:
            query: Search query string
            num_results: Number of results to return

        Returns:
            List of search result dictionaries (title, url, snippet)
        """
        start_time = perf_tracker.start_timer("web_search")

        try:
            # Set the order of engines to try
            engines_to_try = [self.engine]

            # Add fallback engines if primary isn't already in the list
            for fallback in ["duckduckgo", "bing"]:
                if fallback not in engines_to_try:
                    engines_to_try.append(fallback)

            # Try each engine until one works
            results = []

            for engine in engines_to_try:
                logger.info(f"Attempting search with engine: {engine}")

                # Rotate user agent for each attempt
                self.current_user_agent = random.choice(self.user_agents)

                # Close any existing session to refresh headers
                await self.close()

                # Choose search method based on engine
                if engine == "google":
                    results = await self._search_google(query, num_results)
                elif engine == "bing":
                    results = await self._search_bing(query, num_results)
                elif engine == "duckduckgo" or engine == "ddg":
                    results = await self._search_duckduckgo(query, num_results)

                # If results found, break the loop
                if results:
                    if engine != self.engine:
                        logger.info(f"Fallback to {engine} engine successful")
                    break
                else:
                    logger.warning(f"No results from {engine}, trying next engine")

            perf_tracker.end_timer("web_search", start_time)
            perf_tracker.increment_counter("web_searches")
            return results

        except Exception as e:
            logger.error(f"Error during web search: {e}")
            perf_tracker.end_timer("web_search", start_time)
            return []

    async def _search_google(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Perform a Google search."""
        session = await self._ensure_session()

        # Format the search URL with country and language parameters to bypass region-specific challenges
        escaped_query = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={escaped_query}&num={num_results + 5}&hl=en&gl=US"

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Google search request failed with status {response.status}")
                    return []

                html = await response.text()

                # Check for security challenge or captcha
                if "Our systems have detected unusual traffic" in html or "captcha" in html.lower():
                    logger.warning("Google security challenge detected, cannot proceed with scraping")
                    return []

                # Log a small sample of the HTML for debugging
                logger.debug(f"Google search response sample: {html[:500]}...")

                # Parse the HTML with BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")

                results = []

                # Try multiple selectors for different Google layouts
                result_elements = None

                # Check if we have results divs
                for selector in ["div.g", "div.tF2Cxc", "div.yuRUbf", "div[data-sokoban-container]"]:
                    result_elements = soup.select(selector)
                    if result_elements:
                        logger.debug(f"Found {len(result_elements)} results with selector '{selector}'")
                        break

                # If no results found with primary selectors, try broader approach
                if not result_elements or len(result_elements) == 0:
                    logger.warning("Google search failed to find results with primary selectors")
                    return []

                # Process the results
                for result in result_elements[:num_results + 3]:  # Process a few extra in case some fail
                    try:
                        # Extract title
                        title_element = result.select_one("h3") or result.select_one(".LC20lb")
                        if not title_element:
                            continue

                        title = title_element.get_text().strip()
                        if not title:
                            continue

                        # Extract URL
                        link_element = result.select_one("a")
                        if not link_element:
                            continue

                        url = link_element.get("href", "")

                        # Clean up Google's redirect URLs
                        if url.startswith("/url?"):
                            url_match = re.search(r"url\?q=([^&]+)", url)
                            if url_match:
                                url = urllib.parse.unquote(url_match.group(1))

                        if not url or not url.startswith("http"):
                            continue

                        # Extract snippet
                        snippet_element = result.select_one("div.VwiC3b") or result.select_one("span.aCOpRe")
                        snippet = snippet_element.get_text().strip() if snippet_element else ""

                        if title and url:  # Even if snippet is empty, we'll keep the result
                            results.append({
                                "title": title,
                                "url": url,
                                "snippet": snippet or "(No description available)"
                            })

                        if len(results) >= num_results:
                            break

                    except Exception as e:
                        logger.warning(f"Error processing Google search result: {e}")
                        continue

                return results

        except Exception as e:
            logger.error(f"Error during Google search: {e}")
            return []

    async def _search_duckduckgo(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Perform a DuckDuckGo search."""
        session = await self._ensure_session()

        # Format the search URL
        escaped_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={escaped_query}"

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"DuckDuckGo search request failed with status {response.status}")
                    return []

                html = await response.text()

                # Log a small sample for debugging
                logger.debug(f"DuckDuckGo response sample: {html[:500]}...")

                # Parse the HTML with BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")

                results = []

                # Find all result divs
                for result in soup.select(".result"):
                    try:
                        # Extract title
                        title_element = result.select_one(".result__title")
                        if not title_element:
                            continue

                        title = title_element.get_text().strip()

                        # Extract URL
                        link_element = result.select_one(".result__title a")
                        if not link_element:
                            continue

                        # Get the actual URL, not the redirect URL
                        url = link_element.get("href", "")

                        # Extract from DuckDuckGo redirect if needed
                        if not url.startswith("http"):
                            url_match = re.search(r"uddg=([^&]+)", url)
                            if url_match:
                                url = urllib.parse.unquote(url_match.group(1))
                            else:
                                # Fallback to displayed URL
                                url_display = result.select_one(".result__url")
                                if url_display:
                                    url_text = url_display.get_text().strip()
                                    if url_text:
                                        url = f"https://{url_text}"

                        if not url or not url.startswith("http"):
                            continue

                        # Extract snippet
                        snippet_element = result.select_one(".result__snippet")
                        snippet = snippet_element.get_text().strip() if snippet_element else "(No description available)"

                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet
                        })

                        if len(results) >= num_results:
                            break
                    except Exception as e:
                        logger.warning(f"Error processing DuckDuckGo result: {e}")
                        continue

                return results

        except Exception as e:
            logger.error(f"Error during DuckDuckGo search: {e}")
            return []

    async def _search_bing(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Perform a Bing search."""
        session = await self._ensure_session()

        # Format the search URL
        escaped_query = urllib.parse.quote_plus(query)
        url = f"https://www.bing.com/search?q={escaped_query}&count={num_results + 3}"

        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Bing search request failed with status {response.status}")
                    return []

                html = await response.text()

                # Log a small sample for debugging
                logger.debug(f"Bing response sample: {html[:500]}...")

                # Parse the HTML with BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")

                results = []

                # Find all result divs
                for result in soup.select("li.b_algo"):
                    try:
                        # Extract title
                        title_element = result.select_one("h2")
                        if not title_element:
                            continue

                        title = title_element.get_text().strip()

                        # Extract URL
                        link_element = result.select_one("h2 a")
                        if not link_element:
                            continue

                        url = link_element.get("href", "")
                        if not url or not url.startswith("http"):
                            continue

                        # Extract snippet
                        snippet_element = result.select_one("p") or result.select_one(".b_caption")
                        snippet = snippet_element.get_text().strip() if snippet_element else "(No description available)"

                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet
                        })

                        if len(results) >= num_results:
                            break
                    except Exception as e:
                        logger.warning(f"Error processing Bing result: {e}")
                        continue

                return results

        except Exception as e:
            logger.error(f"Error during Bing search: {e}")
            return []

    async def set_engine(self, engine: str) -> bool:
        """
        Set the search engine to use.

        Args:
            engine: Search engine name ('google', 'bing', 'duckduckgo', 'ddg')

        Returns:
            True if successful, False otherwise
        """
        engine = engine.lower()
        if engine in ["google", "bing", "duckduckgo", "ddg"]:
            self.engine = "duckduckgo" if engine == "ddg" else engine
            logger.info(f"Search engine set to: {self.engine}")
            return True
        else:
            logger.error(f"Unknown search engine: {engine}")
            return False