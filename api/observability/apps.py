from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    name = "observability"

    def ready(self) -> None:
        from .collectors import start_runtime_metrics

        start_runtime_metrics()
