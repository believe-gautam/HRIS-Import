from io import StringIO

from django.test import TestCase

from imports.analysis import analyze_csv
from imports.models import ImportScan, ScanEmployeeDetail, ScanIssue
from imports.persistence import save_analysis_result


class PersistenceTests(TestCase):
    def test_completed_analysis_round_trips_through_sqlite(self):
        csv_text = (
            "employee_id,employee_name,email,manager_id,manager_email,department\n"
            "ROOT,Root,root@example.com,,,Leadership\n"
            "M1,Manager,manager@example.com,ROOT,,Engineering\n"
            "E1,Report,report@example.com,M1,,Engineering\n"
            "A,Cycle A,a@example.com,B,,Operations\n"
            "B,Cycle B,b@example.com,A,,Operations\n"
            "BAD,Missing Manager,bad@example.com,UNKNOWN,,Sales\n"
        )
        result = analyze_csv(StringIO(csv_text))

        scan = save_analysis_result(
            result,
            original_filename="../../exports\\employees.csv",
        )
        self.assertEqual(scan.original_filename, "employees.csv")
        self.assertEqual(scan.total_rows, result.total_rows)
        self.assertEqual(scan.accepted_count, result.accepted_count)
        self.assertEqual(ImportScan.objects.count(), 1)
        self.assertEqual(ScanIssue.objects.count(), 1)
        self.assertEqual(
            ScanIssue.objects.get().messages,
            ["Manager ID 'UNKNOWN' was not found among accepted employees."],
        )
        self.assertEqual(
            ScanEmployeeDetail.objects.filter(
                category=ScanEmployeeDetail.Category.ROOT
            ).count(),
            1,
        )
        self.assertEqual(
            ScanEmployeeDetail.objects.filter(
                category=ScanEmployeeDetail.Category.MANAGER
            ).count(),
            4,
        )
        self.assertEqual(
            ScanEmployeeDetail.objects.filter(
                category=ScanEmployeeDetail.Category.CYCLE
            ).count(),
            2,
        )
        self.assertEqual(
            set(
                ScanEmployeeDetail.objects.filter(
                    category=ScanEmployeeDetail.Category.CYCLE
                ).values_list("employee_id", flat=True)
            ),
            {"A", "B"},
        )
