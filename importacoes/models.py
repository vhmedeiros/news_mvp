from django.db import models
from django.utils import timezone
from veiculos.models import Vehicle

class ImportStatus(models.TextChoices):
    IDLE = "idle", "Idle"
    RUNNING = "running", "Running"
    FAILED = "failed", "Failed"
    DONE = "done", "Done"

class ImportConfig(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="import_configs")
    name = models.CharField(max_length=150, help_text="A short label for this import")

    # XPaths
    editorial_xpaths = models.TextField(
        blank=True,
        help_text="1 XPath por linha. Cada linha extrai a URL do editoria"
    )
    listing_link_xpath = models.TextField(help_text="XPath that extracts article links from a section page.")
    article_section_name_xpath = models.TextField(blank=True, help_text="Optional: XPath to extract section name inside article.")
    article_date_xpath = models.TextField(blank=True)
    article_title_xpath = models.TextField()
    article_subtitle_xpath = models.TextField(blank=True)
    article_author_xpath = models.TextField(blank=True)
    article_content_xpath = models.TextField()

    # schedule
    interval_minutes = models.PositiveIntegerField(default=20)
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ImportStatus.choices, default=ImportStatus.IDLE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("vehicle", "name"),)
        ordering = ["vehicle__name", "name"]

    def __str__(self):
        return f"{self.vehicle.name} • {self.name}"

class ImportJob(models.Model):
    config = models.ForeignKey(ImportConfig, on_delete=models.CASCADE, related_name="jobs")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ImportStatus.choices, default=ImportStatus.RUNNING)
    found_count = models.PositiveIntegerField(default=0)
    new_count = models.PositiveIntegerField(default=0)
    log = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def mark_done(self, found: int, new: int):
        self.found_count = found
        self.new_count = new
        self.status = ImportStatus.DONE
        self.finished_at = timezone.now()
        self.save(update_fields=["found_count", "new_count", "status", "finished_at"])
