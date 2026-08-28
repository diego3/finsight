"""Extra CPython memory / GC internals for Prometheus.

`prometheus_client` already ships a ProcessCollector (`process_resident_memory_bytes`,
`process_virtual_memory_bytes`, `process_cpu_seconds_total`, `process_open_fds`, …)
and a GCCollector (`python_gc_collections_total`, `python_gc_objects_collected_total`).

CPython has no fixed "heap" or "stack" size to report the way a JVM does — the
closest signals are the process RSS above and the allocator/GC internals below.
"""
import gc
import sys
import tracemalloc

from prometheus_client.core import REGISTRY, GaugeMetricFamily


class PythonRuntimeCollector:
    def collect(self):
        blocks = GaugeMetricFamily(
            "python_allocated_blocks",
            "Memory blocks currently allocated by the CPython allocator "
            "(sys.getallocatedblocks()).",
        )
        blocks.add_metric([], sys.getallocatedblocks())
        yield blocks

        tracked = GaugeMetricFamily(
            "python_gc_tracked_objects",
            "Objects currently tracked by the garbage collector "
            "(len(gc.get_objects())).",
        )
        tracked.add_metric([], len(gc.get_objects()))
        yield tracked

        garbage = GaugeMetricFamily(
            "python_gc_garbage_objects",
            "Unreachable objects the collector could not free (len(gc.garbage)).",
        )
        garbage.add_metric([], len(gc.garbage))
        yield garbage

        pending = GaugeMetricFamily(
            "python_gc_pending_objects",
            "Allocations minus deallocations since each generation was last "
            "collected (gc.get_count()).",
            labels=["generation"],
        )
        for generation, count in enumerate(gc.get_count()):
            pending.add_metric([str(generation)], count)
        yield pending

        # Only populated when tracemalloc is on (PYTHONTRACEMALLOC=1). It roughly
        # doubles memory and slows allocation, so it is opt-in.
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            traced = GaugeMetricFamily(
                "python_tracemalloc_bytes",
                "Python-level allocated memory tracked by tracemalloc.",
                labels=["kind"],
            )
            traced.add_metric(["current"], current)
            traced.add_metric(["peak"], peak)
            yield traced


def register_python_runtime_collector() -> None:
    try:
        REGISTRY.register(PythonRuntimeCollector())
    except ValueError:
        # Already registered (the runserver autoreloader imports apps twice).
        pass
