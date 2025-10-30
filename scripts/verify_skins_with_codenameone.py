#!/usr/bin/env python3
"""Validate generated Codename One skin archives."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import List

REQUIRED_PNG_ENTRIES = (
    "skin.png",
    "skin_l.png",
    "skin_map.png",
    "skin_map_l.png",
)
REQUIRED_PROPERTIES = (
    "touch",
    "platformName",
    "tablet",
    "systemFontFamily",
    "proportionalFontFamily",
    "monospaceFontFamily",
    "smallFontSize",
    "mediumFontSize",
    "largeFontSize",
    "overrideNames",
)
KNOWN_THEME_FILES = {
    "iOS7Theme.res",
    "iPhoneTheme.res",
    "android_holo_light.res",
    "androidTheme.res",
    "winTheme.res",
}
KNOWN_PLATFORMS = {"ios", "and", "win", "rim", "se"}


@dataclass
class PngInfo:
    width: int
    height: int


class VerificationError(RuntimeError):
    """Raised when a verification step fails."""


def _load_report(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    generated = data.get("generated", [])
    if not isinstance(generated, list):
        raise VerificationError("Report file is malformed: 'generated' should be a list")
    return [entry for entry in generated if isinstance(entry, dict)]


def _read_zip_entry(zip_file: zipfile.ZipFile, name: str) -> bytes:
    try:
        with zip_file.open(name) as fh:
            return fh.read()
    except KeyError as exc:
        raise VerificationError(f"Skin archive missing required entry: {name}") from exc


def _parse_png_info(data: bytes, entry_name: str) -> PngInfo:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise VerificationError(f"{entry_name} is not a valid PNG file")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise VerificationError(f"{entry_name} has invalid dimensions {width}x{height}")
    return PngInfo(width=width, height=height)


def _load_properties(data: bytes) -> dict[str, str]:
    parser = ConfigParser()
    parser.optionxform = str  # preserve key case
    try:
        parser.read_string("[DEFAULT]\n" + data.decode("utf-8"))
    except Exception as exc:
        raise VerificationError(f"Unable to parse skin.properties: {exc}") from exc
    return dict(parser["DEFAULT"])


def _validate_override_names(raw_value: str) -> None:
    parts = [part.strip() for part in raw_value.split(",") if part.strip()]
    if len(parts) != 3:
        raise VerificationError(
            "skin.properties overrideNames must contain three comma-separated values (e.g. phone,ios,iphone)"
        )


def _ensure_bool(name: str, value: str) -> None:
    if value.lower() not in {"true", "false"}:
        raise VerificationError(f"skin.properties {name} must be 'true' or 'false', found '{value}'")


def _ensure_int(name: str, value: str, minimum: int = 1) -> None:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise VerificationError(f"skin.properties {name} must be an integer, found '{value}'") from exc
    if parsed < minimum:
        raise VerificationError(f"skin.properties {name} must be >= {minimum}, found {parsed}")


def _ensure_float(name: str, value: str, minimum: float = 0.0) -> None:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise VerificationError(f"skin.properties {name} must be a number, found '{value}'") from exc
    if parsed <= minimum:
        raise VerificationError(f"skin.properties {name} must be greater than {minimum}, found {parsed}")


def _ensure_non_empty(name: str, value: str) -> None:
    if not value.strip():
        raise VerificationError(f"skin.properties {name} must not be empty")


def _validate_properties(props: dict[str, str]) -> None:
    missing = [key for key in REQUIRED_PROPERTIES if key not in props]
    if missing:
        raise VerificationError("skin.properties missing required keys: " + ", ".join(sorted(missing)))

    _ensure_bool("touch", props["touch"])
    _ensure_bool("tablet", props["tablet"])
    _ensure_non_empty("systemFontFamily", props["systemFontFamily"])
    _ensure_non_empty("proportionalFontFamily", props["proportionalFontFamily"])
    _ensure_non_empty("monospaceFontFamily", props["monospaceFontFamily"])
    _ensure_int("smallFontSize", props["smallFontSize"])
    _ensure_int("mediumFontSize", props["mediumFontSize"])
    _ensure_int("largeFontSize", props["largeFontSize"])
    pixel_ratio = props.get("pixelRatio")
    if pixel_ratio is not None:
        _ensure_float("pixelRatio", pixel_ratio, minimum=0.0)
    _validate_override_names(props["overrideNames"])

    platform = props["platformName"].strip()
    if platform not in KNOWN_PLATFORMS:
        raise VerificationError(
            "skin.properties platformName must be one of " + ", ".join(sorted(KNOWN_PLATFORMS)) + f"; found '{platform}'"
        )


def verify_skins(report_file: Path, _unused_work_dir: Path) -> None:
    generated = _load_report(report_file)
    if not generated:
        print("No generated skins to verify.")
        return

    for entry in generated:
        skin_path = Path(entry["archive"]).resolve()
        if not skin_path.is_file():
            raise VerificationError(f"Skin archive not found: {skin_path}")
        print(f"Verifying skin {entry.get('skin')} at {skin_path}")
        _validate_skin_archive(skin_path)


def _validate_skin_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            missing = [name for name in REQUIRED_PNG_ENTRIES if name not in names]
            if missing:
                raise VerificationError(f"Skin archive missing required PNG assets: {', '.join(sorted(missing))}")

            pngs: dict[str, PngInfo] = {}
            for entry in REQUIRED_PNG_ENTRIES:
                data = _read_zip_entry(zf, entry)
                pngs[entry] = _parse_png_info(data, entry)

            if pngs["skin.png"] != pngs["skin_map.png"]:
                raise VerificationError("skin_map.png dimensions must match skin.png")
            if pngs["skin_l.png"] != pngs["skin_map_l.png"]:
                raise VerificationError("skin_map_l.png dimensions must match skin_l.png")

            theme_present = any(name in names for name in KNOWN_THEME_FILES)
            if not theme_present:
                raise VerificationError(
                    "Skin archive is missing a supported theme resource (expected one of: "
                    + ", ".join(sorted(KNOWN_THEME_FILES))
                    + ")"
                )

            try:
                props_data = _read_zip_entry(zf, "skin.properties")
            except VerificationError:
                raise
            else:
                props = _load_properties(props_data)
                _validate_properties(props)
    except zipfile.BadZipFile as exc:
        raise VerificationError(f"{path} is not a valid Codename One skin archive: {exc}") from exc


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codename One skin verification")
    parser.add_argument("--report-file", type=Path, required=True, help="Path to the JSON report emitted by the generator")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("tmp") / "codenameone",
        help="Optional workspace retained for backwards compatibility (unused)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        verify_skins(args.report_file, args.work_dir)
    except VerificationError as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
