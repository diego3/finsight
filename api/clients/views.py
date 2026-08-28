from rest_framework import viewsets

from .models import Client
from .serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    """CRUD for clients: list, create, retrieve, update, destroy."""

    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    filterset_fields = ["risk_profile"]
    search_fields = ["name", "email"]
    ordering_fields = ["created_at", "name"]
