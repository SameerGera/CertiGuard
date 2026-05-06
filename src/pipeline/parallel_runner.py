"""Parallel bidder processing."""

import asyncio
from typing import List, Dict, Any, Callable
from dataclasses import dataclass


@dataclass
class ParallelConfig:
    max_workers: int = 4
    timeout_seconds: int = 300


class ParallelRunner:
    def __init__(self, config: ParallelConfig = None):
        self.config = config or ParallelConfig()

    async def process_bidders(
        self,
        bidders: List[Dict],
        process_func: Callable
    ) -> List[Dict]:
        semaphore = asyncio.Semaphore(self.config.max_workers)

        async def process_with_limit(bidder):
            async with semaphore:
                return await process_func(bidder)

        tasks = [process_with_limit(b) for b in bidders]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r if not isinstance(r, Exception) else {"error": str(r)} for r in results]

    def run_sync(
        self,
        bidders: List[Dict],
        process_func: Callable
    ) -> List[Dict]:
        results = []
        for bidder in bidders:
            try:
                result = process_func(bidder)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        return results


parallel_runner = ParallelRunner()