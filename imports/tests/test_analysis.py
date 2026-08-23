from io import StringIO

from django.test import SimpleTestCase

from imports.analysis import CSVImportError, analyze_csv, detect_cycle_members, parse_csv


HEADERS = "employee_id,employee_name,email,manager_id,manager_email,department\n"


class AnalysisTests(SimpleTestCase):
    def analyze(self, *rows: str):
        return analyze_csv(StringIO(HEADERS + "\n".join(rows) + "\n"))

    def test_normalizes_values_and_parses_quoted_commas(self):
        result = self.analyze(
            ' E1 ," Lovelace, Ada ", ADA@EXAMPLE.COM ,,, Research '
        )

        self.assertEqual(result.total_rows, 1)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.issues, ())
        self.assertEqual(result.roots[0].employee_id, "E1")
        self.assertEqual(result.roots[0].employee_name, "Lovelace, Ada")
        self.assertEqual(result.roots[0].email, "ada@example.com")
        self.assertEqual(result.roots[0].department, "Research")

    def test_headers_can_be_in_any_order(self):
        csv_text = (
            "email,department,manager_email,employee_name,employee_id,manager_id\n"
            "person@example.com,People,,Person,E1,\n"
        )

        result = analyze_csv(StringIO(csv_text))

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.roots[0].employee_id, "E1")

    def test_all_duplicate_identity_rows_are_rejected_and_cannot_be_managers(self):
        result = self.analyze(
            "M1,First,first@example.com,,,Leadership",
            "M1,Duplicate,duplicate@example.com,,,Leadership",
            "E2,Report,report@example.com,M1,,Engineering",
        )

        self.assertEqual(result.total_rows, 3)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual([issue.source_row for issue in result.issues], [2, 3, 4])
        self.assertIn("appears more than once", result.issues[0].messages[0])
        self.assertIn("appears more than once", result.issues[1].messages[0])
        self.assertIn("was not found", result.issues[2].messages[0])
        self.assertEqual(result.roots, ())
        self.assertEqual(result.managers, ())

    def test_duplicate_emails_are_case_insensitive(self):
        result = self.analyze(
            "E1,One,Same@Example.com,,,Engineering",
            "E2,Two, same@example.com ,,,Engineering",
        )

        self.assertEqual(result.accepted_count, 0)
        self.assertEqual(len(result.issues), 2)
        self.assertTrue(
            all("Email 'same@example.com'" in issue.messages[0] for issue in result.issues)
        )

    def test_manager_reference_modes_and_direct_report_counts(self):
        result = self.analyze(
            "E1,By ID,e1@example.com,M1,,Engineering",
            "M1,Manager,manager@example.com,,,Leadership",
            "E2,By email,e2@example.com,,MANAGER@EXAMPLE.COM,Engineering",
            "E3,By both,e3@example.com,M1,manager@example.com,Engineering",
        )

        self.assertEqual(result.accepted_count, 4)
        self.assertEqual(result.issues, ())
        self.assertEqual([root.employee_id for root in result.roots], ["M1"])
        self.assertEqual(len(result.managers), 1)
        self.assertEqual(result.managers[0].employee.employee_id, "M1")
        self.assertEqual(result.managers[0].direct_report_count, 3)

    def test_manager_errors_do_not_make_accepted_employee_a_root(self):
        result = self.analyze(
            "M1,Manager One,one@example.com,,,Leadership",
            "M2,Manager Two,two@example.com,,,Leadership",
            "E1,Conflict,e1@example.com,M1,two@example.com,Engineering",
            "E2,Self,e2@example.com,E2,,Engineering",
            "E3,Missing,e3@example.com,UNKNOWN,,Engineering",
        )

        self.assertEqual(result.accepted_count, 5)
        self.assertEqual([root.employee_id for root in result.roots], ["M1", "M2"])
        self.assertEqual([issue.source_row for issue in result.issues], [4, 5, 6])
        self.assertIn("different employees", result.issues[0].messages[0])
        self.assertIn("cannot manage themselves", result.issues[1].messages[0])
        self.assertIn("was not found", result.issues[2].messages[0])

    def test_cycle_detection_excludes_employee_leading_into_cycle(self):
        result = self.analyze(
            "A,Cycle A,a@example.com,B,,Engineering",
            "B,Cycle B,b@example.com,A,,Engineering",
            "C,Follower,c@example.com,A,,Engineering",
        )

        self.assertEqual(
            {employee.employee_id for employee in result.cyclic_employees},
            {"A", "B"},
        )
        self.assertEqual(result.managers[0].employee.employee_id, "A")
        self.assertEqual(result.managers[0].direct_report_count, 2)

    def test_iterative_cycle_detection_handles_very_deep_hierarchy(self):
        manager_by_employee = {
            f"E{index}": f"E{index - 1}" for index in range(1, 20_000)
        }

        self.assertEqual(detect_cycle_members(manager_by_employee), frozenset())

    def test_rejects_bad_headers_as_a_clear_file_error(self):
        with self.assertRaisesMessage(CSVImportError, "missing headers"):
            analyze_csv(StringIO("employee_id,email\nE1,e1@example.com\n"))

    def test_rejects_malformed_csv_as_a_clear_file_error(self):
        with self.assertRaisesMessage(CSVImportError, "Malformed CSV"):
            analyze_csv(StringIO(HEADERS + 'E1,"Unclosed,e1@example.com,,,Dept\n'))

    def test_rejects_rows_beyond_the_configured_safety_limit(self):
        csv_text = HEADERS + (
            "E1,One,one@example.com,,,People\n"
            "E2,Two,two@example.com,,,People\n"
            "E3,Three,three@example.com,,,People\n"
        )

        with self.assertRaisesMessage(CSVImportError, "2-row safety limit"):
            parse_csv(StringIO(csv_text), max_rows=2)
