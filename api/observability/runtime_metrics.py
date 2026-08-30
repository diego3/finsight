"""Process-level runtime metrics (CPython memory, GC, file descriptors) for Prometheus.

Interface
---------
``install()`` — call once per process, from ``AppConfig.ready()``. Idempotent, and
a no-op for one-shot management commands. Everything else here is implementation.

Why this needs more than ``prometheus_client``'s built-ins
---------------------------------------------------------
``prometheus_client`` ships live collectors for ``process_*``, ``python_gc_*`` and
``python_info``. They work under ``runserver`` (one process), but under gunicorn the
``/metrics`` endpoint aggregates the per-worker ``.db`` files
(``multiprocess.MultiProcessCollector``) and live collectors are dropped.

So there is **one metric table** (``_METRICS``) consumed by **two adapters**:

* single process (dev) — ``_LiveCollector`` reads a fresh :class:`Snapshot` on every
  scrape and emits only the series the built-ins don't already provide.
* multi process (gunicorn, ``PROMETHEUS_MULTIPROC_DIR`` set) — ``_WorkerSampler``
  unregisters the built-in ``process_*`` / ``python_gc_*`` collectors (they can't see
  across workers) and republishes every series as a ``multiprocess_mode="liveall"``
  gauge that a per-worker daemon thread refreshes. Each series then carries a ``pid``
  label, so the dashboard shows one line per worker.

CPython has no fixed heap or stack size to expose the way a JVM does. Process RSS is
the real footprint; the rest are allocator / GC internals.
"""

from __future__ import annotations

import contextlib
import gc
import os
import sys
import threading
import time
import tracemalloc
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

from prometheus_client import REGISTRY, Gauge
from prometheus_client.core import GaugeMetricFamily

__all__ = ["Snapshot", "install", "take_snapshot"]

_SAMPLE_INTERVAL = float(os.getenv("RUNTIME_METRICS_INTERVAL", "10"))
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
_CLK_TCK = os.sysconf("SC_CLK_TCK")

# Management commands that load Django, do one thing and exit. Starting the sampler
# in these would leave a stale per-pid metrics file behind in multiprocess mode
# (migrate / collectstatic run from the entrypoint before the workers start).
_ONE_SHOT = frozenset(
    {
        "migrate",
        "makemigrations",
        "collectstatic",
        "check",
        "shell",
        "dbshell",
        "createsuperuser",
        "showmigrations",
        "seed",
        "test",
        "loaddata",
        "dumpdata",
    }
)


# --------------------------------------------------------------------------- #
# snapshot: the testable core
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Snapshot:
    """One reading of the current process's runtime state. Plain data, so the metric
    table can be exercised against a synthetic snapshot without a running process."""

    rss_bytes: int
    vsize_bytes: int
    cpu_seconds: float
    open_fds: int
    allocated_blocks: int
    gc_tracked: int
    gc_garbage: int
    gc_pending: tuple[int, ...]  # gc.get_count(), by generation
    gc_collections: tuple[int, ...]  # gc.get_stats()[g]["collections"], by generation
    gc_collected: tuple[int, ...]
    gc_uncollectable: tuple[int, ...]
    # (("current", n), ("peak", n)) while tracemalloc is tracing, else ().
    tracemalloc_bytes: tuple[tuple[str, int], ...]


def _proc_stat() -> tuple[int, int, float, int]:
    """``(rss_bytes, vsize_bytes, cpu_seconds, open_fds)`` from ``/proc/self``.

    ``/proc/self/stat`` field 2 is ``(comm)`` and can contain spaces and parens, so
    parse everything after the final ``)``. In that tail the 0-based indices are:
    utime=11, stime=12, vsize=20, rss(pages)=21.
    """
    with open("/proc/self/stat", "rb") as fh:
        raw = fh.read()
    tail = raw[raw.rindex(b")") + 2 :].split(b" ")
    utime, stime = int(tail[11]), int(tail[12])
    vsize, rss_pages = int(tail[20]), int(tail[21])
    open_fds = len(os.listdir("/proc/self/fd"))
    return rss_pages * _PAGE_SIZE, vsize, (utime + stime) / _CLK_TCK, open_fds


def take_snapshot() -> Snapshot:
    """Read the current process's runtime state. Cheap; safe to call once per scrape."""
    rss, vsize, cpu, fds = _proc_stat()
    stats = gc.get_stats()
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        traced: tuple[tuple[str, int], ...] = (("current", current), ("peak", peak))
    else:
        traced = ()
    return Snapshot(
        rss_bytes=rss,
        vsize_bytes=vsize,
        cpu_seconds=cpu,
        open_fds=fds,
        allocated_blocks=sys.getallocatedblocks(),
        gc_tracked=len(gc.get_objects()),
        gc_garbage=len(gc.garbage),
        gc_pending=tuple(gc.get_count()),
        gc_collections=tuple(s["collections"] for s in stats),
        gc_collected=tuple(s["collected"] for s in stats),
        gc_uncollectable=tuple(s["uncollectable"] for s in stats),
        tracemalloc_bytes=traced,
    )


# --------------------------------------------------------------------------- #
# the metric table: one definition, both adapters read it
# --------------------------------------------------------------------------- #
_Samples = list[tuple[Sequence[str], float]]


@dataclass(frozen=True)
class _Metric:
    name: str
    doc: str
    labels: tuple[str, ...]
    read: Callable[[Snapshot], _Samples]
    # True when this restores something a prometheus_client built-in collector
    # publishes. Emitted only in multiprocess mode, where those collectors are
    # unregistered because they cannot see across workers.
    replaces_builtin: bool = False


def _scalar(value: Callable[[Snapshot], float]) -> Callable[[Snapshot], _Samples]:
    return lambda snap: [((), value(snap))]


def _per_generation(
    value: Callable[[Snapshot], tuple[int, ...]],
) -> Callable[[Snapshot], _Samples]:
    return lambda snap: [((str(g),), float(v)) for g, v in enumerate(value(snap))]


_METRICS: tuple[_Metric, ...] = (
    _Metric(
        "process_resident_memory_bytes",
        "Resident memory size in bytes.",
        (),
        _scalar(lambda s: float(s.rss_bytes)),
        replaces_builtin=True,
    ),
    _Metric(
        "process_virtual_memory_bytes",
        "Virtual memory size in bytes.",
        (),
        _scalar(lambda s: float(s.vsize_bytes)),
        replaces_builtin=True,
    ),
    _Metric(
        "process_cpu_seconds_total",
        "Total user + system CPU time spent in seconds.",
        (),
        _scalar(lambda s: s.cpu_seconds),
        replaces_builtin=True,
    ),
    _Metric(
        "process_open_fds",
        "Number of open file descriptors.",
        (),
        _scalar(lambda s: float(s.open_fds)),
        replaces_builtin=True,
    ),
    _Metric(
        "python_allocated_blocks",
        "Live memory blocks in the CPython allocator (sys.getallocatedblocks()).",
        (),
        _scalar(lambda s: float(s.allocated_blocks)),
    ),
    _Metric(
        "python_gc_tracked_objects",
        "Objects tracked by the garbage collector (len(gc.get_objects())).",
        (),
        _scalar(lambda s: float(s.gc_tracked)),
    ),
    _Metric(
        "python_gc_garbage_objects",
        "Unreachable objects the collector could not free (len(gc.garbage)).",
        (),
        _scalar(lambda s: float(s.gc_garbage)),
    ),
    _Metric(
        "python_gc_pending_objects",
        "Allocations minus deallocations since each generation was last collected "
        "(gc.get_count()).",
        ("generation",),
        _per_generation(lambda s: s.gc_pending),
    ),
    _Metric(
        "python_gc_collections_total",
        "Number of times each generation was collected.",
        ("generation",),
        _per_generation(lambda s: s.gc_collections),
        replaces_builtin=True,
    ),
    _Metric(
        "python_gc_objects_collected_total",
        "Objects collected during gc.",
        ("generation",),
        _per_generation(lambda s: s.gc_collected),
        replaces_builtin=True,
    ),
    _Metric(
        "python_gc_objects_uncollectable_total",
        "Uncollectable objects found during gc.",
        ("generation",),
        _per_generation(lambda s: s.gc_uncollectable),
        replaces_builtin=True,
    ),
    _Metric(
        "python_tracemalloc_bytes",
        "Python-level allocated memory tracked by tracemalloc.",
        ("kind",),
        lambda s: [((kind,), float(n)) for kind, n in s.tracemalloc_bytes],
    ),
)


# --------------------------------------------------------------------------- #
# adapter 1: single process — a fresh snapshot on every scrape
# --------------------------------------------------------------------------- #
class _LiveCollector:
    """A ``prometheus_client`` collector. Reads a snapshot per scrape and emits the
    metrics that don't duplicate the still-registered built-in collectors."""

    def collect(self) -> Iterator[GaugeMetricFamily]:
        snap = take_snapshot()
        for metric in _METRICS:
            if metric.replaces_builtin:
                continue
            samples = metric.read(snap)
            if not samples:
                continue
            family = GaugeMetricFamily(metric.name, metric.doc, labels=list(metric.labels) or None)
            for label_values, value in samples:
                family.add_metric(list(label_values), value)
            yield family


# --------------------------------------------------------------------------- #
# adapter 2: multi process — a daemon thread pushes into liveall gauges
# --------------------------------------------------------------------------- #
def _unregister_builtins() -> None:
    """Drop prometheus_client's own ``process_*`` / ``python_gc_*`` / platform
    collectors. Under a multi-process server they only see one worker, so the
    sampler republishes those series per pid instead."""
    from prometheus_client import GC_COLLECTOR, PLATFORM_COLLECTOR, PROCESS_COLLECTOR

    for collector in (PROCESS_COLLECTOR, GC_COLLECTOR, PLATFORM_COLLECTOR):
        with contextlib.suppress(KeyError):
            REGISTRY.unregister(collector)


class _WorkerSampler:
    """Publishes every metric as a ``multiprocess_mode="liveall"`` gauge and refreshes
    them from a background thread. One series per worker pid."""

    def __init__(self, interval: float) -> None:
        self._interval = interval
        # Drop the built-ins first: they own some of these names, and creating our
        # own gauge for a name already registered raises DuplicateTimeseries.
        _unregister_builtins()
        self._gauges = {
            m.name: Gauge(m.name, m.doc, m.labels, multiprocess_mode="liveall") for m in _METRICS
        }

    def _sample_once(self) -> None:
        snap = take_snapshot()
        for metric in _METRICS:
            gauge = self._gauges[metric.name]
            for label_values, value in metric.read(snap):
                target = gauge.labels(*label_values) if metric.labels else gauge
                target.set(value)

    def _loop(self) -> None:
        while True:
            with contextlib.suppress(Exception):  # never let the thread kill the worker
                self._sample_once()
            time.sleep(self._interval)

    def start(self) -> None:
        self._sample_once()
        threading.Thread(target=self._loop, name="runtime-metrics", daemon=True).start()


# --------------------------------------------------------------------------- #
# interface
# --------------------------------------------------------------------------- #
_installed = False


def _multiprocess_enabled() -> bool:
    return bool(
        os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get("prometheus_multiproc_dir")  # noqa: SIM112  older prometheus_client
    )


def _is_one_shot_command() -> bool:
    return len(sys.argv) > 1 and sys.argv[1] in _ONE_SHOT


def install() -> None:
    """Wire up runtime metrics for this process. Call once, from ``AppConfig.ready()``.

    Idempotent, and a no-op for one-shot management commands.
    """
    global _installed
    if _installed or _is_one_shot_command():
        return
    _installed = True

    if _multiprocess_enabled():
        _WorkerSampler(_SAMPLE_INTERVAL).start()
    else:
        with contextlib.suppress(ValueError):  # runserver autoreloader imports twice
            REGISTRY.register(_LiveCollector())
