import sys

from django.apps import AppConfig

# Management commands that load Django, do one thing, and exit. Starting the
# runtime-metrics sampler in these would leave a stale per-pid metrics file
# behind in multiprocess mode (migrate/collectstatic run from the entrypoint).
_ONE_SHOT = {
    "migrate", "makemigrations", "collectstatic", "check", "shell", "dbshell",
    "createsuperuser", "showmigrations", "seed", "test", "loaddata", "dumpdata",
}


class ObservabilityConfig(AppConfig):
    name = "observability"

    def ready(self) -> None:
        if len(sys.argv) > 1 and sys.argv[1] in _ONE_SHOT:
            return
        from .collectors import start_runtime_metrics

        start_runtime_metrics()
