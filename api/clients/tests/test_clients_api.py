import pytest
from rest_framework.test import APIClient

from clients.models import Client


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_create_and_list_client(api: APIClient) -> None:
    payload = {"name": "Ada Lovelace", "email": "ada@example.com", "risk_profile": "aggressive"}

    create = api.post("/api/clients/", payload, format="json")
    assert create.status_code == 201
    assert create.data["risk_profile"] == "aggressive"

    listing = api.get("/api/clients/")
    assert listing.status_code == 200
    assert listing.data["count"] == 1
    assert listing.data["results"][0]["name"] == "Ada Lovelace"


@pytest.mark.django_db
def test_email_must_be_unique(api: APIClient) -> None:
    Client.objects.create(name="First", email="dup@example.com")

    resp = api.post(
        "/api/clients/",
        {"name": "Second", "email": "dup@example.com"},
        format="json",
    )
    assert resp.status_code == 400
    assert "email" in resp.data


@pytest.mark.django_db
def test_update_and_delete_client(api: APIClient) -> None:
    client = Client.objects.create(name="Temp", email="temp@example.com")

    patch = api.patch(f"/api/clients/{client.id}/", {"phone": "+55 11 99999-0000"}, format="json")
    assert patch.status_code == 200
    assert patch.data["phone"] == "+55 11 99999-0000"

    delete = api.delete(f"/api/clients/{client.id}/")
    assert delete.status_code == 204
    assert Client.objects.count() == 0
