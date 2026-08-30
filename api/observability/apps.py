from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    name = "observability"

    def ready(self) -> None:
        # Deferred import: settings must be configured before prometheus_client loads.
        from .runtime_metrics import install

        install()
