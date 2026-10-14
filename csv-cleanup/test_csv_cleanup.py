from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from csv_cleanup import clean


class CleanupTests(unittest.TestCase):
    def test_trim_blank_and_exact_dedupe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, output, report = root / "in.csv", root / "out.csv", root / "report.json"
            source.write_text("email,name,note\n a@example.com , Alice ,N/A\na@example.com,Alice,null\nb@example.com, Bob, keep \n", encoding="utf-8")
            result = clean(source, output, report, ["email"])
            self.assertEqual((result["rows_in"], result["rows_out"]), (3, 2))
            self.assertEqual(result["changes"]["duplicates_removed"], 1)
            self.assertEqual(result["changes"]["normalized_blank"], 2)
            with output.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0], {"email": "a@example.com", "name": "Alice", "note": ""})
            self.assertEqual(rows[1]["note"], "keep")
            self.assertEqual(json.loads(report.read_text())["rows_out"], 2)

    def test_full_row_default_keeps_distinct_values(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, output, report = root / "in.csv", root / "out.csv", root / "report.json"
            source.write_text("id,value\n1,A\n1,B\n", encoding="utf-8")
            result = clean(source, output, report)
            self.assertEqual(result["rows_out"], 2)

    def test_unknown_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "in.csv"
            source.write_text("id\n1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown dedupe"):
                clean(source, root / "out.csv", root / "report.json", ["missing"])

    def test_header_collision_after_trim_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "in.csv"
            source.write_text("id, id \n1,2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Headers become duplicated"):
                clean(source, root / "out.csv", root / "report.json")

    def test_blank_keys_are_preserved_and_formula_cells_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, output, report = root / "in.csv", root / "out.csv", root / "report.json"
            source.write_text("email,note\n,=2+2\n,+SUM(A1:A2)\n", encoding="utf-8")
            result = clean(source, output, report, ["email"])
            self.assertEqual(result["rows_out"], 2)
            self.assertEqual(result["changes"]["blank_dedupe_keys_preserved"], 2)
            self.assertEqual(result["changes"]["formula_like_cells"], 2)
            self.assertEqual(len(result["exceptions"]), 4)

    def test_extra_fields_are_rejected_instead_of_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "in.csv"
            source.write_text("id,name\n1,Alice,unexpected\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "more fields than the header"):
                clean(source, root / "out.csv", root / "report.json")

    def test_input_output_and_report_paths_must_be_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "in.csv"
            output = root / "out.csv"
            report = root / "report.json"
            source.write_text("id\n1\n", encoding="utf-8")
            for paths in ((source, source, report), (source, output, source), (source, output, output)):
                with self.subTest(paths=paths), self.assertRaisesRegex(ValueError, "must be different"):
                    clean(*paths)


if __name__ == "__main__":
    unittest.main()
