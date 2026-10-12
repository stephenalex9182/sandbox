import unittest
from backend.services.log_parser import parse_log
from backend.services.patch_validation import validate_diff

class LogParserTests(unittest.TestCase):
    def test_python_traceback_frame_and_timestamp(self):
        log = '2026-10-12 10:12:13 ERROR ZeroDivisionError: bad\n  File "app.py", line 12, in divide'
        result = parse_log(log)
        self.assertEqual(result["error_type"], "ZeroDivisionError")
        self.assertEqual(result["file"], "app.py")
        self.assertEqual(result["line"], 12)
        self.assertEqual(result["function"], "divide")
        self.assertIsNotNone(result["timestamp"])

    def test_empty_log_is_rejected(self):
        with self.assertRaises(ValueError): parse_log(" \n")

class PatchValidationTests(unittest.TestCase):
    def test_accepts_scoped_unified_diff(self):
        diff = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x=1\n+x=2\n"
        self.assertEqual(validate_diff(diff)["files"], ["app.py"])

    def test_rejects_traversal_and_environment_files(self):
        for path in ("../app.py", ".env.production"):
            diff = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-a\n+b\n"
            with self.subTest(path=path), self.assertRaises(ValueError): validate_diff(diff)

if __name__ == "__main__": unittest.main()
