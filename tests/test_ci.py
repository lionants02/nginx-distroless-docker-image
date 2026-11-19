import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "ci" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


image_ref = load("image_ref").image_ref
evaluate = load("scan_gate").evaluate


class TagRules(unittest.TestCase):
    def test_main_only_latest(self):
        self.assertEqual(image_ref("Owner/Repo", "refs/heads/main"), "ghcr.io/owner/repo:latest")

    def test_branch_slash_and_collision(self):
        self.assertEqual(image_ref("o/r", "refs/heads/feature/test"), image_ref("o/r", "refs/heads/feature-test"))

    def test_git_tag_unchanged(self):
        self.assertEqual(image_ref("o/r", "refs/tags/v1.2.3"), "ghcr.io/o/r:v1.2.3")

    def test_invalid_refs_fail(self):
        for ref in ("refs/tags/latest", "refs/heads/latest", "refs/tags/release/v1", "refs/tags/-bad", "refs/heads/ไทย", "refs/tags/" + "x" * 129, "refs/pull/1/merge"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                image_ref("o/r", ref)


class ScanGate(unittest.TestCase):
    def fixture(self, path):
        for name in ("image-save", "hadolint", "trivy-config", "trivy-image", "sbom"):
            (path / f"{name}.exit").write_text("0\n")
        (path / "hadolint.json").write_text("[]")
        for name in ("trivy-config", "trivy-image"):
            result = {"Type": "dockerfile", "MisconfSummary": {"Successes": 1, "Failures": 0}} if name == "trivy-config" else {
                "Type": "debian", "Packages": [{"Name": package} for package in ("libcrypt1", "libssl3t64", "libpcre2-8-0", "zlib1g", "libzstd1")]
            }
            (path / f"{name}.json").write_text(json.dumps({"SchemaVersion": 2, "Results": [result]}))
        (path / "sbom.cdx.json").write_text('{"bomFormat":"CycloneDX"}')

    def test_success_and_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            (path / "hadolint.json").write_text('[{"level":"warning"}]')
            self.assertTrue(evaluate(path)[1])

    def test_high_blocks_even_without_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            report = json.loads((path / "trivy-image.json").read_text())
            report["Results"][0]["Vulnerabilities"] = [{"Severity": "HIGH", "FixedVersion": ""}]
            (path / "trivy-image.json").write_text(json.dumps(report))
            details, passed = evaluate(path)
            self.assertFalse(passed)
            self.assertEqual(details["trivy-image"]["blocking_findings"], 1)

    def test_critical_config_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            report = json.loads((path / "trivy-config.json").read_text())
            report["Results"][0]["Misconfigurations"] = [{"Severity": "CRITICAL"}]
            (path / "trivy-config.json").write_text(json.dumps(report))
            details, passed = evaluate(path)
            self.assertFalse(passed)
            self.assertEqual(details["trivy-config"]["blocking_findings"], 1)

    def test_tool_failure_or_missing_report_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            (path / "trivy-image.exit").write_text("125")
            self.assertFalse(evaluate(path)[1])
            (path / "trivy-image.exit").write_text("0")
            (path / "trivy-image.json").unlink()
            self.assertFalse(evaluate(path)[1])

    def test_empty_scan_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name in ("trivy-config", "trivy-image"):
                self.fixture(path)
                (path / f"{name}.json").write_text('{"SchemaVersion":2,"Results":[]}')
                self.assertFalse(evaluate(path)[1])

    def test_missing_library_metadata_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            (path / "trivy-image.json").write_text('{"SchemaVersion":2,"Results":[{"Packages":[]}]}')
            self.assertFalse(evaluate(path)[1])

    def test_hadolint_error_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            (path / "hadolint.json").write_text('[{"level":"error"}]')
            self.assertFalse(evaluate(path)[1])


if __name__ == "__main__":
    unittest.main()
