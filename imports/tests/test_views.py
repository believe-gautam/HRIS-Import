from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse


class UploadViewTests(SimpleTestCase):
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
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analysis complete")
        self.assertContains(response, "person@example.com")

    def test_utf8_bom_is_supported(self):
        csv_bytes = (
            b"\xef\xbb\xbfemployee_id,employee_name,email,manager_id,manager_email,department\n"
            b"E1,Person,PERSON@example.com,,,People\n"
        )

        response = self.client.post(
            reverse("imports:upload"),
            {"csv_file": SimpleUploadedFile("employees.csv", csv_bytes)},
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
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["table_data"]["roots"]), 30)
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

    def test_table_json_escapes_script_like_employee_values(self):
        csv_bytes = (
            b"employee_id,employee_name,email,manager_id,manager_email,department\n"
            b"E1,</script><script>alert(1)</script>,person@example.com,,,People\n"
        )

        response = self.client.post(
            reverse("imports:upload"),
            {"csv_file": SimpleUploadedFile("employees.csv", csv_bytes)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "</script><script>alert(1)</script>")
        self.assertContains(response, "\\u003Cscript\\u003Ealert(1)")
