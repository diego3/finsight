"""CPython memory / GC metrics that survive a multi-process server.

`prometheus_client` ships live collectors for `process_*`, `python_gc_*` and
`python_info`. They work fine under `runserver` (one process), but under
gunicorn the `/metrics` endpoint aggregates *files* written by every worker
(`multiprocess.MultiProcessCollector`) and live collectors are dropped.

So:

* single process (dev)  -> register a normal live collector, keep the built-ins
* multi process (gunicorn, PROMETHEUS_MULTIPROC_DIR set)
      -> unregister the built-in ``process_*`` / ``python_gc_*`` collectors and
         replace them with ``multiprocess_mode="liveall"`` gauges that a
         per-worker background thread refreshes. Every series then carries a
         ``pid`` label, so the dashboard shows one line per worker (and can
         ``sum()`` for a total).

CPython has no fixed heap or stack size to expose the way a JVM does. Process
RSS is the real footprint; the rest are allocator / GC internals.
"""
import gc
import os
import sys
import threading
import time
import tracemalloc

from prometheus_client import REGISTRY, Gauge
from prometheus_client.core import GaugeMetricFamily

_MULTIPROC = bool(
    os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get("prometheus_multiproc_dir")
)
_SAMPLE_INTERVAL = float(os.getenv("RUNTIME_METRICS_INTERVAL", "10"))
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
_CLK_TCK = os.sysconf("SC_CLK_TCK")

_started = False


def _proc_stat():
    """(rss_bytes, vsize_bytes, cpu_seconds, num_fds) for the current process.

    /proc/self/stat field 2 is "(comm)" and can contain spaces and parens, so
    parse everything after the final ')'. In that tail, indices are:
    utime=11, stime=12, vsize=20, rss(pages)=21 (0-based).
    """
    with open("/proc/self/stat", "rb") as fh:
        raw = fh.read()
    tail = raw[raw.rindex(b")") + 2 :].split(b" ")
    utime, stime = int(tail[11]), int(tail[12])
    vsize, rss_pages = int(tail[20]), int(tail[21])
    num_fds = len(os.listdir("/proc/self/fd"))
    return rss_pages * _PAGE_SIZE, vsize, (utime + stime) / _CLK_TCK, num_fds


# --------------------------------------------------------------------------- #
# single process
# --------------------------------------------------------------------------- #
class _PythonRuntimeCollector:
    def collect(self):
        blocks = GaugeMetricFamily(
            "python_allocated_blocks",
            "Live memory blocks in the CPython allocator (sys.getallocatedblocks()).",
        )
        blocks.add_metric([], sys.getallocatedblocks())
        yield blocks

        tracked = GaugeMetricFamily(
            "python_gc_tracked_objects",
            "Objects tracked by the garbage collector (len(gc.get_objects())).",
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


# --------------------------------------------------------------------------- #
# multi process
# --------------------------------------------------------------------------- #
if _MULTIPROC:
    from prometheus_client import GC_COLLECTOR, PLATFORM_COLLECTOR, PROCESS_COLLECTOR

    for _c in (PROCESS_COLLECTOR, GC_COLLECTOR, PLATFORM_COLLECTOR):
        try:
            REGISTRY.unregister(_c)
        except KeyError:
            pass

    _M = "liveall"  # one series per worker pid
    _G_RSS = Gauge("process_resident_memory_bytes", "Resident memory size in bytes.", multiprocess_mode=_M)
    _G_VMS = Gauge("process_virtual_memory_bytes", "Virtual memory size in bytes.", multiprocess_mode=_M)
    _G_CPU = Gauge("process_cpu_seconds_total", "Total user + system CPU time spent in seconds.", multiprocess_mode=_M)
    _G_FDS = Gauge("process_open_fds", "Number of open file descriptors.", multiprocess_mode=_M)
    _G_BLOCKS = Gauge("python_allocated_blocks", "Live blocks in the CPython allocator.", multiprocess_mode=_M)
    _G_TRACKED = Gauge("python_gc_tracked_objects", "Objects tracked by the garbage collector.", multiprocess_mode=_M)
    _G_GARBAGE = Gauge("python_gc_garbage_objects", "Unreachable objects the collector could not free.", multiprocess_mode=_M)
    _G_PENDING = Gauge("python_gc_pending_objects", "gc.get_count() per generation.", ["generation"], multiprocess_mode=_M)
    _G_COLLECTIONS = Gauge("python_gc_collections_total", "Number of times each generation was collected.", ["generation"], multiprocess_mode=_M)
    _G_COLLECTED = Gauge("python_gc_objects_collected_total", "Objects collected during gc.", ["generation"], multiprocess_mode=_M)
    _G_UNCOLLECTABLE = Gauge("python_gc_objects_uncollectable_total", "Uncollectable objects found during gc.", ["generation"], multiprocess_mode=_M)
    _G_TRACEMALLOC = Gauge("python_tracemalloc_bytes", "Python-level allocated memory tracked by tracemalloc.", ["kind"], multiprocess_mode=_M)

    def _sample_once():
        rss, vms, cpu, fds = _proc_stat()
        _G_RSS.set(rss)
        _G_VMS.set(vms)
        _G_CPU.set(cpu)
        _G_FDS.set(fds)
        _G_BLOCKS.set(sys.getallocatedblocks())
        _G_TRACKED.set(len(gc.get_objects()))
        _G_GARBAGE.set(len(gc.garbage))
        for generation, count in enumerate(gc.get_count()):
            _G_PENDING.labels(str(generation)).set(count)
        for generation, stats in enumerate(gc.get_stats()):
            _G_COLLECTIONS.labels(str(generation)).set(stats["collections"])
            _G_COLLECTED.labels(str(generation)).set(stats["collected"])
            _G_UNCOLLECTABLE.labels(str(generation)).set(stats["uncollectable"])
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            _G_TRACEMALLOC.labels("current").set(current)
            _G_TRACEMALLOC.labels("peak").set(peak)

    def _sampler_loop():
        while True:
            try:
                _sample_once()
            except Exception:  # never let the metrics thread kill the worker
                pass
            time.sleep(_SAMPLE_INTERVAL)


def start_runtime_metrics() -> None:
    """Idempotent. Call once per process (from AppConfig.ready())."""
    global _started
    if _started:
        return
    _started = True

    if _MULTIPROC:
        _sample_once()
        threading.Thread(target=_sampler_loop, name="runtime-metrics", daemon=True).start()
    else:
        try:
            REGISTRY.register(_PythonRuntimeCollector())
        except ValueError:
            pass  # already registered (runserver autoreloader imports twice)
