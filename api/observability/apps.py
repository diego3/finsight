from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    name = "observability"

    def ready(self) -> None:
        from .collectors import register_python_runtime_collector

        register_python_runtime_collector()
