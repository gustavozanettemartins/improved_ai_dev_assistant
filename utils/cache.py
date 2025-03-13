#!/usr/bin/env python3

import json
import time
import hashlib
import asyncio
import aiofiles
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import sys
from config.config_manager import config_manager, logger
from core.performance import perf_tracker


class CacheItem:
    """Represents a single item in the cache with memory usage tracking."""

    def __init__(self, key: str, model: str, response: str, metadata: Dict[str, Any] = None):
        self.key = key
        self.model = model
        self.response = response
        self.created_at = time.time()
        self.last_access = time.time()
        self.metadata = metadata or {}
        self.hits = 0

        # Calculate memory usage
        self.size_estimate = (
                sys.getsizeof(key) +
                sys.getsizeof(model) +
                sys.getsizeof(response) +
                sys.getsizeof(self.metadata)
        )

    def update_access(self) -> None:
        """Update last access time and hit count."""
        self.last_access = time.time()
        self.hits += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "model": self.model,
            "response": self.response,
            "created_at": self.created_at,
            "last_access": self.last_access,
            "hits": self.hits,
            "size_bytes": self.size_estimate,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheItem':
        """Create a CacheItem from a dictionary."""
        item = cls(
            key=data["key"],
            model=data["model"],
            response=data["response"],
            metadata=data.get("metadata", {})
        )
        item.created_at = data.get("created_at", time.time())
        item.last_access = data.get("last_access", time.time())
        item.hits = data.get("hits", 0)
        item.size_estimate = data.get("size_bytes", sys.getsizeof(item.response))
        return item


class ResponseCache:
    """
    Caches API responses with optimized memory management and efficient cleanup.

    Features:
    - Memory-aware caching with size estimation
    - LRU (Least Recently Used) and LFU (Least Frequently Used) eviction policies
    - Background cleanup to prevent memory bloat
    - Async disk I/O for better performance
    - In-memory cache for frequently accessed items
    """

    def __init__(self,
                 cache_dir: str = config_manager.get("cache_dir"),
                 max_size_mb: int = config_manager.get("max_cache_size_mb"),
                 cleanup_interval: int = 3600,
                 max_memory_items: int = 100,
                 eviction_policy: str = "lru"):
        """
        Initialize the cache with optimized parameters.

        Args:
            cache_dir: Directory to store cache files
            max_size_mb: Maximum disk cache size in MB
            cleanup_interval: Time between cleanup operations in seconds
            max_memory_items: Maximum number of items to keep in memory
            eviction_policy: Cache eviction policy ('lru' or 'lfu')
        """
        self.cache_dir = Path(cache_dir)
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cleanup_interval = cleanup_interval
        self.max_memory_items = max_memory_items
        self.eviction_policy = eviction_policy.lower()

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(exist_ok=True, parents=True)

        # Cache index file path
        self.cache_index_file = self.cache_dir / "cache_index.json"

        # In-memory cache (key -> CacheItem)
        self.memory_cache: Dict[str, CacheItem] = {}

        # Disk cache index (key -> metadata)
        self.cache_index: Dict[str, Dict[str, Any]] = {}

        # Load cache index from disk
        self._load_cache_index()

        # Track total cache size
        self.current_size_bytes = 0
        self._calculate_current_size()

        # Last cleanup time
        self.last_cleanup = time.time()

        # Lock for thread safety
        self.lock = asyncio.Lock()

        logger.info(f"Response cache initialized with max size {max_size_mb}MB, "
                    f"using {eviction_policy} eviction policy")

    def _load_cache_index(self) -> None:
        """Load the cache index from file with error handling."""
        try:
            if self.cache_index_file.exists():
                with open(self.cache_index_file, 'r', encoding='utf-8') as f:
                    loaded_index = json.load(f)

                    # Validate the structure
                    if isinstance(loaded_index, dict):
                        self.cache_index = loaded_index
                        logger.info(f"Loaded cache index with {len(self.cache_index)} entries")
                    else:
                        logger.warning(f"Invalid cache index format, resetting")
                        self.cache_index = {}
            else:
                self.cache_index = {}
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
            self.cache_index = {}

    async def _save_cache_index(self) -> None:
        """Save the cache index to file asynchronously with proper error handling."""
        try:
            # Create a temporary file for atomic write
            temp_file = self.cache_index_file.with_suffix('.tmp')

            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.cache_index, ensure_ascii=False))

            # Atomic rename for safer file operations
            temp_file.replace(self.cache_index_file)

            logger.debug("Cache index saved successfully")
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")

    def _calculate_current_size(self) -> None:
        """Calculate the current total size of the cache."""
        self.current_size_bytes = 0
        for key, metadata in self.cache_index.items():
            self.current_size_bytes += metadata.get("size_bytes", 0)

    def _get_cache_key(self, model: str, prompt: str) -> str:
        """Generate a unique cache key for a model-prompt pair."""
        hash_obj = hashlib.blake2b((model + prompt).encode('utf-8'), digest_size=16)
        return hash_obj.hexdigest()

    async def _check_and_cleanup(self, force: bool = False) -> None:
        """
        Check cache size and clean up if necessary, using the configured eviction policy.

        Args:
            force: Force cleanup regardless of time interval
        """
        async with self.lock:
            now = time.time()
            if not force and now - self.last_cleanup < self.cleanup_interval:
                return

            self.last_cleanup = now

            # First, clean up memory cache if needed
            self._cleanup_memory_cache()

            # Then check and clean up disk cache
            self._calculate_current_size()
            target_size = int(self.max_size_bytes * 0.9)  # Target 90% of max size

            if self.current_size_bytes <= target_size and not force:
                return

            # Need to clean up disk cache
            logger.info(f"Running cache cleanup, current size: {self.current_size_bytes / (1024 * 1024):.2f}MB, "
                        f"target: {target_size / (1024 * 1024):.2f}MB")

            # Get list of cache entries with their metadata
            cache_items = []
            for key, metadata in self.cache_index.items():
                cache_items.append((
                    key,
                    metadata.get("last_access", 0),
                    metadata.get("hits", 0),
                    metadata.get("size_bytes", 0)
                ))

            # Sort by eviction policy
            if self.eviction_policy == "lru":
                # Least Recently Used - sort by last access time (oldest first)
                cache_items.sort(key=lambda x: x[1])
            elif self.eviction_policy == "lfu":
                # Least Frequently Used - sort by hit count (least hits first)
                cache_items.sort(key=lambda x: x[2])
            else:
                # Default to LRU+Size for best memory efficiency
                # This ranks items by (access_time * size) to prioritize removing large, old items
                cache_items.sort(key=lambda x: x[1] * x[3])

            # Remove items until we're under the target size
            bytes_to_remove = self.current_size_bytes - target_size
            bytes_removed = 0
            items_removed = 0

            for key, _, _, size in cache_items:
                if bytes_removed >= bytes_to_remove and not force:
                    break

                # Remove from disk
                cache_file = self.cache_dir / f"{key}.json"
                try:
                    if cache_file.exists():
                        cache_file.unlink()

                    # Remove from memory cache if present
                    self.memory_cache.pop(key, None)

                    # Remove from index
                    del self.cache_index[key]

                    bytes_removed += size
                    items_removed += 1

                except Exception as e:
                    logger.error(f"Error removing cache file {key}: {e}")

            # Update current size
            self.current_size_bytes -= bytes_removed

            # Save updated index
            await self._save_cache_index()

            logger.info(f"Cache cleanup complete: removed {items_removed} items, "
                        f"{bytes_removed / (1024 * 1024):.2f}MB, "
                        f"new size: {self.current_size_bytes / (1024 * 1024):.2f}MB")

    def _cleanup_memory_cache(self) -> None:
        """Clean up memory cache if it exceeds the maximum number of items."""
        if len(self.memory_cache) <= self.max_memory_items:
            return

        # Sort by last access time (oldest first)
        items_to_remove = len(self.memory_cache) - self.max_memory_items

        if self.eviction_policy == "lru":
            # Sort by last access time
            sorted_items = sorted(self.memory_cache.items(), key=lambda x: x[1].last_access)
        else:
            # Sort by hit count
            sorted_items = sorted(self.memory_cache.items(), key=lambda x: x[1].hits)

        # Remove oldest/least used items
        for i in range(items_to_remove):
            key, _ = sorted_items[i]
            self.memory_cache.pop(key, None)

        logger.debug(f"Memory cache cleanup: removed {items_to_remove} items, "
                     f"current size: {len(self.memory_cache)}")

    async def get(self, model: str, prompt: str) -> Optional[str]:
        """
        Get a cached response if available, with optimized memory usage.

        Args:
            model: Model identifier
            prompt: The prompt to look up

        Returns:
            Cached response or None if not found
        """
        start_time = perf_tracker.start_timer("cache_lookup")
        key = self._get_cache_key(model, prompt)

        # Check memory cache first for fastest retrieval
        cache_hit = self.memory_cache.get(key)
        if cache_hit:
            cache_hit.update_access()
            perf_tracker.end_timer("cache_lookup", start_time)
            perf_tracker.increment_counter("cache_hits")
            logger.debug(f"Memory cache hit for key: {key[:8]}...")
            return cache_hit.response

        # Check disk cache
        if key in self.cache_index:
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                try:
                    async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)

                    # Update last access time and hit count
                    async with self.lock:
                        self.cache_index[key]["last_access"] = time.time()
                        self.cache_index[key]["hits"] = self.cache_index[key].get("hits", 0) + 1

                    # Store in memory cache for faster future access
                    cache_item = CacheItem(
                        key=key,
                        model=data.get("model", model),
                        response=data.get("response", ""),
                        metadata=data.get("metadata", {})
                    )
                    cache_item.hits = self.cache_index[key].get("hits", 1)
                    self.memory_cache[key] = cache_item

                    # Clean up memory cache if needed
                    self._cleanup_memory_cache()

                    # Schedule index save (don't wait)
                    asyncio.create_task(self._save_cache_index())

                    perf_tracker.end_timer("cache_lookup", start_time)
                    perf_tracker.increment_counter("cache_hits")
                    logger.debug(f"Disk cache hit for key: {key[:8]}...")
                    return data.get("response")

                except Exception as e:
                    logger.error(f"Error reading cache file: {e}")

                    # Remove corrupted entry
                    try:
                        cache_file.unlink(missing_ok=True)
                        async with self.lock:
                            self.cache_index.pop(key, None)
                            await self._save_cache_index()
                    except Exception:
                        pass

        perf_tracker.end_timer("cache_lookup", start_time)
        perf_tracker.increment_counter("cache_misses")
        return None

    async def store(self, model: str, prompt: str, response: str, metadata: Dict[str, Any] = None) -> None:
        """
        Store a response in the cache with optimized serialization.

        Args:
            model: Model identifier
            prompt: The prompt that was used
            response: The response to cache
            metadata: Optional metadata to store with the response
        """
        if not response or not prompt:
            return

        start_time = perf_tracker.start_timer("cache_store")

        key = self._get_cache_key(model, prompt)
        metadata = metadata or {}

        # Create cache item
        cache_item = CacheItem(
            key=key,
            model=model,
            response=response,
            metadata={
                "prompt_hash": hashlib.md5(prompt.encode('utf-8')).hexdigest(),
                "timestamp": time.time(),
                **metadata
            }
        )

        # Store in memory
        self.memory_cache[key] = cache_item

        # Store on disk
        cache_file = self.cache_dir / f"{key}.json"

        try:
            # Prepare data for serialization
            data = {
                "key": key,
                "model": model,
                "response": response,
                "prompt_hash": cache_item.metadata["prompt_hash"],
                "timestamp": cache_item.created_at,
                "metadata": cache_item.metadata
            }

            # Write to disk asynchronously
            async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False))

            # Update index
            async with self.lock:
                self.cache_index[key] = {
                    "key": key,
                    "model": model,
                    "created": cache_item.created_at,
                    "last_access": cache_item.last_access,
                    "size_bytes": cache_item.size_estimate,
                    "hits": 1
                }

                # Update total cache size
                self.current_size_bytes += cache_item.size_estimate

                # Save index
                await self._save_cache_index()

            # Check if cleanup is needed
            if self.current_size_bytes > self.max_size_bytes:
                asyncio.create_task(self._check_and_cleanup())

            perf_tracker.end_timer("cache_store", start_time)
            perf_tracker.increment_counter("cache_stores")
            logger.debug(f"Cached response for key: {key[:8]}...")

        except Exception as e:
            logger.error(f"Error storing cache: {e}")
            perf_tracker.end_timer("cache_store", start_time)

    async def clear(self, older_than_days: Optional[int] = None) -> Tuple[int, int]:
        """
        Clear all or part of the cache.

        Args:
            older_than_days: If specified, only clear items older than this many days

        Returns:
            Tuple of (items_removed, bytes_freed)
        """
        items_removed = 0
        bytes_freed = 0

        async with self.lock:
            # Determine which items to remove
            keys_to_remove = []

            if older_than_days is not None:
                cutoff_time = time.time() - (older_than_days * 86400)

                for key, metadata in self.cache_index.items():
                    if metadata.get("created", 0) < cutoff_time:
                        keys_to_remove.append(key)
                        bytes_freed += metadata.get("size_bytes", 0)
            else:
                # Clear everything
                bytes_freed = self.current_size_bytes
                keys_to_remove = list(self.cache_index.keys())

            # Remove items
            for key in keys_to_remove:
                cache_file = self.cache_dir / f"{key}.json"
                try:
                    if cache_file.exists():
                        cache_file.unlink()

                    # Remove from memory cache
                    self.memory_cache.pop(key, None)

                    # Remove from index
                    self.cache_index.pop(key, None)

                    items_removed += 1
                except Exception as e:
                    logger.error(f"Error removing cache file during clear: {e}")

            # Reset or update cache size
            if older_than_days is None:
                self.current_size_bytes = 0
                self.cache_index = {}
                self.memory_cache = {}
            else:
                self.current_size_bytes -= bytes_freed

            # Save updated index
            await self._save_cache_index()

            logger.info(f"Cache clear: removed {items_removed} items, freed {bytes_freed / (1024 * 1024):.2f}MB")
            return items_removed, bytes_freed

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        disk_size = sum(metadata.get("size_bytes", 0) for metadata in self.cache_index.values())
        memory_size = sum(item.size_estimate for item in self.memory_cache.values())

        stats = {
            "disk_items": len(self.cache_index),
            "memory_items": len(self.memory_cache),
            "disk_size_bytes": disk_size,
            "disk_size_mb": disk_size / (1024 * 1024),
            "memory_size_bytes": memory_size,
            "memory_size_mb": memory_size / (1024 * 1024),
            "max_size_mb": self.max_size_mb,
            "eviction_policy": self.eviction_policy,
            "cleanup_interval_seconds": self.cleanup_interval,
            "last_cleanup": self.last_cleanup
        }

        # Get hit/miss statistics from perf_tracker
        metrics = perf_tracker.get_metrics()
        stats.update({
            "hits": metrics.get("counters", {}).get("cache_hits", 0),
            "misses": metrics.get("counters", {}).get("cache_misses", 0),
            "stores": metrics.get("counters", {}).get("cache_stores", 0)
        })

        # Calculate hit rate
        total_lookups = stats["hits"] + stats["misses"]
        stats["hit_rate"] = stats["hits"] / total_lookups if total_lookups > 0 else 0

        return stats

    async def close(self) -> None:
        """Safely close the cache, ensuring all data is saved."""
        logger.info("Closing response cache")
        try:
            # Save index one last time
            await self._save_cache_index()
        except Exception as e:
            logger.error(f"Error closing cache: {e}")


# Initialize the global response cache instance
response_cache = ResponseCache()