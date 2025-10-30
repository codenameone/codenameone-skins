#!/usr/bin/env python3
"""Verify generated Codename One skins by loading them with the JavaSE simulator."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List
from urllib.request import Request, urlopen

CODENAMEONE_JAR_URLS = [
    "https://repo1.maven.org/maven2/com/codenameone/codenameone-core/7.0.209/codenameone-core-7.0.209.jar",
    "https://repo1.maven.org/maven2/com/codenameone/codenameone-core/7.0.208/codenameone-core-7.0.208.jar",
    "https://github.com/codenameone/CodenameOne/releases/latest/download/CodenameOne.jar",
    "https://raw.githubusercontent.com/codenameone/CodenameOne/master/dist/CodenameOne.jar",
    "https://repo1.maven.org/maven2/com/codenameone/codenameone/7.0/codenameone-7.0.jar",
    "https://repo1.maven.org/maven2/com/codenameone/codenameone/6.0/codenameone-6.0.jar",
]
JAVA_SE_PORT_JAR_URLS = [
    "https://repo1.maven.org/maven2/com/codenameone/codenameone-javase/7.0.209/codenameone-javase-7.0.209.jar",
    "https://repo1.maven.org/maven2/com/codenameone/codenameone-javase/7.0.208/codenameone-javase-7.0.208.jar",
    "https://github.com/codenameone/CodenameOne/releases/latest/download/JavaSEPort.jar",
    "https://raw.githubusercontent.com/codenameone/CodenameOne/master/dist/JavaSEPort.jar",
    "https://repo1.maven.org/maven2/com/codenameone/java-se/7.0/java-se-7.0.jar",
    "https://repo1.maven.org/maven2/com/codenameone/java-se/6.0/java-se-6.0.jar",
]
HARNESS_SOURCE = Path(__file__).resolve().parent / "java" / "SkinHarness.java"


class VerificationError(RuntimeError):
    """Raised when a verification step fails."""


def _load_report(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    generated = data.get("generated", [])
    if not isinstance(generated, list):
        raise VerificationError("Report file is malformed: 'generated' should be a list")
    return [entry for entry in generated if isinstance(entry, dict)]


def _ensure_artifact(target_dir: Path, urls: Iterable[str]) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for url in urls:
        filename = url.rsplit("/", 1)[-1]
        artifact_path = target_dir / filename
        if artifact_path.exists():
            return artifact_path

        try:
            request = Request(url, headers={"User-Agent": "codenameone-skin-verifier/1.0"})
            with urlopen(request) as response, tempfile.NamedTemporaryFile(delete=False) as tmp:
                shutil.copyfileobj(response, tmp)
                tmp.flush()
                tmp_path = Path(tmp.name)
        except Exception as exc:  # urllib raises a variety of exceptions, surface them uniformly
            errors.append(f"{url}: {exc}")
            continue

        tmp_path.replace(artifact_path)
        return artifact_path

    raise VerificationError(
        "Failed to download required artifact. Attempts: " + "; ".join(errors) if errors else "No URLs supplied"
    )


def _find_tool(tool_name: str) -> Path:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home).expanduser().resolve() / "bin" / tool_name
        if candidate.exists():
            return candidate
    resolved = shutil.which(tool_name)
    if resolved:
        return Path(resolved).resolve()
    raise VerificationError(f"{tool_name} executable not found – ensure a JDK providing {tool_name} is installed")


def _compile_harness(harness_path: Path, classpath: Iterable[Path], output_dir: Path) -> None:
    javac = _find_tool("javac")
    output_dir.mkdir(parents=True, exist_ok=True)
    cp_value = os.pathsep.join(path.as_posix() for path in classpath)
    cmd = [
        javac.as_posix(),
        "-cp",
        cp_value,
        "-d",
        output_dir.as_posix(),
        harness_path.as_posix(),
    ]
    subprocess.run(cmd, check=True)


def _run_harness(classpath: Iterable[Path], classes_dir: Path, skin_path: Path) -> None:
    java = _find_tool("java")
    xvfb_run = shutil.which("xvfb-run")
    if not xvfb_run:
        raise VerificationError("xvfb-run is required to execute the Codename One simulator in headless mode")

    cp_entries = list(classpath) + [classes_dir]
    cp_value = os.pathsep.join(path.as_posix() for path in cp_entries)
    cmd = [
        Path(xvfb_run).resolve().as_posix(),
        "-a",
        java.as_posix(),
        "-Djava.awt.headless=true",
        "-cp",
        cp_value,
        "SkinHarness",
        skin_path.as_posix(),
    ]
    subprocess.run(cmd, check=True)


def verify_skins(
    report_file: Path,
    work_dir: Path,
    codenameone_urls: Iterable[str],
    javase_port_urls: Iterable[str],
) -> None:
    generated = _load_report(report_file)
    if not generated:
        print("No generated skins to verify.")
        return

    if not HARNESS_SOURCE.exists():
        raise VerificationError(f"Harness source not found at {HARNESS_SOURCE}")

    work_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = work_dir / "artifacts"
    classes_dir = work_dir / "classes"
    codenameone_jar = _ensure_artifact(artifacts_dir, codenameone_urls)
    javase_port_jar = _ensure_artifact(artifacts_dir, javase_port_urls)
    classpath = [codenameone_jar, javase_port_jar]

    _compile_harness(HARNESS_SOURCE, classpath, classes_dir)

    for entry in generated:
        skin_path = Path(entry["archive"]).resolve()
        if not skin_path.is_file():
            raise VerificationError(f"Skin archive not found: {skin_path}")
        print(f"Verifying skin {entry.get('skin')} at {skin_path}")
        _run_harness(classpath, classes_dir, skin_path)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codename One skin verification")
    parser.add_argument("--report-file", type=Path, required=True, help="Path to the JSON report emitted by the generator")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("tmp") / "codenameone",
        help="Directory used to cache Codename One artifacts and compilation output",
    )
    parser.add_argument(
        "--codenameone-url",
        action="append",
        default=[],
        help="URL of the Codename One API jar to download (can be provided multiple times)",
    )
    parser.add_argument(
        "--javase-url",
        action="append",
        default=[],
        help="URL of the Codename One JavaSEPort simulator jar to download (can be provided multiple times)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    codenameone_urls = args.codenameone_url or CODENAMEONE_JAR_URLS
    javase_urls = args.javase_url or JAVA_SE_PORT_JAR_URLS

    try:
        verify_skins(args.report_file, args.work_dir, codenameone_urls, javase_urls)
    except VerificationError as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Verification command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
