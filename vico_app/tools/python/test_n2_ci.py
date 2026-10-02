"""Fail-closed CI result handling. These tests require only the standard library."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run_n2_ci import OPT_IN_JVM_TESTS, validate_jvm_log, validate_python_result


class CiResultTest(unittest.TestCase):
    def jvm_log(self, **changes):
        result = dict(run=36, passed=34, failed=0, assumption_skipped=2, ignored=0, runtime_ms=1)
        result.update(changes)
        return "\n".join(["ASSUMPTION_SKIPPED " + test for test in sorted(OPT_IN_JVM_TESTS)]
                         + [json.dumps(result)])

    def test_only_named_opt_in_jvm_skips_are_allowed(self):
        self.assertEqual(34, validate_jvm_log(self.jvm_log())["passed"])
        for change in ({"failed": 1}, {"ignored": 1}, {"assumption_skipped": 3}, {"passed": 0}, {"run": 37}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_jvm_log(self.jvm_log(**change))
        with self.assertRaises(ValueError):
            validate_jvm_log(self.jvm_log().replace(sorted(OPT_IN_JVM_TESTS)[0], "unexpectedSkip"))

    def test_python_skips_and_expected_failures_are_not_green(self):
        for outcome in ("skip", "expected_failure", "failure", "unexpected_success", "empty"):
            result = unittest.TestResult()
            case = unittest.FunctionTestCase(lambda: None)
            if outcome != "empty":
                result.startTest(case)
            if outcome == "skip":
                result.addSkip(case, "missing fixture")
            elif outcome == "unexpected_success":
                result.addUnexpectedSuccess(case)
            elif outcome != "empty":
                try:
                    raise AssertionError("fixture")
                except AssertionError:
                    method = result.addExpectedFailure if outcome == "expected_failure" else result.addFailure
                    method(case, sys.exc_info())
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                validate_python_result(result)

    def test_python_success_count_is_actual_run_count(self):
        suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
        result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertEqual(dict(run=1, passed=1, skipped=0, failed=0), validate_python_result(result))

    def test_cannot_claim_other_operating_system(self):
        other = "windows" if sys.platform != "win32" else "linux"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-created"
            process = subprocess.run([sys.executable, str(Path(__file__).with_name("run_n2_ci.py")),
                                      "--platform", other, "--output", str(output)],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(2, process.returncode)
            self.assertIn("Expected actual", process.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
