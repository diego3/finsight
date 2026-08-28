from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", healthcheck, name="health"),
    path("api/", include("clients.urls")),
    # Prometheus scrape endpoint. Public for local dev — put behind auth/network
    # policy before any real deployment.
    path("", include("django_prometheus.urls")),
]
