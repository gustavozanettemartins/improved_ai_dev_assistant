#!/usr/bin/env python3

import os
import json
import time
import hashlib
import aiofiles
from typing import Dict, Any, Optional

from config.config_manager import config_manager, logger
from core.performance import perf_tracker


class ResponseCache:
    """Caches API responses to improve performance and reduce API calls."""

    def __init__(self, cache_dir: str = config_manager.get("cache_dir"),
                 max_size_mb: int = config_manager.get("max_cache_size_mb")):
        self.cache_dir = cache_dir
        self.max_size_mb = max_size_mb
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_index_file = os.path.join(self.cache_dir, "cache_index.json")
        self.cache_index = self._load_cache_index()
        self.last_cleanup = time.time()
        self.cleanup_interval = 3600  # 1 hour
        logger.info(f"Response cache initialized with max size {max_size_mb}MB")

    def _load_cache_index(self) -> Dict[str, Dict[str, Any]]:
        """Load the cache index from file."""
        try:
            if os.path.exists(self.cache_index_file):
                with open(self.cache_index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
        return {}

    def _save_cache_index(self) -> None:
        """Save the cache index to file."""
        try:
            with open(self.cache_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_index, f)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")

    def _get_cache_key(self, model: str, prompt: str) -> str:
        """Generate a unique cache key for a model-prompt pair."""
        hash_obj = hashlib.md5((model + prompt).encode('utf-8'))
        return hash_obj.hexdigest()

    def _check_and_cleanup(self) -> None:
        """Check cache size and clean up if necessary."""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return

        self.last_cleanup = now
        total_size_bytes = 0
        cache_items = []

        # Calculate current cache size
        for key, metadata in self.cache_index.items():
            cache_file = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.exists(cache_file):
                file_size = os.path.getsize(cache_file)
                total_size_bytes += file_size
                cache_items.append((key, metadata["last_access"], file_size))

        total_size_mb = total_size_bytes / (1024 * 1024)
        if total_size_mb <= self.max_size_mb:
            return

        # Sort by last access time (oldest first)
        cache_items.sort(key=lambda x: x[1])

        # Delete oldest items until we're under the size limit
        bytes_to_remove = total_size_bytes - (self.max_size_mb * 1024 * 1024 * 0.9)  # Target 90% of max
        bytes_removed = 0

        for key, _, file_size in cache_items:
            if bytes_removed >= bytes_to_remove:
                break

            cache_file = os.path.join(self.cache_dir, f"{key}.json")
            try:
                os.remove(cache_file)
                del self.cache_index[key]
                bytes_removed += file_size
                logger.debug(f"Removed cache item: {key}, size: {file_size / 1024:.2f}KB")
            except Exception as e:
                logger.error(f"Error removing cache file: {e}")

        self._save_cache_index()
        logger.info(
            f"Cache cleanup: removed {bytes_removed / 1024 / 1024:.2f}MB, new size: {(total_size_bytes - bytes_removed) / 1024 / 1024:.2f}MB")

    async def get(self, model: str, prompt: str) -> Optional[str]:
        """Get a cached response if available."""
        start_time = perf_tracker.start_timer("cache_lookup")
        key = self._get_cache_key(model, prompt)

        if key in self.cache_index:
            cache_file = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.exists(cache_file):
                try:
                    async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)

                    # Update last access time
                    self.cache_index[key]["last_access"] = time.time()
                    self._save_cache_index()

                    perf_tracker.end_timer("cache_lookup", start_time)
                    perf_tracker.increment_counter("cache_hits")
                    logger.debug(f"Cache hit for key: {key[:8]}...")
                    return data["response"]
                except Exception as e:
                    logger.error(f"Error reading cache file: {e}")

        perf_tracker.end_timer("cache_lookup", start_time)
        perf_tracker.increment_counter("cache_misses")
        return None

    async def store(self, model: str, prompt: str, response: str) -> None:
        """Store a response in the cache."""
        start_time = perf_tracker.start_timer("cache_store")
        key = self._get_cache_key(model, prompt)
        cache_file = os.path.join(self.cache_dir, f"{key}.json")

        try:
            data = {
                "model": model,
                "prompt_hash": hashlib.md5(prompt.encode('utf-8')).hexdigest(),
                "response": response,
                "timestamp": time.time()
            }

            async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False))

            self.cache_index[key] = {
                "model": model,
                "created": time.time(),
                "last_access": time.time(),
                "size_bytes": len(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            }

            self._save_cache_index()
            self._check_and_cleanup()
            perf_tracker.end_timer("cache_store", start_time)
            perf_tracker.increment_counter("cache_stores")
            logger.debug(f"Cached response for key: {key[:8]}...")
        except Exception as e:
            logger.error(f"Error storing cache: {e}")
            perf_tracker.end_timer("cache_store", start_time)


# Initialize the global response cache instance
response_cache = ResponseCache()