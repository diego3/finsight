from rest_framework.routers import DefaultRouter

from .views import ClientViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")

urlpatterns = router.urls
