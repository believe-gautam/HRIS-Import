from django.db import models


class ImportScan(models.Model):
    original_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    total_rows = models.PositiveIntegerField()
    accepted_count = models.PositiveIntegerField()
    error_count = models.PositiveIntegerField()
    root_count = models.PositiveIntegerField()
    manager_count = models.PositiveIntegerField()
    cycle_count = models.PositiveIntegerField()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.created_at:%Y-%m-%d %H:%M})"


class ScanIssue(models.Model):
    scan = models.ForeignKey(
        ImportScan,
        on_delete=models.CASCADE,
        related_name="stored_issues",
    )
    position = models.PositiveIntegerField()
    source_row = models.PositiveIntegerField()
    messages = models.JSONField(default=list)
    search_text = models.TextField(blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["scan", "position"],
                name="unique_scan_issue_position",
            )
        ]
        indexes = [
            models.Index(
                fields=["scan", "source_row"],
                name="scan_issue_source_idx",
            )
        ]


class ScanEmployeeDetail(models.Model):
    class Category(models.TextChoices):
        ROOT = "root", "Root"
        MANAGER = "manager", "Manager"
        CYCLE = "cycle", "Cycle member"

    scan = models.ForeignKey(
        ImportScan,
        on_delete=models.CASCADE,
        related_name="employee_details",
    )
    category = models.CharField(max_length=10, choices=Category.choices)
    position = models.PositiveIntegerField()
    employee_id = models.TextField()
    employee_name = models.TextField(blank=True)
    email = models.TextField()
    department = models.TextField(blank=True)
    direct_report_count = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["category", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["scan", "category", "position"],
                name="unique_scan_detail_position",
            )
        ]
        indexes = [
            models.Index(
                fields=["scan", "category", "position"],
                name="scan_category_position_idx",
            ),
            models.Index(
                fields=["scan", "category", "employee_id"],
                name="scan_category_emp_id_idx",
            ),
            models.Index(
                fields=["scan", "category", "employee_name"],
                name="scan_category_name_idx",
            ),
            models.Index(
                fields=["scan", "category", "email"],
                name="scan_category_email_idx",
            ),
            models.Index(
                fields=["scan", "category", "department"],
                name="scan_category_dept_idx",
            ),
            models.Index(
                fields=["scan", "category", "direct_report_count"],
                name="scan_category_reports_idx",
            ),
        ]
