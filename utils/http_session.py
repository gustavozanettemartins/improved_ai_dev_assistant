#!/usr/bin/env python3

import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
import random
import time
from urllib.parse import urlparse
from utils.async_context import AsyncSessionResource


class HttpSessionManager(AsyncSessionResource):
    """
    Async context manager for HTTP sessions with proper lifecycle management.

    Features:
    - Automatic session creation and cleanup
    - Connection pooling and reuse
    - Configurable timeout and retry behavior
    - User agent rotation
    - Request throttling
    - Domain-specific rate limiting
    """

    def __init__(self,
                 base_url: Optional[str] = None,
                 headers: Optional[Dict[str, str]] = None,
                 timeout: int = 30,
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 throttle_rate: float = 0.5,
                 user_agent_rotation: bool = True,
                 name: str = "HttpSession"):
        """
        Initialize the HTTP session manager.

        Args:
            base_url: Optional base URL for all requests
            headers: Optional default headers
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
            throttle_rate: Minimum seconds between requests (rate limiting)
            user_agent_rotation: Whether to rotate user agents
            name: Name for the session (for logging)
        """
        super().__init__(name=name, max_retries=max_retries, retry_delay=retry_delay)
        self.base_url = base_url
        self.default_headers = headers or {}
        self.timeout_seconds = timeout
        self.throttle_rate = throttle_rate
        self.user_agent_rotation = user_agent_rotation

        # Track last request time for throttling
        self.last_request_time = 0

        # Domain-specific throttling
        self.domain_last_request: Dict[str, float] = {}
        self.domain_throttle_rates: Dict[str, float] = {}

        # User agents for rotation
        self.user_agents: List[str] = []
        self.current_user_agent: Optional[str] = None

    def add_user_agent(self, user_agent: str) -> None:
        """
        Add a user agent to the rotation pool.

        Args:
            user_agent: User agent string
        """
        if user_agent not in self.user_agents:
            self.user_agents.append(user_agent)
            # If this is our first user agent, set it as current
            if self.current_user_agent is None:
                self.current_user_agent = user_agent

    async def _initialize_resource(self) -> aiohttp.ClientSession:
        """
        Initialize and return an aiohttp ClientSession.

        Returns:
            Configured aiohttp.ClientSession
        """
        # Prepare default headers
        headers = self.default_headers.copy()

        # Add user agent if not present and we have one available
        if 'User-Agent' not in headers and self.user_agent_rotation and self.current_user_agent:
            headers['User-Agent'] = self.current_user_agent

        # Configure timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

        # Create session with TCP connector for connection pooling
        connector = aiohttp.TCPConnector(
            limit=20,  # Maximum number of simultaneous connections
            ttl_dns_cache=300,  # DNS cache TTL in seconds
            enable_cleanup_closed=True,  # Clean up closed connections
            force_close=False  # Allow connection reuse
        )

        # Create and return the session
        session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=connector
        )

        return session

    async def _cleanup_resource(self, resource: aiohttp.ClientSession) -> None:
        """
        Clean up the aiohttp ClientSession.

        Args:
            resource: The session to close
        """
        if not resource.closed:
            await resource.close()

            # Give the event loop time to clean up connections
            await asyncio.sleep(0.1)

    def _is_connection_error(self, error: Exception) -> bool:
        """
        Determine if an error is related to HTTP connection issues.

        Args:
            error: The exception to check

        Returns:
            True if it's a connection error, False otherwise
        """
        # First check the parent class implementation
        if super()._is_connection_error(error):
            return True

        # Check for aiohttp specific errors
        if isinstance(error, (
                aiohttp.ClientConnectorError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientOSError,
                aiohttp.ClientPayloadError,
                asyncio.TimeoutError
        )):
            return True

        return False

    def _rotate_user_agent(self) -> None:
        """Rotate to a different user agent."""
        if self.user_agent_rotation and self.user_agents:
            # Avoid using the same user agent twice in a row
            available_agents = [ua for ua in self.user_agents if ua != self.current_user_agent]
            if available_agents:
                self.current_user_agent = random.choice(available_agents)
            else:
                self.current_user_agent = random.choice(self.user_agents)

            # Update the session headers if it exists
            if self.is_initialized and self._resource is not None:
                self._resource.headers.update({'User-Agent': self.current_user_agent})

    async def _throttle_request(self, url: str) -> None:
        """
        Apply request throttling based on global and domain-specific rates.

        Args:
            url: The URL being requested
        """
        current_time = time.time()

        # Apply global throttling
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.throttle_rate:
            await asyncio.sleep(self.throttle_rate - time_since_last_request)

        # Apply domain-specific throttling if configured
        domain = urlparse(url).netloc
        if domain in self.domain_throttle_rates:
            domain_rate = self.domain_throttle_rates[domain]
            domain_last_time = self.domain_last_request.get(domain, 0)
            time_since_domain_request = current_time - domain_last_time

            if time_since_domain_request < domain_rate:
                await asyncio.sleep(domain_rate - time_since_domain_request)

            # Update domain last request time
            self.domain_last_request[domain] = time.time()

        # Update global last request time
        self.last_request_time = time.time()

    def set_domain_throttle(self, domain: str, rate_limit: float) -> None:
        """
        Set a domain-specific rate limit.

        Args:
            domain: Domain name (e.g., 'api.example.com')
            rate_limit: Minimum seconds between requests to this domain
        """
        self.domain_throttle_rates[domain] = rate_limit

    def update_headers(self, headers: Dict[str, str]) -> None:
        """
        Update default headers for future requests.

        Args:
            headers: Headers to update
        """
        self.default_headers.update(headers)

        # Update current session if initialized
        if self.is_initialized and self._resource is not None:
            self._resource.headers.update(headers)

    async def get(self, url: str, headers: Optional[Dict[str, str]] = None,
                  params: Optional[Dict[str, Any]] = None, **kwargs) -> aiohttp.ClientResponse:
        """
        Perform an HTTP GET request with proper resource management.

        Args:
            url: URL to request
            headers: Optional request-specific headers
            params: Optional URL parameters
            **kwargs: Additional arguments to pass to session.get()

        Returns:
            aiohttp.ClientResponse object
        """
        return await self.request('GET', url, headers=headers, params=params, **kwargs)

    async def post(self, url: str, data: Any = None, json: Any = None,
                   headers: Optional[Dict[str, str]] = None, **kwargs) -> aiohttp.ClientResponse:
        """
        Perform an HTTP POST request with proper resource management.

        Args:
            url: URL to request
            data: Optional form data
            json: Optional JSON data
            headers: Optional request-specific headers
            **kwargs: Additional arguments to pass to session.post()

        Returns:
            aiohttp.ClientResponse object
        """
        return await self.request('POST', url, data=data, json=json, headers=headers, **kwargs)

    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        Perform an HTTP request with automatic retries and proper throttling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional arguments to pass to session.request()

        Returns:
            aiohttp.ClientResponse object
        """
        # Build the full URL if a base URL is provided
        full_url = url
        if self.base_url and not url.startswith(('http://', 'https://')):
            full_url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        # Apply throttling
        await self._throttle_request(full_url)

        # Rotate user agent if configured
        self._rotate_user_agent()

        # Create the request function to execute with retry logic
        async def make_request():
            session = await self.ensure_initialized()
            return await session.request(method, full_url, **kwargs)

        # Execute with retry logic
        return await self.execute_with_retry(make_request)

    async def fetch_text(self, method: str, url: str, **kwargs) -> str:
        """
        Perform an HTTP request and return the response text.

        Args:
            method: HTTP method
            url: URL to request
            **kwargs: Additional arguments to pass to session.request()

        Returns:
            Response text
        """
        async with await self.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.text()

    async def fetch_json(self, method: str, url: str, **kwargs) -> Any:
        """
        Perform an HTTP request and return the JSON response.

        Args:
            method: HTTP method
            url: URL to request
            **kwargs: Additional arguments to pass to session.request()

        Returns:
            Parsed JSON response
        """
        async with await self.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def fetch_bytes(self, method: str, url: str, **kwargs) -> bytes:
        """
        Perform an HTTP request and return the response bytes.

        Args:
            method: HTTP method
            url: URL to request
            **kwargs: Additional arguments to pass to session.request()

        Returns:
            Response bytes
        """
        async with await self.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.read()