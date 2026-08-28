from django.db import models


class Client(models.Model):
    """A financial advisory client. First domain entity of the platform."""

    class RiskProfile(models.TextChoices):
        CONSERVATIVE = "conservative", "Conservative"
        MODERATE = "moderate", "Moderate"
        AGGRESSIVE = "aggressive", "Aggressive"

    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    risk_profile = models.CharField(
        max_length=20,
        choices=RiskProfile.choices,
        default=RiskProfile.MODERATE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
