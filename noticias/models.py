from django.db import models
from veiculos.models import Vehicle, Section

class News(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="news")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="news")
    url = models.URLField(max_length=800)
    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=700, blank=True)
    author = models.CharField(max_length=300, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    content = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["vehicle", "url"], name="uniq_news_vehicle_url"),
        ]
        indexes = [
            models.Index(fields=["published_at"]),
            models.Index(fields=["title"]),
        ]
        ordering = ["-published_at", "-captured_at"]

    def __str__(self):
        return self.title[:60]
