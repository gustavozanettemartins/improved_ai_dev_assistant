#!/usr/bin/env python3

import asyncio
import inspect
from typing import Dict, Any, List, Callable, Awaitable, Optional, Tuple
from config.config_manager import logger


class ResourceRegistry:
    """
    Registry for tracking and managing async resources lifecycle.

    This class provides a central mechanism for registering, tracking, and
    properly closing async resources, ensuring proper cleanup during shutdown.
    """

    def __init__(self):
        """Initialize the resource registry."""
        self._resources: Dict[str, Tuple[Any, Optional[Callable]]] = {}
        self._lock = asyncio.Lock()
        logger.info("ResourceRegistry initialized")

    async def register(self, name: str, resource: Any,
                       close_method: Optional[Callable] = None) -> None:
        """
        Register a resource for lifecycle management.

        Args:
            name: Unique identifier for the resource
            resource: The resource object to manage
            close_method: Optional custom close method, defaults to resource.close
        """
        async with self._lock:
            # If no custom close method, use resource.close if it exists
            if close_method is None and hasattr(resource, 'close'):
                close_method = resource.close

            self._resources[name] = (resource, close_method)
            logger.debug(f"Registered resource: {name}")

    async def unregister(self, name: str) -> bool:
        """
        Unregister a resource without closing it.

        Args:
            name: Identifier of the resource to unregister

        Returns:
            True if resource was found and unregistered, False otherwise
        """
        async with self._lock:
            if name in self._resources:
                del self._resources[name]
                logger.debug(f"Unregistered resource: {name}")
                return True
            return False

    async def close_resource(self, name: str) -> Tuple[bool, Optional[Exception]]:
        """
        Close a specific resource.

        Args:
            name: Identifier of the resource to close

        Returns:
            Tuple of (success, error)
        """
        async with self._lock:
            if name not in self._resources:
                return False, None

            resource, close_method = self._resources[name]

            if close_method is None:
                logger.warning(f"No close method for resource: {name}")
                del self._resources[name]
                return True, None

            try:
                if asyncio.iscoroutinefunction(close_method):
                    await close_method()
                else:
                    close_method()

                del self._resources[name]
                logger.debug(f"Closed resource: {name}")
                return True, None
            except Exception as e:
                logger.error(f"Error closing resource {name}: {e}")
                # Still remove it from registry
                del self._resources[name]
                return False, e

    async def close_all(self) -> Tuple[int, int, List[Tuple[str, Exception]]]:
        """
        Close all registered resources.

        Returns:
            Tuple of (total_count, success_count, errors)
            where errors is list of (resource_name, exception) tuples
        """
        async with self._lock:
            if not self._resources:
                return 0, 0, []

            total_count = len(self._resources)
            success_count = 0
            errors = []

            # Make a copy of the keys since we'll be modifying during iteration
            resource_names = list(self._resources.keys())

            for name in resource_names:
                success, error = await self.close_resource(name)
                if success:
                    success_count += 1
                else:
                    errors.append((name, error))

            logger.info(f"Closed {success_count}/{total_count} resources")
            if errors:
                logger.warning(f"Encountered {len(errors)} errors during resource cleanup")

            return total_count, success_count, errors

    def get_resource(self, name: str) -> Optional[Any]:
        """
        Get a registered resource by name.

        Args:
            name: Resource identifier

        Returns:
            The resource object or None if not found
        """
        resource_tuple = self._resources.get(name)
        return resource_tuple[0] if resource_tuple else None

    def get_resource_names(self) -> List[str]:
        """
        Get list of registered resource names.

        Returns:
            List of resource names
        """
        return list(self._resources.keys())

    def count(self) -> int:
        """
        Get count of registered resources.

        Returns:
            Number of registered resources
        """
        return len(self._resources)


# Create global resource registry instance
resource_registry = ResourceRegistry()