"""Unit tests for the runtime-metrics module.

No Django and no Prometheus registry mutation: the metric table is exercised
against synthetic snapshots, and ``take_snapshot`` is checked for plausibility
against the running test process.
"""

from __future__ import annotations

import tracemalloc
from dataclasses import replace

import pytest

from observability import runtime_metrics as rm

SYNTHETIC = rm.Snapshot(
    rss_bytes=100_000_000,
    vsize_bytes=500_000_000,
    cpu_seconds=1.5,
    open_fds=12,
    allocated_blocks=50_000,
    gc_tracked=40_000,
    gc_garbage=0,
    gc_pending=(700, 3, 1),
    gc_collections=(10, 4, 2),
    gc_collected=(500, 40, 5),
    gc_uncollectable=(0, 0, 0),
    tracemalloc_bytes=(("current", 1_000), ("peak", 2_000)),
)

BY_NAME = {m.name: m for m in rm._METRICS}


class TestMetricTable:
    def test_metric_names_are_unique(self) -> None:
        names = [m.name for m in rm._METRICS]
        assert sorted(names) == sorted(set(names))

    def test_every_metric_reads_from_a_snapshot(self) -> None:
        for metric in rm._METRICS:
            for label_values, value in metric.read(SYNTHETIC):
                assert len(label_values) == len(metric.labels)
                assert isinstance(value, float)

    def test_pending_objects_are_labelled_by_generation(self) -> None:
        assert BY_NAME["python_gc_pending_objects"].read(SYNTHETIC) == [
            (("0",), 700.0),
            (("1",), 3.0),
            (("2",), 1.0),
        ]

    def test_tracemalloc_yields_nothing_when_not_tracing(self) -> None:
        idle = replace(SYNTHETIC, tracemalloc_bytes=())
        assert BY_NAME["python_tracemalloc_bytes"].read(idle) == []

    def test_builtin_replacements_are_exactly_the_process_and_counter_series(self) -> None:
        replaced = {m.name for m in rm._METRICS if m.replaces_builtin}
        assert replaced == {
            "process_resident_memory_bytes",
            "process_virtual_memory_bytes",
            "process_cpu_seconds_total",
            "process_open_fds",
            "python_gc_collections_total",
            "python_gc_objects_collected_total",
            "python_gc_objects_uncollectable_total",
        }


class TestLiveCollector:
    def test_omits_the_builtin_replacement_series(self) -> None:
        emitted = {family.name for family in rm._LiveCollector().collect()}
        assert not any(name.startswith("process_") for name in emitted)
        assert "python_allocated_blocks" in emitted
        assert "python_gc_collections" not in emitted  # built-in GC_COLLECTOR owns it

    def test_emitted_families_are_a_subset_of_the_non_builtin_metrics(self) -> None:
        emitted = {family.name for family in rm._LiveCollector().collect()}
        non_builtin = {m.name for m in rm._METRICS if not m.replaces_builtin}
        # tracemalloc is the only one that may be absent (off unless PYTHONTRACEMALLOC)
        assert emitted <= non_builtin
        assert non_builtin - emitted <= {"python_tracemalloc_bytes"}

    def test_family_labels_match_the_table(self) -> None:
        for family in rm._LiveCollector().collect():
            spec = BY_NAME[family.name]
            for sample in family.samples:
                assert tuple(sample.labels) == spec.labels or set(sample.labels) == set(spec.labels)


class TestTakeSnapshot:
    def test_reports_plausible_values_for_this_process(self) -> None:
        snap = rm.take_snapshot()
        assert snap.rss_bytes > 0
        assert snap.vsize_bytes >= snap.rss_bytes
        assert snap.open_fds > 0
        assert snap.allocated_blocks > 0
        assert snap.cpu_seconds >= 0
        assert len(snap.gc_pending) == 3
        assert len(snap.gc_collections) == 3

    def test_reflects_live_tracemalloc_state(self) -> None:
        was_tracing = tracemalloc.is_tracing()
        try:
            if not was_tracing:
                tracemalloc.start()
            snap = rm.take_snapshot()
            assert [kind for kind, _ in snap.tracemalloc_bytes] == ["current", "peak"]
        finally:
            if not was_tracing:
                tracemalloc.stop()


class TestInstallGuards:
    @pytest.mark.parametrize("command", ["migrate", "collectstatic", "test", "seed"])
    def test_one_shot_commands_are_detected(
        self, command: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(rm.sys, "argv", ["manage.py", command])
        assert rm._is_one_shot_command() is True

    @pytest.mark.parametrize("argv", [["manage.py", "runserver"], ["gunicorn"], ["pytest"]])
    def test_long_running_processes_are_not_one_shot(
        self, argv: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(rm.sys, "argv", argv)
        assert rm._is_one_shot_command() is False

    def test_multiprocess_mode_follows_the_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
        monkeypatch.delenv("prometheus_multiproc_dir", raising=False)
        assert rm._multiprocess_enabled() is False
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/xyz")
        assert rm._multiprocess_enabled() is True

    def test_install_is_idempotent_and_registers_one_collector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
        monkeypatch.delenv("prometheus_multiproc_dir", raising=False)
        monkeypatch.setattr(rm, "_installed", False)
        registered: list[object] = []
        monkeypatch.setattr(rm.REGISTRY, "register", registered.append)

        rm.install()
        rm.install()

        assert len(registered) == 1
        assert isinstance(registered[0], rm._LiveCollector)
