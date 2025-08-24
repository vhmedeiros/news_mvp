from django.db import models

class MediaType(models.TextChoices):
    SITE = "site", "Site"
    BLOG = "blog", "Blog"
    MAGAZINE = "magazine", "Magazine"
    TELEVISION = "television", "Television"
    RADIO = "radio", "Radio"
    PODCAST = "podcast", "Podcast"
    VIDEOCAST = "videocast", "Videocast"

class Status(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"

class Vehicle(models.Model):
    name = models.CharField(max_length=150)
    media_type = models.CharField(max_length=20, choices=MediaType.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    country = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    url = models.URLField(max_length=500)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["media_type"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.name
    
    
    def location_display(self):
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts)

class Section(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=150)

    class Meta:
        unique_together = (("vehicle", "name"),)
        ordering = ["vehicle__name", "name"]

    def __str__(self):
        return f"{self.vehicle.name} • {self.name}"
