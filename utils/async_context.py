#!/usr/bin/env python3

import asyncio
from typing import TypeVar, Generic, Optional, Callable, Any, Awaitable
from abc import abstractmethod
from contextlib import AbstractAsyncContextManager

from config.config_manager import logger

# Type variable for the resource managed by the context manager
T = TypeVar('T')


class AsyncResource(Generic[T], AbstractAsyncContextManager):
    """
    Base class for async resources that need proper lifecycle management.

    This class ensures that resources are properly acquired and released,
    even when exceptions occur, following the async context manager protocol.
    """

    def __init__(self, name: str = None):
        """
        Initialize the async resource.

        Args:
            name: Optional name for the resource (for logging)
        """
        self.name = name or self.__class__.__name__
        self._resource: Optional[T] = None
        self._initialized = False
        self._lock = asyncio.Lock()
        self._close_callbacks: list[Callable[[], Awaitable[None]]] = []

    @abstractmethod
    async def _initialize_resource(self) -> T:
        """
        Initialize and return the managed resource.

        Must be implemented by subclasses.

        Returns:
            The initialized resource
        """
        raise NotImplementedError("Subclasses must implement _initialize_resource")

    @abstractmethod
    async def _cleanup_resource(self, resource: T) -> None:
        """
        Clean up the managed resource.

        Must be implemented by subclasses.

        Args:
            resource: The resource to clean up
        """
        raise NotImplementedError("Subclasses must implement _cleanup_resource")

    async def __aenter__(self) -> T:
        """
        Enter the async context, ensuring the resource is initialized.

        Returns:
            The managed resource
        """
        async with self._lock:
            if not self._initialized or self._resource is None:
                try:
                    self._resource = await self._initialize_resource()
                    self._initialized = True
                    logger.debug(f"Initialized async resource: {self.name}")
                except Exception as e:
                    logger.error(f"Error initializing async resource {self.name}: {e}")
                    # Re-raise to ensure context isn't entered if initialization fails
                    raise

        return self._resource

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit the async context, cleaning up resources if needed.

        This method doesn't fully close the resource but ensures it's in a clean state.
        For full cleanup, use close().
        """
        # Resource will be fully closed only in close(), not on context exit
        # This allows reuse of the resource across multiple context blocks
        pass

    async def close(self) -> None:
        """
        Fully close and clean up the resource.

        This should be called when the resource is no longer needed.
        """
        async with self._lock:
            if self._initialized and self._resource is not None:
                try:
                    # First run any registered cleanup callbacks
                    for callback in self._close_callbacks:
                        try:
                            await callback()
                        except Exception as e:
                            logger.error(f"Error in cleanup callback for {self.name}: {e}")

                    # Then clean up the main resource
                    await self._cleanup_resource(self._resource)
                    logger.debug(f"Closed async resource: {self.name}")
                except Exception as e:
                    logger.error(f"Error closing async resource {self.name}: {e}")
                    raise
                finally:
                    self._resource = None
                    self._initialized = False

    def register_close_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """
        Register a callback to be called when the resource is closed.

        Args:
            callback: Async function to call during resource cleanup
        """
        self._close_callbacks.append(callback)

    @property
    def is_initialized(self) -> bool:
        """Check if the resource is initialized."""
        return self._initialized and self._resource is not None

    async def ensure_initialized(self) -> T:
        """
        Ensure the resource is initialized and return it.

        Returns:
            The managed resource
        """
        if not self.is_initialized:
            async with self:
                return self._resource
        return self._resource


class AsyncSessionResource(AsyncResource[Any]):
    """
    Base class for async session management with automatic reconnection.

    This class adds retry and reconnection capabilities for network-based resources.
    """

    def __init__(self, name: str = None, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the async session resource.

        Args:
            name: Optional name for the resource
            max_retries: Maximum number of connection retry attempts
            retry_delay: Delay between retries in seconds
        """
        super().__init__(name)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def execute_with_retry(self, operation: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        Execute an operation with automatic retry logic.

        Args:
            operation: Async function to execute
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation

        Returns:
            The result of the operation

        Raises:
            Exception: If all retries fail
        """
        retries = 0
        last_error = None

        while retries <= self.max_retries:
            try:
                # Ensure resource is available
                resource = await self.ensure_initialized()

                # Execute the operation
                return await operation(*args, **kwargs)

            except Exception as e:
                last_error = e
                retries += 1

                # If this is a connection-related error, try to reinitialize
                if self._is_connection_error(e):
                    logger.warning(f"{self.name} connection error, attempting to reconnect: {e}")

                    # Close and reinitialize
                    try:
                        await self.close()
                    except Exception as close_err:
                        logger.debug(f"Error while closing during reconnect: {close_err}")

                    self._initialized = False

                    # Wait before retry
                    if retries <= self.max_retries:
                        await asyncio.sleep(self.retry_delay * retries)  # Exponential backoff
                else:
                    # For non-connection errors, just re-raise
                    logger.error(f"Error in {self.name} operation: {e}")
                    raise

        # If we get here, all retries failed
        logger.error(f"All retries failed for {self.name}: {last_error}")
        raise last_error

    def _is_connection_error(self, error: Exception) -> bool:
        """
        Determine if an error is related to connection issues.

        Subclasses should override this for more specific detection.

        Args:
            error: The exception to check

        Returns:
            True if it's a connection error, False otherwise
        """
        # Basic detection - subclasses should enhance this
        error_str = str(error).lower()
        connection_terms = [
            'connection', 'timeout', 'connect', 'socket', 'network',
            'reset', 'closed', 'refused', 'unreachable'
        ]
        return any(term in error_str for term in connection_terms)