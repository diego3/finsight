from django.core.management.base import BaseCommand

from clients.models import Client

SEED_CLIENTS = [
    ("Ada Lovelace", "ada@example.com", "+55 11 90000-0001", Client.RiskProfile.AGGRESSIVE),
    ("Grace Hopper", "grace@example.com", "+55 11 90000-0002", Client.RiskProfile.MODERATE),
    ("Alan Turing", "alan@example.com", "+55 11 90000-0003", Client.RiskProfile.CONSERVATIVE),
    ("Katherine Johnson", "katherine@example.com", "", Client.RiskProfile.MODERATE),
]


class Command(BaseCommand):
    help = "Populate the database with a few sample clients (idempotent)."

    def handle(self, *args, **options) -> None:
        created = 0
        for name, email, phone, risk in SEED_CLIENTS:
            _, was_created = Client.objects.get_or_create(
                email=email,
                defaults={"name": name, "phone": phone, "risk_profile": risk},
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Seed done. {created} new client(s)."))
