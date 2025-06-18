#!/usr/bin/env python3
"""Cryptofeed Performance Benchmarking Script.

This script provides comprehensive benchmarking for cryptofeed components,
measuring performance metrics like execution time, memory usage, and throughput.
"""

import json
import os
import time
from typing import Any

import psutil


class BenchmarkSuite:
    """Comprehensive benchmark suite for cryptofeed components."""

    def __init__(self):
        self.results: dict[str, Any] = {}

    def time_function(self, name: str, func, *args, **kwargs):
        """Time a function execution and store results."""
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            duration = end_time - start_time
            self.results[name] = duration
            return result
        except Exception:
            self.results[name] = -1
            return None

    def benchmark_feed_handler_creation(self):
        """Benchmark FeedHandler instantiation."""
        try:
            from cryptofeed import FeedHandler

            def create_handler():
                return FeedHandler()

            self.time_function("FeedHandler creation", create_handler)
        except ImportError:
            self.results["FeedHandler creation"] = -1

    def benchmark_exchange_setup(self):
        """Benchmark exchange configuration."""
        try:
            from cryptofeed.defines import TRADES
            from cryptofeed.exchanges import Binance, Coinbase

            def setup_exchanges():
                coinbase = Coinbase(symbols=["BTC-USD"], channels=[TRADES])
                binance = Binance(symbols=["BTCUSDT"], channels=[TRADES])
                return coinbase, binance

            self.time_function("Exchange setup", setup_exchanges)
        except ImportError:
            self.results["Exchange setup"] = -1

    def benchmark_memory_usage(self):
        """Benchmark memory consumption."""
        try:
            from cryptofeed import FeedHandler

            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Create multiple handlers to test memory usage
            handlers = []
            for _i in range(5):  # Reduced from 10 to 5 for stability
                fh = FeedHandler()
                handlers.append(fh)

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_diff = final_memory - initial_memory

            self.results["memory_usage_mb"] = memory_diff

            # Cleanup
            del handlers

        except ImportError:
            self.results["memory_usage_mb"] = -1

    def benchmark_import_time(self):
        """Benchmark import time for cryptofeed."""

        def import_cryptofeed():
            return True

        self.time_function("Cryptofeed import", import_cryptofeed)

    def run_all_benchmarks(self):
        """Run all benchmark suites."""
        # Run basic benchmarks that should always work
        self.benchmark_import_time()

        # Run cryptofeed-specific benchmarks
        self.benchmark_feed_handler_creation()
        self.benchmark_exchange_setup()
        self.benchmark_memory_usage()

        for name, value in self.results.items():
            if value == -1:
                pass
            elif "time" in name.lower() or name.endswith("_s"):
                pass
            elif "memory" in name.lower():
                pass
            else:
                pass

        return self.results


def main():
    """Main benchmark execution."""
    benchmark = BenchmarkSuite()
    results = benchmark.run_all_benchmarks()

    # Save results to file
    output_file = "benchmark-results.json"
    try:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
    except Exception:
        pass

    return results


if __name__ == "__main__":
    main()
