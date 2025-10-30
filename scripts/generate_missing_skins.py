#!/usr/bin/env python3
"""Generate Codename One skin archives for directories that are missing them.

This script inspects the repository for directories that contain ``skin.properties``
files (i.e. Codename One skin definitions). For each such directory it verifies that
an OTA ``.skin`` archive has not yet been captured in the metadata ledger. Missing
entries are regenerated with maximum compression and recorded in the ledger so that
future runs can skip work that has already been performed.

The resulting archives are written to a configurable output directory (``tmp/`` by
default) so that the Git repository does not need to track large binary assets.
An optional JSON report summarises the work, which can be consumed by CI pipelines
to run additional validation steps.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "generated_skins"
DEFAULT_METADATA_PATH = REPO_ROOT / ".github" / "skin-generation-log.json"

# Roots that contain upstream Android emulator skin assets that still need
# Codename One archives.  The historical Codename One skins that ship with the
# simulator live at the repository root and should be ignored – those are
# already committed and would just be regenerated unnecessarily.  Only the
# Android emulator dumps (phones/tablets) are eligible for conversion.
EMULATOR_SKIN_ROOTS = ("Phones", "Tablets")

# Directories that should never be considered as skin sources.
EXCLUDED_TOP_LEVEL = {".git", "OTA", "tmp", ".github"}

ISO_8601_Z_SUFFIX = "%Y-%m-%dT%H:%M:%SZ"


@dataclasses.dataclass(frozen=True)
class SkinGeneration:
    """Description of a generated skin archive."""

    name: str
    source_dir: Path
    archive_path: Path


def _load_metadata(path: Path) -> Dict[str, Dict[str, str]]:
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            try:
                raw = json.load(fh)
                if isinstance(raw, dict):
                    return {str(k): dict(v) for k, v in raw.get("skins", {}).items()}
            except json.JSONDecodeError:
                pass
    return {}


def _save_metadata(path: Path, records: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": _dt.datetime.utcnow().strftime(ISO_8601_Z_SUFFIX), "skins": records}
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _iter_skin_directories() -> Iterable[Path]:
    for root_name in EMULATOR_SKIN_ROOTS:
        candidate_root = REPO_ROOT / root_name
        if not candidate_root.exists():
            continue
        for properties_file in candidate_root.rglob("skin.properties"):
            try:
                relative_parts = properties_file.relative_to(REPO_ROOT).parts
            except ValueError:
                continue
            if not relative_parts:
                continue
            if relative_parts[0] in EXCLUDED_TOP_LEVEL:
                continue
            yield properties_file.parent


def _directory_fingerprint(directory: Path) -> str:
    sha = hashlib.sha256()
    for item in sorted(directory.iterdir()):
        if item.name.startswith("."):
            # Ignore hidden files such as .DS_Store.
            continue
        if item.is_dir():
            # Current skin layout stores assets flat, but recurse defensively.
            sha.update(item.name.encode("utf-8"))
            sha.update(_directory_fingerprint(item).encode("utf-8"))
            continue
        sha.update(item.name.encode("utf-8"))
        sha.update(item.read_bytes())
    return sha.hexdigest()


def _find_existing_archive(name: str) -> Path | None:
    ota_dir = REPO_ROOT / "OTA"
    candidate = ota_dir / f"{name}.skin"
    if candidate.exists():
        return candidate
    return None


def _isoformat_from_timestamp(timestamp: float) -> str:
    return _dt.datetime.utcfromtimestamp(timestamp).replace(microsecond=0).strftime(ISO_8601_Z_SUFFIX)


MANUAL_PIXEL_RATIOS = {
    "BlackberryBold9790": 9.681166903317413,
    "Tablets/MicrosoftSurface3": 8.411901488396593,
    "Tablets/MicrosoftSurfacePro4": 10.525135276945004,
    "android": 6.299212598425197,
    "feature_phone": 7.158196134574087,
    "NokiaE71": 6.672894701721608,
    "lumia": 8.54195479926065,
    "nexus": 9.927136658600213,
}


def _parse_skin_properties(text: str) -> Tuple[Dict[str, str], List[str]]:
    props: Dict[str, str] = {}
    comments: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            comments.append(stripped)
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in props:
            props[key] = value
    return props, comments


def _derive_pixel_ratio(props: Dict[str, str], comments: List[str], source_hint: str) -> float | None:
    if "pixelRatio" in props:
        try:
            return float(props["pixelRatio"])
        except ValueError:
            return None

    def _parse_float(value: str) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed <= 0:
            return None
        return parsed

    ppi = _parse_float(props.get("ppi")) or _parse_float(props.get("dpi"))
    if ppi is None:
        for line in comments:
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:pp|dp)i", line, flags=re.IGNORECASE)
            if match:
                ppi = _parse_float(match.group(1))
                if ppi:
                    break
        if ppi is None:
            diag = None
            width = height = None
            for line in comments:
                if diag is None:
                    diag_match = re.search(r"(\d+(?:\.\d+)?)\"", line)
                    if diag_match:
                        diag = _parse_float(diag_match.group(1))
                if width is None or height is None:
                    res_match = re.search(r"(\d+)\s*[xX]\s*(\d+)", line)
                    if res_match:
                        width = int(res_match.group(1))
                        height = int(res_match.group(2))
                if diag and width and height:
                    break
            if diag and width and height:
                diag_pixels = math.hypot(width, height)
                if diag_pixels > 0 and diag > 0:
                    ppi = diag_pixels / diag

    if ppi is None:
        ratio = MANUAL_PIXEL_RATIOS.get(source_hint)
        return ratio

    return ppi / 25.4


def _ensure_trailing_newline(text: str) -> str:
    if text.endswith("\n"):
        return text
    if text.endswith("\r\n"):
        return text
    return text + "\n"


def _maybe_augment_skin_properties(text: str, source_hint: str) -> str:
    props, comments = _parse_skin_properties(text)
    ratio = _derive_pixel_ratio(props, comments, source_hint)
    if ratio is None or "pixelRatio" in props:
        return _ensure_trailing_newline(text)

    formatted = f"pixelRatio={ratio:.12f}".rstrip("0").rstrip(".")
    base = _ensure_trailing_newline(text)
    if not base.endswith(("\n", "\r\n")):
        base += "\n"
    return base + formatted + "\n"


def _zip_skin_directory(source_dir: Path, target_zip: Path, source_hint: str) -> None:
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target_zip, "w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        for entry in sorted(source_dir.rglob("*")):
            if entry.is_dir() or entry.name.startswith("."):
                continue
            arcname = entry.relative_to(source_dir).as_posix()
            if arcname == "skin.properties":
                original = entry.read_text(encoding="utf-8", errors="replace")
                updated = _maybe_augment_skin_properties(original, source_hint)
                zf.writestr(arcname, updated)
            else:
                zf.write(entry, arcname=arcname)


def _current_utc_isoformat() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).strftime(ISO_8601_Z_SUFFIX)


def process_skins(
    *,
    output_dir: Path,
    metadata_path: Path,
    dry_run: bool = False,
    force: bool = False,
) -> Tuple[List[SkinGeneration], List[str]]:
    output_dir = output_dir.resolve()
    metadata_path = metadata_path.resolve()
    metadata = _load_metadata(metadata_path)
    generated: List[SkinGeneration] = []
    skipped: List[str] = []

    for skin_dir in sorted(_iter_skin_directories(), key=lambda p: p.relative_to(REPO_ROOT).as_posix()):
        relative_source = skin_dir.relative_to(REPO_ROOT).as_posix()
        skin_name = skin_dir.name
        metadata_key = relative_source
        archive_path = output_dir / f"{skin_name}.skin"
        fingerprint = _directory_fingerprint(skin_dir)
        record = metadata.get(metadata_key)
        existing_archive = _find_existing_archive(skin_name)

        if not force and record and record.get("fingerprint") == fingerprint:
            skipped.append(skin_name)
            continue

        if not force and record is None and existing_archive is not None:
            if not dry_run:
                metadata[metadata_key] = {
                    "generated_at": _isoformat_from_timestamp(existing_archive.stat().st_mtime),
                    "source": relative_source,
                    "fingerprint": fingerprint,
                    "archive": _relative_to_repo(existing_archive),
                }
            skipped.append(skin_name)
            continue

        if dry_run:
            generated.append(SkinGeneration(skin_name, skin_dir, archive_path))
            continue

        source_hint = relative_source
        _zip_skin_directory(skin_dir, archive_path, source_hint)
        archive_entry = _relative_to_repo(archive_path)
        metadata[metadata_key] = {
            "generated_at": _current_utc_isoformat(),
            "source": relative_source,
            "fingerprint": fingerprint,
            "archive": archive_entry,
        }
        generated.append(SkinGeneration(skin_name, skin_dir, archive_path))

    if not dry_run:
        ordered = dict(sorted(metadata.items()))
        _save_metadata(metadata_path, ordered)

    return generated, skipped


def _relative_to_repo(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_report(report_path: Path, generated: List[SkinGeneration], skipped: List[str]) -> None:
    report_payload = {
        "generated": [
            {
                "skin": entry.name,
                "archive": entry.archive_path.as_posix(),
                "source": entry.source_dir.relative_to(REPO_ROOT).as_posix(),
            }
            for entry in generated
        ],
        "skipped": sorted(skipped),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report_payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Codename One skin archives when missing")
    parser.add_argument("--dry-run", action="store_true", help="Only report the work that would be performed")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where generated .skin archives should be written (default: tmp/generated_skins)",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA_PATH,
        help="Location of the metadata ledger tracking previously generated skins",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        help="Optional path for a JSON report describing generated and skipped skins",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate skins even if the metadata fingerprint matches",
    )
    args = parser.parse_args()

    generated, skipped = process_skins(
        output_dir=args.output_dir,
        metadata_path=args.metadata,
        dry_run=args.dry_run,
        force=args.force,
    )

    if generated:
        print("Generated/updated skins:\n - " + "\n - ".join(entry.name for entry in sorted(generated, key=lambda e: e.name)))
    else:
        print("No skins required regeneration.")

    if skipped:
        print("Skipped skins (up-to-date):\n - " + "\n - ".join(sorted(skipped)))

    if args.report_file:
        _write_report(args.report_file, generated, skipped)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
