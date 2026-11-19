#!/usr/bin/env python3
"""Fail closed on missing reports, tool failures and HIGH/CRITICAL findings."""
import json
import pathlib
import sys


def evaluate(reports: pathlib.Path) -> tuple[dict, bool]:
    results = {}
    for name in ("image-save", "hadolint", "trivy-config", "trivy-image", "sbom"):
        try:
            code = int((reports / f"{name}.exit").read_text().strip())
            data = None if name == "image-save" else json.loads(
                (reports / ("sbom.cdx.json" if name == "sbom" else f"{name}.json")).read_text()
            )
            if name == "hadolint":
                if not isinstance(data, list):
                    raise ValueError("Hadolint report must be an array")
                findings = sum(item.get("level") == "error" for item in data)
            elif name.startswith("trivy-"):
                if not isinstance(data, dict) or not isinstance(data.get("Results", []), list):
                    raise ValueError("Invalid Trivy report")
                if "SchemaVersion" not in data:
                    raise ValueError("Missing Trivy schema")
                if name == "trivy-config" and not any(
                    result.get("Type") == "dockerfile"
                    and sum(result.get("MisconfSummary", {}).values()) > 0
                    for result in data.get("Results", [])
                ):
                    raise ValueError("No Dockerfile checks were reported")
                findings = sum(
                    item.get("Severity") in ("HIGH", "CRITICAL")
                    for result in data.get("Results", [])
                    for key in ("Vulnerabilities", "Misconfigurations")
                    for item in (result.get(key) or [])
                )
                if name == "trivy-image" and not data.get("Results"):
                    raise ValueError("No scanned image packages reported")
                if name == "trivy-image":
                    packages = {package.get("Name") for result in data["Results"] for package in (result.get("Packages") or [])}
                    expected = {"libcrypt1", "libssl3t64", "libpcre2-8-0", "zlib1g"}
                    if missing := expected - packages:
                        raise ValueError(f"Missing runtime package metadata: {sorted(missing)}")
            else:
                findings = 0
                if name == "sbom" and data.get("bomFormat") != "CycloneDX":
                    raise ValueError("Invalid CycloneDX SBOM")
            results[name] = {"exit_code": code, "blocking_findings": findings, "passed": code == 0 and findings == 0}
        except (OSError, ValueError, TypeError, AttributeError) as error:
            results[name] = {"passed": False, "error": str(error)}
    return results, all(item["passed"] for item in results.values())


if __name__ == "__main__":
    directory = pathlib.Path(sys.argv[1])
    details, passed = evaluate(directory)
    (directory / "scan-summary.json").write_text(json.dumps({"passed": passed, "checks": details}, indent=2) + "\n")
    lines = ["| Check | Result | Blocking findings |", "| --- | --- | --- |"]
    lines += [f"| {name} | {'PASS' if item['passed'] else 'FAIL'} | {item.get('blocking_findings', 'tool/report error')} |" for name, item in details.items()]
    summary = "\n".join(lines) + "\n"
    (directory / "scan-summary.md").write_text(summary)
    print(summary)
    sys.exit(0 if passed else 1)
