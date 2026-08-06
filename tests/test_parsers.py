import hashlib
from codeguard.feedback.parsers import PytestParser, RuffParser, MypyParser, GenericParser


# ── PytestParser ──────────────────────────────────────────────────────

class TestPytestParser:
    def test_passed_summary(self):
        parser = PytestParser()
        result = parser.parse("collected 3 items\nmain.py .\n\n3 passed")
        assert result["failure_category"] is None
        assert result["diagnostics"] == []

    def test_assertion_failure(self):
        parser = PytestParser()
        output = (
            "_____________________ FAILURES ______________________\n"
            "____ test_main.py:3: in test_hello\n"
            ">    assert 1 == 2\n"
            "E    assert 1 == 2\n\n"
            "FAILED test_main.py::test_hello"
        )
        result = parser.parse(output)
        assert result["failure_category"] == "TEST_FAILURE"
        assert len(result["diagnostics"]) >= 1

    def test_extracts_file_and_line(self):
        parser = PytestParser()
        output = "FAILED tests/test_foo.py:42::test_bar - AssertionError"
        result = parser.parse(output)
        assert len(result["diagnostics"]) >= 1
        d = result["diagnostics"][0]
        assert d["file"] == "tests/test_foo.py"
        assert d["line"] == 42

    def test_extracts_failure_location(self):
        parser = PytestParser()
        output = "FAILED src/main.py::test_func - assert 1 == 2"
        result = parser.parse(output)
        d = result["diagnostics"][0]
        assert "src/main.py" in d["file"]

    def test_empty_output_returns_none_category(self):
        parser = PytestParser()
        result = parser.parse("")
        assert result["failure_category"] is None

    def test_malformed_output_does_not_crash(self):
        parser = PytestParser()
        result = parser.parse("\x00\x01\x02garbage")
        assert result["failure_category"] is None

    def test_ansi_colors_stripped(self):
        parser = PytestParser()
        output = "\x1b[31mFAILED\x1b[0m test_main.py::test_foo"
        result = parser.parse(output)
        assert result["failure_category"] == "TEST_FAILURE"

    def test_does_not_match_casual_failed_word(self):
        parser = PytestParser()
        output = "The build failed because of network error"
        result = parser.parse(output)
        # "failed" alone without FAILED marker should not produce diagnostics
        assert result["failure_category"] is None

    def test_multiple_failures(self):
        parser = PytestParser()
        output = (
            "FAILED test_a.py::test_one - assert 1 == 2\n"
            "FAILED test_b.py::test_two - AssertionError"
        )
        result = parser.parse(output)
        assert len(result["diagnostics"]) >= 2

    def test_fingerprint_deterministic(self):
        parser = PytestParser()
        output = "FAILED test_a.py::test_one - assert 1 == 2"
        r1 = parser.parse(output)
        r2 = parser.parse(output)
        assert r1["fingerprint"] == r2["fingerprint"]

    def test_fingerprint_differs_for_different_failures(self):
        parser = PytestParser()
        r1 = parser.parse("FAILED test_a.py::test_one")
        r2 = parser.parse("FAILED test_b.py::test_two")
        assert r1["fingerprint"] != r2["fingerprint"]


# ── RuffParser ────────────────────────────────────────────────────────

class TestRuffParser:
    def test_standard_diagnostic(self):
        parser = RuffParser()
        output = "main.py:1:1: F401 `os` imported but unused"
        result = parser.parse(output)
        assert result["failure_category"] == "LINT_ERROR"
        assert len(result["diagnostics"]) >= 1
        d = result["diagnostics"][0]
        assert d["file"] == "main.py"
        assert d["line"] == 1
        assert d["column"] == 1
        assert d["code"] == "F401"

    def test_multiple_diagnostics(self):
        parser = RuffParser()
        output = (
            "main.py:1:1: F401 `os` imported but unused\n"
            "main.py:5:10: E501 line too long\n"
            "src/util.py:3:1: I001 import block is un-sorted"
        )
        result = parser.parse(output)
        assert len(result["diagnostics"]) == 3

    def test_windows_path(self):
        parser = RuffParser()
        output = r"src\module.py:10:5: E999 SyntaxError"
        result = parser.parse(output)
        assert len(result["diagnostics"]) >= 1
        d = result["diagnostics"][0]
        assert "src" in d["file"] and "module.py" in d["file"]

    def test_no_match_returns_none(self):
        parser = RuffParser()
        result = parser.parse("All checks passed!")
        assert result["failure_category"] is None

    def test_empty_output(self):
        parser = RuffParser()
        result = parser.parse("")
        assert result["failure_category"] is None

    def test_fingerprint_deterministic(self):
        parser = RuffParser()
        output = "main.py:1:1: F401 unused import"
        r1 = parser.parse(output)
        r2 = parser.parse(output)
        assert r1["fingerprint"] == r2["fingerprint"]

    def test_ansi_stripped(self):
        parser = RuffParser()
        output = "\x1b[31mmain.py:1:1: F401\x1b[0m unused import"
        result = parser.parse(output)
        assert result["failure_category"] == "LINT_ERROR"


# ── MypyParser ────────────────────────────────────────────────────────

class TestMypyParser:
    def test_standard_error(self):
        parser = MypyParser()
        output = 'main.py:10: error: Incompatible return value type (got "int", expected "str")'
        result = parser.parse(output)
        assert result["failure_category"] == "TYPE_ERROR"
        assert len(result["diagnostics"]) >= 1
        d = result["diagnostics"][0]
        assert d["file"] == "main.py"
        assert d["line"] == 10

    def test_with_column(self):
        parser = MypyParser()
        output = "main.py:10:5: error: Name 'x' is not defined"
        result = parser.parse(output)
        d = result["diagnostics"][0]
        assert d["file"] == "main.py"
        assert d["line"] == 10
        assert d.get("column") == 5

    def test_with_error_code(self):
        parser = MypyParser()
        output = 'main.py:10: error: Incompatible types  [assignment]'
        result = parser.parse(output)
        d = result["diagnostics"][0]
        assert d.get("code") == "assignment"

    def test_multiple_errors(self):
        parser = MypyParser()
        output = (
            "main.py:10: error: Type mismatch\n"
            "main.py:20: error: Missing return statement\n"
            "src/util.py:5: error: Name 'foo' is not defined"
        )
        result = parser.parse(output)
        assert len(result["diagnostics"]) == 3

    def test_windows_path(self):
        parser = MypyParser()
        output = r"src\module.py:10: error: Type mismatch"
        result = parser.parse(output)
        assert len(result["diagnostics"]) >= 1

    def test_warning_treated_as_failure(self):
        parser = MypyParser()
        output = "main.py:10: warning: Unused variable"
        result = parser.parse(output)
        assert result["failure_category"] is not None

    def test_no_match_returns_none(self):
        parser = MypyParser()
        result = parser.parse("Success: no issues found in 5 source files")
        assert result["failure_category"] is None

    def test_empty_output(self):
        parser = MypyParser()
        result = parser.parse("")
        assert result["failure_category"] is None

    def test_fingerprint_deterministic(self):
        parser = MypyParser()
        output = "main.py:10: error: Type mismatch"
        r1 = parser.parse(output)
        r2 = parser.parse(output)
        assert r1["fingerprint"] == r2["fingerprint"]

    def test_ansi_stripped(self):
        parser = MypyParser()
        output = "\x1b[31mmain.py:10: error:\x1b[0m Type mismatch"
        result = parser.parse(output)
        assert result["failure_category"] == "TYPE_ERROR"


# ── GenericParser ─────────────────────────────────────────────────────

class TestGenericParser:
    def test_unknown_failure(self):
        parser = GenericParser()
        result = parser.parse("Some error: something went wrong")
        assert result["failure_category"] == "UNKNOWN_FAILURE"

    def test_empty_output_does_not_crash(self):
        parser = GenericParser()
        result = parser.parse("")
        assert result["failure_category"] == "UNKNOWN_FAILURE"

    def test_has_deterministic_fingerprint(self):
        parser = GenericParser()
        output = "error: build failed"
        r1 = parser.parse(output)
        r2 = parser.parse(output)
        assert r1["fingerprint"] == r2["fingerprint"]


# ── Fingerprint quality ───────────────────────────────────────────────

class TestFingerprintQuality:
    def test_uses_sha256_not_hash(self):
        parser = PytestParser()
        result = parser.parse("FAILED test_a.py::test_one")
        fp = result["fingerprint"]
        assert fp is not None
        assert len(fp) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in fp)

    def test_empty_output_has_no_fingerprint(self):
        parser = PytestParser()
        result = parser.parse("")
        assert result["fingerprint"] is None