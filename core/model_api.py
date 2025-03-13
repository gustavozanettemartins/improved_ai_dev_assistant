#!/usr/bin/env python3

import json
import asyncio
import aiohttp
from typing import Callable, Awaitable, Dict, Any, Optional
from config.config_manager import config_manager, logger
from core.performance import perf_tracker
# Removed import of response_cache here to break circular dependency
from utils.http_session import HttpSessionManager


class ModelAPI:
    """Handles asynchronous interaction with the AI model API using proper resource management."""

    def __init__(self, api_url: str = config_manager.get("api_url")):
        """
        Initialize the ModelAPI.

        Args:
            api_url: Base URL for the model API
        """
        self.api_url = api_url

        # Create an HTTP session manager specifically for model API interactions
        self.session_manager = HttpSessionManager(
            base_url=api_url,
            timeout=config_manager.get("timeout_seconds", 60),
            max_retries=2,
            retry_delay=1.0,
            # Use a slower throttle rate for API calls to avoid rate limiting
            throttle_rate=0.2,
            user_agent_rotation=False,  # API typically doesn't need user agent rotation
        )

        # Set default headers for API requests
        api_key = config_manager.get("api_key")
        if api_key:
            self.session_manager.update_headers({
                "Authorization": f"Bearer {api_key}"
            })

        logger.info(f"ModelAPI initialized with URL: {self.api_url}")

    async def close(self) -> None:
        """Close the session manager safely."""
        await self.session_manager.close()
        logger.info("ModelAPI session closed")

    async def generate_response(self, model: str, prompt: str, temperature: float = None) -> str:
        """
        Generate a response from the model asynchronously with proper resource management.

        Args:
            model: Model identifier
            prompt: Input prompt
            temperature: Optional temperature parameter

        Returns:
            Generated response text
        """
        start_time = perf_tracker.start_timer("api_request")

        # Delayed import to avoid circular reference
        from utils.cache import response_cache

        # Check cache first
        try:
            cached_response = await response_cache.get(model, prompt)
            if cached_response:
                duration = perf_tracker.end_timer("api_request", start_time)
                logger.info(f"Cache hit for prompt (model: {model}, {len(prompt)} chars) in {duration:.2f}s")
                return cached_response
        except Exception as cache_error:
            logger.warning(f"Error checking cache: {cache_error}")
            # Continue without using cache

        # Get model-specific settings
        model_settings = config_manager.get("models", {}).get(model, {})
        if temperature is None:
            temperature = model_settings.get("temperature", 0.7)

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature
        }

        try:
            # Use the session manager to handle the request
            response_json = await self._safe_fetch_json(payload)

            response_text = response_json.get("response", "No response received")

            # Cache the successful response
            try:
                await response_cache.store(model, prompt, response_text)
            except Exception as cache_error:
                logger.warning(f"Error storing in cache: {cache_error}")
                # Continue without caching

            duration = perf_tracker.end_timer("api_request", start_time)
            chars_per_second = len(response_text) / max(duration, 0.1)
            logger.info(
                f"Generated {len(response_text)} chars from {model} in {duration:.2f}s ({chars_per_second:.1f} chars/sec)")

            return response_text

        except asyncio.TimeoutError:
            error_msg = f"Request to model API timed out after {self.session_manager.timeout_seconds} seconds"
            logger.error(error_msg)
            perf_tracker.end_timer("api_request", start_time)
            return error_msg

        except aiohttp.ClientResponseError as e:
            error_msg = f"Error from model API: {e.status} {e.message}"
            logger.error(error_msg)
            perf_tracker.end_timer("api_request", start_time)
            return error_msg

        except Exception as e:
            error_msg = f"Error communicating with model API: {e}"
            logger.error(error_msg)
            perf_tracker.end_timer("api_request", start_time)
            return error_msg

    async def _safe_fetch_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely fetch JSON from the API, handling various error cases.

        Args:
            payload: Request payload

        Returns:
            Response as a dictionary

        Raises:
            Various exceptions that might occur during the request
        """
        try:
            async with await self.session_manager.request(
                    method="POST",
                    url=self.api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
            ) as response:
                # Check status first
                response.raise_for_status()

                # Try to parse as JSON
                try:
                    return await response.json()
                except aiohttp.ContentTypeError:
                    # Handle non-JSON responses
                    text = await response.text()
                    logger.warning(f"API returned non-JSON response: {text[:200]}...")

                    # Try to find JSON in the response text (some APIs wrap JSON in other content)
                    json_match = None
                    try:
                        import re
                        json_pattern = r'(\{.*\}|\[.*\])'
                        matches = re.search(json_pattern, text, re.DOTALL)
                        if matches:
                            json_match = matches.group(0)
                            return json.loads(json_match)
                    except:
                        pass

                    # Return text as response if we couldn't parse JSON
                    return {"response": text}

        except Exception as e:
            logger.error(f"Error in API request: {e}")
            raise

    async def stream_response(self, model: str, prompt: str, callback: Callable[[str], Awaitable[None]],
                              temperature: float = None) -> str:
        """
        Stream a response from the model, calling the callback for each chunk.

        Args:
            model: Model identifier
            prompt: Input prompt
            callback: Async function to call with each response chunk
            temperature: Optional temperature parameter

        Returns:
            Complete generated response
        """
        start_time = perf_tracker.start_timer("api_stream")

        # Delayed import to avoid circular reference
        from utils.cache import response_cache

        # Cache check - if found, we'll simulate streaming from the cache
        try:
            cached_response = await response_cache.get(model, prompt)
            if cached_response:
                # Simulate streaming from cache by chunking the response
                full_response = cached_response
                chunk_size = max(len(full_response) // 10, 1)  # Divide into ~10 chunks

                for i in range(0, len(full_response), chunk_size):
                    chunk = full_response[i:i + chunk_size]
                    await callback(chunk)
                    await asyncio.sleep(0.1)  # Brief pause between chunks

                duration = perf_tracker.end_timer("api_stream", start_time)
                logger.info(f"Streamed {len(full_response)} chars from cache in {duration:.2f}s")
                return full_response
        except Exception as cache_error:
            logger.warning(f"Error checking cache for streaming: {cache_error}")
            # Continue without using cache

        # Get model-specific settings
        model_settings = config_manager.get("models", {}).get(model, {})
        if temperature is None:
            temperature = model_settings.get("temperature", 0.7)

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "temperature": temperature
        }

        try:
            full_response = ""

            # Start the streaming request using the session manager
            async with await self.session_manager.request(
                    method="POST",
                    url=self.api_url,
                    json=payload,
                    timeout=model_settings.get("timeout", config_manager.get("timeout_seconds", 60))
            ) as response:
                response.raise_for_status()

                # Process the streaming response
                async for line in response.content:
                    try:
                        line_text = line.decode('utf-8', errors='replace').strip()
                    except Exception as e:
                        logger.warning(f"Error decoding stream content: {e}")
                        continue

                    if not line_text or not line_text.startswith('{'):
                        continue

                    try:
                        data = json.loads(line_text)
                        if "response" in data:
                            chunk = data["response"]
                            full_response += chunk
                            await callback(chunk)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse streaming response: {line_text}")

            # Cache the complete response
            try:
                await response_cache.store(model, prompt, full_response)
            except Exception as cache_error:
                logger.warning(f"Error storing streaming response in cache: {cache_error}")

            duration = perf_tracker.end_timer("api_stream", start_time)
            chars_per_second = len(full_response) / max(duration, 0.1)
            logger.info(
                f"Streamed {len(full_response)} chars from {model} in {duration:.2f}s ({chars_per_second:.1f} chars/sec)")

            return full_response

        except asyncio.TimeoutError:
            error_msg = f"Streaming request to model API timed out"
            logger.error(error_msg)
            await callback(f"\n\n{error_msg}")
            perf_tracker.end_timer("api_stream", start_time)
            return error_msg

        except aiohttp.ClientResponseError as e:
            error_msg = f"Error from model API: {e.status} {e.message}"
            logger.error(error_msg)
            await callback(f"\n\n{error_msg}")
            perf_tracker.end_timer("api_stream", start_time)
            return error_msg

        except Exception as e:
            error_msg = f"Error communicating with model API: {e}"
            logger.error(error_msg)
            await callback(f"\n\n{error_msg}")
            perf_tracker.end_timer("api_stream", start_time)
            return error_msg