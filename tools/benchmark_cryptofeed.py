#!/usr/bin/env python3
"""
Cryptofeed Performance Benchmarking Script

This script provides comprehensive benchmarking for cryptofeed components,
measuring performance metrics like execution time, memory usage, and throughput.
"""

import time
import asyncio
import json
import os
import psutil
from typing import Dict, Any


class BenchmarkSuite:
    """Comprehensive benchmark suite for cryptofeed components."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        
    def time_function(self, name: str, func, *args, **kwargs):
        """Time a function execution and store results."""
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            duration = end_time - start_time
            self.results[name] = duration
            print(f"⏱️  {name}: {duration:.4f}s")
            return result
        except Exception as e:
            print(f"❌ {name} failed: {e}")
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
            print("⚠️ Cryptofeed not available, skipping FeedHandler benchmark")
            self.results["FeedHandler creation"] = -1
    
    def benchmark_exchange_setup(self):
        """Benchmark exchange configuration."""
        try:
            from cryptofeed.exchanges import Coinbase, Binance
            from cryptofeed.defines import TRADES
            
            def setup_exchanges():
                coinbase = Coinbase(symbols=['BTC-USD'], channels=[TRADES])
                binance = Binance(symbols=['BTCUSDT'], channels=[TRADES])
                return coinbase, binance
            
            self.time_function("Exchange setup", setup_exchanges)
        except ImportError:
            print("⚠️ Cryptofeed exchanges not available, skipping exchange benchmark")
            self.results["Exchange setup"] = -1
    
    def benchmark_memory_usage(self):
        """Benchmark memory consumption."""
        try:
            from cryptofeed import FeedHandler
            
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Create multiple handlers to test memory usage
            handlers = []
            for i in range(5):  # Reduced from 10 to 5 for stability
                fh = FeedHandler()
                handlers.append(fh)
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_diff = final_memory - initial_memory
            
            print(f"💾 Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB (+{memory_diff:.1f}MB)")
            self.results["memory_usage_mb"] = memory_diff
            
            # Cleanup
            del handlers
            
        except ImportError:
            print("⚠️ Cryptofeed not available, skipping memory benchmark")
            self.results["memory_usage_mb"] = -1
    
    def benchmark_import_time(self):
        """Benchmark import time for cryptofeed."""
        def import_cryptofeed():
            import cryptofeed
            return True
        
        self.time_function("Cryptofeed import", import_cryptofeed)
    
    def run_all_benchmarks(self):
        """Run all benchmark suites."""
        print("🚀 Starting cryptofeed benchmarks...")
        
        # Run basic benchmarks that should always work
        self.benchmark_import_time()
        
        # Run cryptofeed-specific benchmarks
        self.benchmark_feed_handler_creation()
        self.benchmark_exchange_setup()
        self.benchmark_memory_usage()
        
        print("\n📊 Benchmark Results Summary:")
        for name, value in self.results.items():
            if value == -1:
                print(f"  {name}: SKIPPED")
            elif "time" in name.lower() or name.endswith("_s"):
                print(f"  {name}: {value:.4f}s")
            elif "memory" in name.lower():
                print(f"  {name}: {value:.2f}MB")
            else:
                print(f"  {name}: {value}")
        
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
        print(f"\n✅ Results saved to {output_file}")
    except Exception as e:
        print(f"❌ Failed to save results: {e}")
    
    return results


if __name__ == "__main__":
    main()