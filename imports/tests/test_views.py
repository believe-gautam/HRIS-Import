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
