#!/usr/bin/env python3
"""Validate generated Codename One skin archives."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REQUIRED_PNG_ENTRIES = (
    "skin.png",
    "skin_l.png",
    "skin_map.png",
    "skin_map_l.png",
)
ESSENTIAL_PROPERTIES = (
    "touch",
    "platformName",
    "overrideNames",
)
SIZE_PROPERTIES = ("smallFontSize", "mediumFontSize", "largeFontSize")
OPTIONAL_BOOL_PROPERTIES = ("tablet", "roundScreen", "rotateKeys")
KNOWN_PLATFORMS = {"ios", "and", "win", "rim", "se", "me"}
MANUAL_PIXEL_RATIOS: Dict[str, float] = {
    "BlackberryBold9790": 9.681166903317413,
    "Tablets/MicrosoftSurface3": 8.411901488396593,
    "Tablets/MicrosoftSurfacePro4": 10.525135276945004,
    "android": 6.299212598425197,
    "feature_phone": 7.158196134574087,
    "NokiaE71": 6.672894701721608,
    "lumia": 8.54195479926065,
    "nexus": 9.927136658600213,
}


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


def _parse_properties(data: bytes) -> Tuple[Dict[str, str], List[str], str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"Unable to decode skin.properties: {exc}") from exc

    props: Dict[str, str] = {}
    comments: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            comments.append(line)
            continue
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in props:
            props[key] = value
    return props, comments, text


def _validate_override_names(raw_value: str) -> None:
    parts = [part.strip() for part in raw_value.split(",") if part.strip()]
    if len(parts) < 2:
        raise VerificationError(
            "skin.properties overrideNames must contain at least two comma-separated values"
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


def _derive_pixel_ratio(props: Dict[str, str], comments: Iterable[str], source_hint: Optional[str]) -> Optional[float]:
    if "pixelRatio" in props:
        try:
            parsed = float(props["pixelRatio"])
        except ValueError:
            raise VerificationError(f"skin.properties pixelRatio is not a number: {props['pixelRatio']}")
        if parsed <= 0:
            raise VerificationError(f"skin.properties pixelRatio must be positive, found {parsed}")
        return parsed

    def _parse_float(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float(value)
        except ValueError:
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

    if ppi is None and source_hint:
        ratio = MANUAL_PIXEL_RATIOS.get(source_hint)
        if ratio is not None:
            return ratio

    if ppi is None:
        return None

    return ppi / 25.4


def _validate_properties(props: Dict[str, str], comments: List[str], source_hint: Optional[str]) -> None:
    missing = [key for key in ESSENTIAL_PROPERTIES if key not in props]
    if missing:
        raise VerificationError("skin.properties missing required keys: " + ", ".join(sorted(missing)))

    _ensure_bool("touch", props["touch"])
    for opt_bool in OPTIONAL_BOOL_PROPERTIES:
        if opt_bool in props:
            _ensure_bool(opt_bool, props[opt_bool])

    if "systemFontFamily" in props:
        _ensure_non_empty("systemFontFamily", props["systemFontFamily"])
    if "proportionalFontFamily" in props:
        _ensure_non_empty("proportionalFontFamily", props["proportionalFontFamily"])
    if "monospaceFontFamily" in props:
        _ensure_non_empty("monospaceFontFamily", props["monospaceFontFamily"])

    for size_key in SIZE_PROPERTIES:
        value = props.get(size_key)
        if value is not None:
            _ensure_int(size_key, value)

    if "nativeThemeAttribute" in props:
        _ensure_non_empty("nativeThemeAttribute", props["nativeThemeAttribute"])

    derived_ratio = _derive_pixel_ratio(props, comments, source_hint)
    if derived_ratio is None:
        raise VerificationError(
            "Unable to determine pixel ratio; provide pixelRatio, ppi, or include resolution/diagonal hints in comments"
        )

    existing_ratio = props.get("pixelRatio")
    if existing_ratio is not None:
        parsed_existing = float(existing_ratio)
        if abs(parsed_existing - derived_ratio) > 0.25:
            raise VerificationError(
                f"skin.properties pixelRatio {parsed_existing:.6f} disagrees with derived value {derived_ratio:.6f}"
            )
    else:
        print(f" Derived pixel ratio from metadata: {derived_ratio:.6f}")

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
        source_hint = entry.get("source")
        print(f"Verifying skin {entry.get('skin')} at {skin_path}")
        _validate_skin_archive(skin_path, source_hint)


def _validate_skin_archive(path: Path, source_hint: Optional[str]) -> None:
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

            try:
                props_data = _read_zip_entry(zf, "skin.properties")
            except VerificationError:
                raise
            else:
                props, comments, _ = _parse_properties(props_data)
                theme_present = any(name.lower().endswith(".res") for name in names)
                if not theme_present and "nativeThemeAttribute" not in props:
                    raise VerificationError(
                        "Skin archive must provide a theme resource (.res) or define nativeThemeAttribute"
                    )
                _validate_properties(props, comments, source_hint)
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
