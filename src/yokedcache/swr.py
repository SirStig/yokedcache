"""
Stale-While-Revalidate (SWR) background refresh scheduling.

Provides intelligent background refresh of cached data before expiration,
ensuring fresh data is always available while serving stale data during refresh.
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from typing import Any, Callable, Dict, Optional, Set, Union

logger = logging.getLogger(__name__)


class SWRScheduler:
    """Manages background refresh scheduling for SWR pattern."""

    def __init__(self, cache_instance):
        """Initialize with a reference to the cache instance."""
        self._cache_ref = weakref.ref(cache_instance)
        self._refresh_tasks: Dict[str, asyncio.Task] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}
        self._shutdown = False
        self._cleanup_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start the SWR scheduler."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.debug("SWR scheduler started")

    async def stop(self) -> None:
        """Stop the SWR scheduler and cancel all refresh tasks."""
        self._shutdown = True

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Cancel all refresh tasks
        for task in list(self._refresh_tasks.values()):
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete
        if self._refresh_tasks:
            await asyncio.gather(*self._refresh_tasks.values(), return_exceptions=True)

        self._refresh_tasks.clear()
        self._refresh_locks.clear()
        logger.debug("SWR scheduler stopped")

    def schedule_refresh(
        self,
        key: str,
        loader: Callable[[], Any],
        ttl: Optional[int] = None,
        tags: Optional[Union[str, list, Set[str]]] = None,
        refresh_threshold: float = 0.1,  # Refresh when 10% of TTL remains
    ) -> None:
        """Schedule a background refresh for a key."""
        cache = self._cache_ref()
        if not cache or self._shutdown:
            return

        # Cancel any existing refresh task for this key
        self._cancel_refresh(key)

        # Calculate delay until refresh should occur
        actual_ttl = ttl if ttl is not None else cache.config.default_ttl
        refresh_delay = actual_ttl * (1 - refresh_threshold)

        # Create refresh task
        task = asyncio.create_task(
            self._refresh_after_delay(key, loader, refresh_delay, actual_ttl, tags)
        )
        self._refresh_tasks[key] = task

        logger.debug(f"Scheduled SWR refresh for {key} in {refresh_delay}s")

    def cancel_refresh(self, key: str) -> bool:
        """Cancel a scheduled refresh for a key."""
        return self._cancel_refresh(key)

    def _cancel_refresh(self, key: str) -> bool:
        """Internal method to cancel refresh."""
        if key in self._refresh_tasks:
            task = self._refresh_tasks.pop(key)
            if not task.done():
                task.cancel()
            if key in self._refresh_locks:
                del self._refresh_locks[key]
            logger.debug(f"Cancelled SWR refresh for {key}")
            return True
        return False

    async def _refresh_after_delay(
        self,
        key: str,
        loader: Callable[[], Any],
        delay: float,
        ttl: int,
        tags: Optional[Union[str, list, Set[str]]] = None,
    ) -> None:
        """Refresh a key after the specified delay."""
        try:
            # Wait for the delay
            await asyncio.sleep(delay)

            if self._shutdown:
                return

            cache = self._cache_ref()
            if not cache:
                return

            # Get or create lock for this key
            if key not in self._refresh_locks:
                self._refresh_locks[key] = asyncio.Lock()

            async with self._refresh_locks[key]:
                # Check if key still exists and hasn't been refreshed
                if await cache.exists(key):
                    try:
                        # Execute the loader
                        if asyncio.iscoroutinefunction(loader):
                            new_value = await loader()
                        else:
                            new_value = loader()

                        # Update the cache with fresh value
                        success = await cache.set(key, new_value, ttl=ttl, tags=tags)

                        if success:
                            logger.debug(f"SWR refresh completed for {key}")

                            # Schedule next refresh if SWR is still enabled
                            if cache.config.enable_stale_while_revalidate:
                                refresh_threshold = getattr(
                                    cache.config, "swr_refresh_threshold", 0.1
                                )
                                self.schedule_refresh(
                                    key, loader, ttl, tags, refresh_threshold
                                )
                        else:
                            logger.warning(
                                f"SWR refresh failed to update cache for {key}"
                            )

                    except Exception as e:
                        logger.error(f"Error in SWR refresh for {key}: {e}")

                        # Retry with exponential backoff
                        retry_delay = min(60, delay * 2)  # Max 60 seconds
                        asyncio.create_task(
                            self._refresh_after_delay(
                                key, loader, retry_delay, ttl, tags
                            )
                        )

        except asyncio.CancelledError:
            logger.debug(f"SWR refresh cancelled for {key}")

        except Exception as e:
            logger.error(f"Unexpected error in SWR refresh for {key}: {e}")

        finally:
            # Clean up
            self._refresh_tasks.pop(key, None)
            if key in self._refresh_locks:
                del self._refresh_locks[key]

    async def _cleanup_loop(self) -> None:
        """Periodically clean up completed tasks."""
        while not self._shutdown:
            try:
                await asyncio.sleep(60)  # Cleanup every minute

                # Remove completed tasks
                completed_keys = [
                    key for key, task in self._refresh_tasks.items() if task.done()
                ]

                for key in completed_keys:
                    self._refresh_tasks.pop(key, None)
                    self._refresh_locks.pop(key, None)

                if completed_keys:
                    logger.debug(
                        f"Cleaned up {len(completed_keys)} completed SWR tasks"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SWR cleanup loop: {e}")

    def get_active_refreshes(self) -> Set[str]:
        """Get the set of keys with active refresh tasks."""
        return {key for key, task in self._refresh_tasks.items() if not task.done()}

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the SWR scheduler."""
        active_tasks = sum(
            1 for task in self._refresh_tasks.values() if not task.done()
        )
        completed_tasks = sum(1 for task in self._refresh_tasks.values() if task.done())

        return {
            "active_refreshes": active_tasks,
            "completed_refreshes": completed_tasks,
            "total_scheduled": len(self._refresh_tasks),
            "is_running": not self._shutdown and self._cleanup_task is not None,
        }
