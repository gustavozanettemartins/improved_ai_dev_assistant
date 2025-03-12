#!/usr/bin/env python3

import time
from typing import Dict, List, Any
from colorama import Fore, Style
from tabulate import tabulate

class PerformanceTracker:
    """Track performance metrics of the assistant operations."""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {}
        
    def start_timer(self, operation: str) -> float:
        """Start timing an operation."""
        return time.time()
    
    def end_timer(self, operation: str, start_time: float) -> float:
        """End timing an operation and record the duration."""
        duration = time.time() - start_time
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(duration)
        return duration
    
    def increment_counter(self, counter: str, value: int = 1) -> int:
        """Increment a counter by a given value."""
        if counter not in self.counters:
            self.counters[counter] = 0
        self.counters[counter] += value
        return self.counters[counter]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics."""
        result = {"timers": {}, "counters": self.counters}
        for op, times in self.metrics.items():
            if times:
                result["timers"][op] = {
                    "count": len(times),
                    "total": sum(times),
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times)
                }
        return result
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.metrics = {}
        self.counters = {}

    def print_summary(self) -> None:
        """Print a summary of all metrics."""
        metrics = self.get_metrics()
        
        print(f"\n{Fore.CYAN}===== Performance Metrics ====={Style.RESET_ALL}")
        
        if metrics["timers"]:
            timer_data = []
            for op, stats in metrics["timers"].items():
                timer_data.append([
                    op, 
                    stats["count"],
                    f"{stats['total']:.2f}s",
                    f"{stats['avg']:.2f}s",
                    f"{stats['min']:.2f}s",
                    f"{stats['max']:.2f}s"
                ])
            
            print(f"\n{Fore.YELLOW}Operation Timers:{Style.RESET_ALL}")
            print(tabulate(
                timer_data, 
                headers=["Operation", "Count", "Total", "Average", "Min", "Max"],
                tablefmt="grid"
            ))
        
        if metrics["counters"]:
            counter_data = [[counter, value] for counter, value in metrics["counters"].items()]
            print(f"\n{Fore.YELLOW}Counters:{Style.RESET_ALL}")
            print(tabulate(
                counter_data,
                headers=["Counter", "Value"],
                tablefmt="grid"
            ))

# Global performance tracker instance
perf_tracker = PerformanceTracker()
