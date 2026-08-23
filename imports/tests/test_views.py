from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from imports.models import ImportScan, ScanEmployeeDetail


class UploadViewTests(TestCase):
    def test_get_displays_upload_form(self):
        response = self.client.get(reverse("imports:upload"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HRIS import preview")
        self.assertContains(response, "Analyze CSV")

    def test_post_displays_analysis(self):
        csv_bytes = (
            b"employee_id,employee_name,email,manager_id,manager_email,department\n"
            b"E1,Person,person@example.com,,,People\n"
        )

        response = self.client.post(
            reverse("imports:upload"),
            {"csv_file": SimpleUploadedFile("employees.csv", csv_bytes)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        scan = ImportScan.objects.get()
        self.assertEqual(
            response.redirect_chain,
            [(reverse("imports:scan_detail", args=[scan.id]), 302)],
        )
        self.assertContains(response, f"Saved scan #{scan.id}")
        self.assertContains(response, "person@example.com")
        self.assertEqual(scan.original_filename, "employees.csv")
        self.assertEqual(scan.total_rows, 1)
        self.assertEqual(scan.accepted_count, 1)
        self.assertEqual(scan.root_count, 1)
        self.assertEqual(
            scan.employee_details.get().category,
            ScanEmployeeDetail.Category.ROOT,
        )

    def test_utf8_bom_is_supported(self):
        csv_bytes = (
            b"\xef\xbb\xbfemployee_id,employee_name,email,manager_id,manager_email,department\n"
            b"E1,Person,PERSON@example.com,,,People\n"
        )

        response = self.client.post(
            reverse("imports:upload"),
            {"csv_file": SimpleUploadedFile("employees.csv", csv_bytes)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "person@example.com")
        self.assertNotContains(response, "Invalid CSV header")

    def test_invalid_utf8_is_shown_as_a_form_error(self):
        response = self.client.post(
            reverse("imports:upload"),
            {"csv_file": SimpleUploadedFile("employees.csv", b"\xff\xfe\x00bad")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must be valid UTF-8")
        self.assertFalse(ImportScan.objects.exists())

    def test_result_tables_have_search_sort_and_pagination_controls(self):
        header = (
            "employee_id,employee_name,email,manager_id,manager_email,department\n"
        )
        rows = [
            f"E{index},Person {index},person{index}@example.com,,,People"
            for index in range(30)
        ]

        response = self.client.post(
            reverse("imports:upload"),
            {
                "csv_file": SimpleUploadedFile(
                    "employees.csv",
                    (header + "\n".join(rows) + "\n").encode(),
                )
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["initial_pages"]["roots"]["total"], 30)
        self.assertEqual(len(response.context["initial_pages"]["roots"]["rows"]), 25)
        self.assertContains(response, 'data-role="search"', count=4)
        self.assertContains(response, 'data-role="page-size"', count=4)
        self.assertContains(response, 'data-role="previous"', count=4)
        self.assertContains(response, "imports/results-table.js")

        # Only the first page is in the fallback HTML; JavaScript renders later pages.
        html = response.content.decode()
        roots_section = html.split('data-table-key="roots"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertEqual(roots_section.count("<tr>"), 26)  # Header + 25 rows.
        self.assertNotContains(response, "person29@example.com")

        scan = ImportScan.objects.get()
        page_response = self.client.get(
            reverse("imports:scan_table_data", args=[scan.id, "roots"]),
            {"page": 2, "page_size": 10},
        )
        page_data = page_response.json()
        self.assertEqual(page_data["total"], 30)
        self.assertEqual(page_data["page"], 2)
        self.assertEqual(len(page_data["rows"]), 10)
        self.assertEqual(page_data["rows"][0]["employee_id"], "E10")

        oversized_page_response = self.client.get(
            reverse("imports:scan_table_data", args=[scan.id, "roots"]),
            {"page_size": 1_000_000},
        )
        self.assertEqual(oversized_page_response.json()["page_size"], 25)
        self.assertEqual(len(oversized_page_response.json()["rows"]), 25)

        search_response = self.client.get(
            reverse("imports:scan_table_data", args=[scan.id, "roots"]),
            {"q": "person 29"},
        )
        self.assertEqual(search_response.json()["total"], 1)
        self.assertEqual(
            search_response.json()["rows"][0]["employee_id"],
            "E29",
        )

        sort_response = self.client.get(
            reverse("imports:scan_table_data", args=[scan.id, "roots"]),
            {
                "sort": "employee_name",
                "direction": "descending",
                "page_size": 10,
            },
        )
        returned_names = [row["employee_name"] for row in sort_response.json()["rows"]]
        expected_names = sorted(
            (f"Person {index}" for index in range(30)),
            reverse=True,
        )[:10]
        self.assertEqual(returned_names, expected_names)

    def test_table_json_escapes_script_like_employee_values(self):
        csv_bytes = (
            b"employee_id,employee_name,email,manager_id,manager_email,department\n"
            b"E1,</script><script>alert(1)</script>,person@example.com,,,People\n"
        )

        response = self.client.post(
            reverse("imports:upload"),
            {"csv_file": SimpleUploadedFile("employees.csv", csv_bytes)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "</script><script>alert(1)</script>")
        self.assertContains(response, "\\u003Cscript\\u003Ealert(1)")

    def test_result_data_endpoint_rejects_unknown_tables(self):
        scan = ImportScan.objects.create(
            original_filename="employees.csv",
            total_rows=0,
            accepted_count=0,
            error_count=0,
            root_count=0,
            manager_count=0,
            cycle_count=0,
        )

        response = self.client.get(
            reverse("imports:scan_table_data", args=[scan.id, "unknown"])
        )

        self.assertEqual(response.status_code, 404)

    def test_history_lists_and_reopens_a_saved_scan(self):
        csv_bytes = (
            b"employee_id,employee_name,email,manager_id,manager_email,department\n"
            b"E1,History Person,history@example.com,,,People\n"
        )
        self.client.post(
            reverse("imports:upload"),
            {"csv_file": SimpleUploadedFile("history-example.csv", csv_bytes)},
        )
        scan = ImportScan.objects.get()

        history_response = self.client.get(reverse("imports:history"))
        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, "history-example.csv")
        self.assertContains(history_response, f"#{scan.id}")

        detail_response = self.client.get(
            reverse("imports:scan_detail", args=[scan.id])
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, f"Saved scan #{scan.id}")
        self.assertContains(detail_response, "history@example.com")
        self.assertContains(detail_response, 'data-role="search"', count=4)

    def test_history_search_filters_by_filename(self):
        required_counts = {
            "total_rows": 1,
            "accepted_count": 1,
            "error_count": 0,
            "root_count": 1,
            "manager_count": 0,
            "cycle_count": 0,
        }
        ImportScan.objects.create(original_filename="alpha.csv", **required_counts)
        ImportScan.objects.create(original_filename="beta.csv", **required_counts)

        response = self.client.get(reverse("imports:history"), {"q": "alpha"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alpha.csv")
        self.assertNotContains(response, "beta.csv")

    def test_history_is_paginated_at_twenty_scans(self):
        scans = [
            ImportScan(
                original_filename=f"scan-{index}.csv",
                total_rows=index,
                accepted_count=index,
                error_count=0,
                root_count=1,
                manager_count=0,
                cycle_count=0,
            )
            for index in range(21)
        ]
        ImportScan.objects.bulk_create(scans)

        first_page = self.client.get(reverse("imports:history"))
        second_page = self.client.get(reverse("imports:history"), {"page": 2})

        self.assertEqual(len(first_page.context["page"].object_list), 20)
        self.assertTrue(first_page.context["page"].has_next())
        self.assertEqual(len(second_page.context["page"].object_list), 1)
