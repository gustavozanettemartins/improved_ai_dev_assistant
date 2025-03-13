import aiohttp
import asyncio
import re
import urllib.parse
import random
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from config.config_manager import logger
from core.performance import perf_tracker


class WebSearchHandler:
    """Handles web search operations using different search engines with improved reliability."""

    def __init__(self, engine: str = "duckduckgo"):
        """
        Initialize the WebSearchHandler.

        Args:
            engine: Search engine to use ('google', 'bing', 'duckduckgo')
        """
        self.engine = engine.lower()
        self.session = None

        # Extended list of user agents for better diversity
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0"
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
            # Create session with proper timeout and connection limits
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
            logger.debug("Created new aiohttp ClientSession")
        return self.session

    async def close(self) -> None:
        """Close the aiohttp session safely."""
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
        Perform a web search with improved fallback mechanisms.

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
            errors = []

            for engine in engines_to_try:
                logger.info(f"Attempting search with engine: {engine}")

                # Rotate user agent for each attempt
                self.current_user_agent = random.choice(self.user_agents)

                # Close any existing session to refresh headers
                await self.close()

                # Choose search method based on engine
                try:
                    if engine == "google":
                        results = await self._search_engine(query, num_results, engine)
                    elif engine == "bing":
                        results = await self._search_engine(query, num_results, engine)
                    elif engine == "duckduckgo" or engine == "ddg":
                        results = await self._search_engine(query, num_results, "duckduckgo")

                    # If results found, break the loop
                    if results:
                        if engine != self.engine:
                            logger.info(f"Fallback to {engine} engine successful")
                        break
                    else:
                        error_msg = f"No results from {engine}"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                except Exception as e:
                    error_msg = f"Error with {engine} engine: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Finalize performance tracking
            perf_tracker.end_timer("web_search", start_time)
            perf_tracker.increment_counter("web_searches")

            # If we have results, return them
            if results:
                return results

            # If we got here, no results were found from any engine
            logger.error(f"All search engines failed: {', '.join(errors)}")
            return []

        except Exception as e:
            logger.error(f"Unexpected error during web search: {e}")
            perf_tracker.end_timer("web_search", start_time)
            return []

    async def _search_engine(self, query: str, num_results: int, engine: str) -> List[Dict[str, str]]:
        """
        Unified search method with engine-specific handling.

        Args:
            query: Search query string
            num_results: Number of results to return
            engine: Search engine to use

        Returns:
            List of search result dictionaries
        """
        session = await self._ensure_session()

        # Engine-specific parameters
        search_url, selectors = self._get_engine_params(query, engine)

        try:
            async with session.get(search_url, timeout=20) as response:
                if response.status != 200:
                    logger.error(f"{engine.capitalize()} search request failed with status {response.status}")
                    return []

                html = await response.text()

                # Check for security challenges or captchas
                if "captcha" in html.lower() or "unusual traffic" in html.lower() or "security check" in html.lower():
                    logger.warning(f"{engine.capitalize()} security challenge detected, cannot proceed with scraping")
                    return []

                # Log a small sample of HTML for debugging
                logger.debug(f"{engine.capitalize()} search response sample: {html[:500]}...")

                # Parse the HTML with BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")

                results = []

                # Try to find results using engine-specific selectors
                result_elements = None
                for selector in selectors["result_container"]:
                    result_elements = soup.select(selector)
                    if result_elements and len(result_elements) > 0:
                        logger.debug(f"Found {len(result_elements)} results with selector '{selector}'")
                        break

                # If no results found, try a broader approach or return empty
                if not result_elements or len(result_elements) == 0:
                    logger.warning(f"{engine.capitalize()} search failed to find results with selectors")
                    return []

                # Process the results using engine-specific extraction
                for result in result_elements[:num_results + 3]:  # Get a few extra in case some fail
                    try:
                        parsed_result = self._extract_result(result, engine, selectors)
                        if parsed_result:
                            results.append(parsed_result)

                            # Stop once we have enough results
                            if len(results) >= num_results:
                                break
                    except Exception as e:
                        logger.debug(f"Error processing search result: {e}")
                        continue

                return results

        except asyncio.TimeoutError:
            logger.error(f"{engine.capitalize()} search timed out")
            return []
        except Exception as e:
            logger.error(f"Error during {engine} search: {e}")
            return []

    def _get_engine_params(self, query: str, engine: str) -> Tuple[str, Dict[str, List[str]]]:
        """
        Get engine-specific parameters for search.

        Args:
            query: Search query
            engine: Search engine name

        Returns:
            Tuple of (search_url, selector_dict)
        """
        escaped_query = urllib.parse.quote_plus(query)

        if engine == "google":
            url = f"https://www.google.com/search?q={escaped_query}&num=15&hl=en&gl=US"
            selectors = {
                "result_container": ["div.g", "div.tF2Cxc", "div.yuRUbf", "div[data-sokoban-container]", "div.EIaa9b"],
                "title": ["h3", ".LC20lb"],
                "url": ["a"],
                "snippet": ["div.VwiC3b", "span.aCOpRe", ".s3v9rd", ".lEBKkf"]
            }
            return url, selectors

        elif engine == "bing":
            url = f"https://www.bing.com/search?q={escaped_query}&count=20"
            selectors = {
                "result_container": ["li.b_algo", ".b_snippetLarge", ".b_algo", "li.b_algoBigWig"],
                "title": ["h2", ".b_title"],
                "url": ["h2 a", "a.tilk"],
                "snippet": ["p", ".b_caption", ".b_snippet", ".b_snippetBigWig"]
            }
            return url, selectors

        elif engine == "duckduckgo":
            url = f"https://html.duckduckgo.com/html/?q={escaped_query}"
            selectors = {
                "result_container": [".result", ".web-result"],
                "title": [".result__title", ".result__a"],
                "url": [".result__title a", ".result__url", ".result__a"],
                "snippet": [".result__snippet"]
            }
            return url, selectors

        else:
            # Default to DuckDuckGo if engine not recognized
            logger.warning(f"Unknown engine: {engine}, falling back to DuckDuckGo")
            url = f"https://html.duckduckgo.com/html/?q={escaped_query}"
            selectors = {
                "result_container": [".result", ".web-result"],
                "title": [".result__title", ".result__a"],
                "url": [".result__title a", ".result__url", ".result__a"],
                "snippet": [".result__snippet"]
            }
            return url, selectors

    def _extract_result(self, result_element: Any, engine: str, selectors: Dict[str, List[str]]) -> Optional[
        Dict[str, str]]:
        """
        Extract search result information from a result element.

        Args:
            result_element: BeautifulSoup element containing a search result
            engine: Search engine name
            selectors: Dictionary of selectors for this engine

        Returns:
            Dictionary with title, url, and snippet or None if extraction failed
        """
        # Extract title
        title_element = None
        for selector in selectors["title"]:
            title_element = result_element.select_one(selector)
            if title_element:
                break

        if not title_element:
            return None

        title = title_element.get_text().strip()
        if not title:
            return None

        # Extract URL
        url = ""
        for selector in selectors["url"]:
            link_element = result_element.select_one(selector)
            if link_element:
                url = link_element.get("href", "")
                break

        if not url:
            return None

        # Clean up URL based on engine-specific patterns
        if engine == "google" and url.startswith("/url?"):
            url_match = re.search(r"url\?q=([^&]+)", url)
            if url_match:
                url = urllib.parse.unquote(url_match.group(1))

        elif engine == "duckduckgo" and not url.startswith("http"):
            # Extract from DuckDuckGo redirect if needed
            url_match = re.search(r"uddg=([^&]+)", url)
            if url_match:
                url = urllib.parse.unquote(url_match.group(1))
            else:
                # Fallback to displayed URL
                url_display = result_element.select_one(".result__url")
                if url_display:
                    url_text = url_display.get_text().strip()
                    if url_text:
                        url = f"https://{url_text}"

        # Ensure URL starts with http
        if not url.startswith(("http://", "https://")):
            return None

        # Extract snippet
        snippet = ""
        for selector in selectors["snippet"]:
            snippet_element = result_element.select_one(selector)
            if snippet_element:
                snippet = snippet_element.get_text().strip()
                break

        if not snippet:
            snippet = "(No description available)"

        return {
            "title": title,
            "url": url,
            "snippet": snippet
        }

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