#!/usr/bin/env python3
"""Generate Codename One skin archives from Android emulator skins."""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile
import subprocess

try:
    from PIL import Image, ImageDraw
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "Pillow is required to generate Codename One skins. Install it with 'pip install Pillow'."
    ) from exc

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "generated_skins"
DEFAULT_METADATA_PATH = REPO_ROOT / ".github" / "skin-generation-log.json"
ISO_8601_Z_SUFFIX = "%Y-%m-%dT%H:%M:%SZ"

EXCLUDED_TOP_LEVEL = {".git", "OTA", "tmp", ".github"}

ANDROID_THEME_TEMPLATE = REPO_ROOT / "android" / "androidTheme.res"
DEFAULT_ANDROID_FONTS: Dict[str, Path] = {
    "DroidSans.ttf": REPO_ROOT / "Phones" / "GooglePixel" / "DroidSans.ttf",
    "DroidSans-Bold.ttf": REPO_ROOT / "Phones" / "GooglePixel" / "DroidSans-Bold.ttf",
    "DroidSansMono.ttf": REPO_ROOT / "Phones" / "GooglePixel" / "DroidSansMono.ttf",
    "DroidSerif.ttf": REPO_ROOT / "Phones" / "GooglePixel" / "DroidSerif.ttf",
    "DroidSerif-Bold.ttf": REPO_ROOT / "Phones" / "GooglePixel" / "DroidSerif-Bold.ttf",
    "DroidSerif-BoldItalic.ttf": REPO_ROOT / "Phones" / "GooglePixel" / "DroidSerif-BoldItalic.ttf",
    "DroidSerif-Italic.ttf": REPO_ROOT / "Phones" / "GooglePixel" / "DroidSerif-Italic.ttf",
}


@dataclasses.dataclass(frozen=True)
class AndroidSkinSource:
    """Description of a remote Android emulator skin source."""

    name: str
    slug: str
    url: str
    metadata_prefix: str
    allowed_roots: Tuple[str, ...] = ()
    subdirectory: Optional[str] = None
    alternate_urls: Tuple[str, ...] = ()


ANDROID_SKIN_SOURCES: Tuple[AndroidSkinSource, ...] = (
    AndroidSkinSource(
        name="Android emulator community skins",
        slug="Android",
        url="https://github.com/larskristianhaga/Android-emulator-skins",
        metadata_prefix="",
        allowed_roots=("Phones", "Tablets", "phones", "tablets"),
    ),
    AndroidSkinSource(
        name="Google device art resources",
        slug="Google",
        url="https://github.com/google/device-art-generator",
        metadata_prefix="google/",
        alternate_urls=(
            "https://github.com/googlesamples/device-art-generator",
            "https://github.com/googlearchive/device-art-generator",
        ),
    ),
    AndroidSkinSource(
        name="Samsung emulator skins",
        slug="Samsung",
        url="https://github.com/HiDeoo/avd-samsung-skins",
        metadata_prefix="samsung/",
        alternate_urls=(
            "https://github.com/HiDeoo/android-emulator-samsung-skins",
            "https://github.com/HiDeoo/avd-skins",
        ),
    ),
)


def _github_token() -> Optional[str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    return None


def _github_headers(url: Optional[str] = None) -> Dict[str, str]:
    headers: Dict[str, str] = {"User-Agent": "codenameone-skin-generator/1.0"}
    token = _github_token()
    if not token:
        return headers
    if url is None:
        headers["Authorization"] = f"Bearer {token}"
        return headers
    host = urlparse(url).netloc.lower()
    if "github.com" in host or "githubusercontent.com" in host or host.startswith("api.github"):
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _authenticated_git_url(url: str) -> str:
    token = _github_token()
    if not token:
        return url
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "github.com" not in host:
        return url
    safe_netloc = f"{token}:x-oauth-basic@{parsed.netloc}"
    return urlunparse(parsed._replace(netloc=safe_netloc))


def _sanitize_url(url: str) -> str:
    token = _github_token()
    if not token:
        return url
    sanitized = url.replace(token, "***")
    return sanitized.replace(f"{token}:x-oauth-basic", "***:x-oauth-basic")


@dataclasses.dataclass(frozen=True)
class SkinGeneration:
    """Description of a generated skin archive."""

    name: str
    source_dir: Path
    source_relative: str
    archive_path: Path


@dataclasses.dataclass(frozen=True)
class OrientationAssets:
    """Assets required to render a specific device orientation."""

    image_bytes: bytes
    width: int
    height: int
    screen_x: int
    screen_y: int
    screen_width: int
    screen_height: int

    def rotate_clockwise(self) -> "OrientationAssets":
        """Return a copy rotated 90 degrees clockwise."""

        with Image.open(io.BytesIO(self.image_bytes)) as img:
            rotated = img.rotate(-90, expand=True)
            buffer = io.BytesIO()
            rotated.save(buffer, format="PNG")
            buffer.seek(0)
            width, height = rotated.size

        new_x = self.height - (self.screen_y + self.screen_height)
        new_y = self.screen_x
        return OrientationAssets(
            image_bytes=buffer.getvalue(),
            width=width,
            height=height,
            screen_x=new_x,
            screen_y=new_y,
            screen_width=self.screen_height,
            screen_height=self.screen_width,
        )


@dataclasses.dataclass(frozen=True)
class ResolvedSource:
    """A resolved Android skin source on disk with cleanup support."""

    spec: AndroidSkinSource
    root: Path
    cleanup: Callable[[], None]


def _load_metadata(path: Path) -> Dict[str, Dict[str, str]]:
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            try:
                raw = json.load(fh)
            except json.JSONDecodeError:
                return {}
            if isinstance(raw, dict):
                return {str(k): dict(v) for k, v in raw.get("skins", {}).items()}
    return {}


def _save_metadata(path: Path, records: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": _current_utc_isoformat(), "skins": records}
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _current_utc_isoformat() -> str:
    return (
        _dt.datetime.now(tz=_dt.timezone.utc)
        .astimezone(_dt.timezone.utc)
        .replace(microsecond=0)
        .strftime(ISO_8601_Z_SUFFIX)
    )


def _directory_fingerprint(directory: Path) -> str:
    sha = hashlib.sha256()
    for entry in sorted(directory.rglob("*")):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            sha.update(entry.name.encode("utf-8"))
            continue
        sha.update(entry.relative_to(directory).as_posix().encode("utf-8"))
        sha.update(entry.read_bytes())
    return sha.hexdigest()


def _isoformat_from_timestamp(timestamp: float) -> str:
    return (
        _dt.datetime.fromtimestamp(timestamp, tz=_dt.timezone.utc)
        .replace(microsecond=0)
        .strftime(ISO_8601_Z_SUFFIX)
    )


def _parse_ini_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _parse_layout_file(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    tokens = re.findall(r"\w+|\{|\}|=|[^\s{}=]+", text)
    stack: List[Dict[str, object]] = [{}]
    key_stack: List[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "}":
            if len(stack) > 1:
                stack.pop()
                key_stack.pop()
            i += 1
            continue
        if token == "{":
            i += 1
            continue
        if i + 1 < len(tokens) and tokens[i + 1] == "{":
            key = token
            parent = stack[-1]
            container: Dict[str, object] = {}
            existing = parent.get(key)
            if existing is None:
                parent[key] = container
            elif isinstance(existing, list):
                existing.append(container)
            else:
                parent[key] = [existing, container]
            stack.append(container)
            key_stack.append(key)
            i += 2
            continue
        if i + 1 < len(tokens) and tokens[i + 1] == "=":
            key = token
            value = tokens[i + 2]
            parent = stack[-1]
            if key not in parent:
                parent[key] = value
            i += 3
            continue
        i += 1
    return stack[0]


def _locate_layout_file(skin_dir: Path) -> Optional[Path]:
    candidates = [
        skin_dir / "layout",
        skin_dir / "layout.ini",
        skin_dir / "skin.layout",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    nested = skin_dir / "layout"
    if nested.is_dir():
        for name in ("layout", "layout.ini"):
            candidate = nested / name
            if candidate.is_file():
                return candidate
    return None


def _ensure_iterable(value: object) -> Iterable[Dict[str, object]]:
    if isinstance(value, list):
        return (item for item in value if isinstance(item, dict))
    if isinstance(value, dict):
        return (value,)
    return ()


def _normalise_orientation_names() -> Dict[str, Tuple[str, ...]]:
    return {
        "portrait": ("portrait", "vertical", "default", "upright"),
        "landscape": ("landscape", "horizontal", "sideways"),
    }


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _resolve_image_file(base_dir: Path, part: Dict[str, object]) -> Optional[Path]:
    candidates: List[Tuple[Optional[str], Optional[str], str]] = []
    nodes: List[Dict[str, object]] = []
    for key in ("background", "image", "images"):
        node = part.get(key)
        if isinstance(node, dict):
            nodes.append(node)
    nodes.append(part)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        folder = node.get("folder") if isinstance(node.get("folder"), str) else None
        prefix = node.get("prefix") if isinstance(node.get("prefix"), str) else ""
        image_node = node.get("image") if isinstance(node.get("image"), dict) else node
        for key in ("file", "filename", "src"):
            candidate = image_node.get(key) if isinstance(image_node, dict) else None
            if isinstance(candidate, str):
                candidates.append((folder, prefix, candidate))
    for folder, prefix, raw_path in candidates:
        parts = [part for part in re.split(r"[\\/]+", raw_path) if part]
        if not parts:
            continue
        filename = parts[-1]
        search_roots: List[Path] = [base_dir]
        if folder:
            search_roots.append(base_dir / folder)
        for root in search_roots:
            candidate_path = root / f"{prefix}{filename}"
            if candidate_path.exists():
                return candidate_path
        matches = list(base_dir.rglob(filename))
        if matches:
            return matches[0]
    return None


def _extract_orientation(layout: Dict[str, object], orientation: str, base_dir: Path) -> Optional[OrientationAssets]:
    orientation_names = _normalise_orientation_names()[orientation]
    parts_container = layout.get("parts")
    for candidate in _ensure_iterable(parts_container):
        for name in orientation_names:
            part = candidate.get(name) if isinstance(candidate, dict) else None
            if isinstance(part, dict):
                assets = _orientation_from_part(part, base_dir)
                if assets:
                    return assets
    for name in orientation_names:
        part = layout.get(name)
        if isinstance(part, dict):
            assets = _orientation_from_part(part, base_dir)
            if assets:
                return assets
    return None


def _orientation_from_part(part: Dict[str, object], base_dir: Path) -> Optional[OrientationAssets]:
    display = part.get("display")
    if not isinstance(display, dict):
        display = part.get("screen") if isinstance(part.get("screen"), dict) else None
    if not isinstance(display, dict):
        return None
    x = _parse_int(str(display.get("x"))) if display.get("x") is not None else _parse_int(display.get("xOffset"))
    y = _parse_int(str(display.get("y"))) if display.get("y") is not None else _parse_int(display.get("yOffset"))
    width = _parse_int(display.get("width"))
    height = _parse_int(display.get("height"))
    if None in {x, y, width, height}:
        return None
    if width <= 0 or height <= 0:
        return None
    image_path = _resolve_image_file(base_dir, part)
    if image_path is None or not image_path.exists():
        return None
    with Image.open(image_path) as img:
        rgba = img.convert("RGBA")
        width_px, height_px = rgba.size
        buffer = io.BytesIO()
        rgba.save(buffer, format="PNG")
        buffer.seek(0)
    return OrientationAssets(
        image_bytes=buffer.getvalue(),
        width=width_px,
        height=height_px,
        screen_x=x or 0,
        screen_y=y or 0,
        screen_width=width or width_px,
        screen_height=height or height_px,
    )


def _render_overlay(width: int, height: int, rect: Tuple[int, int, int, int]) -> bytes:
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y, w, h = rect
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    draw.rectangle([x, y, x + w - 1, y + h - 1], fill=(0, 0, 0, 255))
    buffer = io.BytesIO()
    overlay.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def _derive_pixel_ratio(hardware: Dict[str, str]) -> Optional[float]:
    density_keys = (
        "hw.lcd.density",
        "hw.display.density",
        "lcd.density",
        "density",
        "ro.sf.lcd_density",
        "config_lcdDensity",
        "hw.gpu.density",
    )
    for key in density_keys:
        if key in hardware:
            try:
                density = float(hardware[key])
                if density > 0:
                    return density / 25.4
            except ValueError:
                continue
    width = _parse_int(hardware.get("hw.lcd.width"))
    height = _parse_int(hardware.get("hw.lcd.height"))
    diag_mm = hardware.get("hw.device.display_diagonal") or hardware.get("device.display_diagonal")
    if width and height and diag_mm:
        try:
            diag_inches = float(diag_mm)
        except ValueError:
            diag_inches = None
        if diag_inches:
            diag_pixels = math.hypot(width, height)
            if diag_pixels > 0 and diag_inches > 0:
                dpi = diag_pixels / diag_inches
                return dpi / 25.4
    return None


def _determine_override_names(tablet: bool) -> str:
    if tablet:
        return "tablet,android,android-tablet"
    return "phone,android,android-phone"


def _is_tablet(width: int, height: int) -> bool:
    longest = max(width, height)
    return longest >= 1200


def _normalise_name_component(component: str) -> str:
    tokens = re.split(r"[^A-Za-z0-9]+", component)
    return "".join(token.capitalize() for token in tokens if token)


def _derive_skin_name(relative_parts: Sequence[str], used: set[str], prefix: Optional[str] = None) -> str:
    filtered = [part for part in relative_parts if part.lower() not in {"phones", "phone", "tablets", "tablet", "skins", "skin"}]
    if not filtered:
        filtered = list(relative_parts)
    components = list(filtered)
    if prefix and prefix.lower() not in {component.lower() for component in components}:
        components.insert(0, prefix)
    name = "".join(_normalise_name_component(part) for part in components)
    if not name:
        name = "Skin"
    base = name
    counter = 1
    while name in used:
        counter += 1
        name = f"{base}{counter}"
    used.add(name)
    return name


def _relative_to_repo(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _build_skin_properties(
    *,
    device_name: str,
    source: AndroidSkinSource,
    relative_source: str,
    pixel_ratio: Optional[float],
    tablet: bool,
    hardware: Dict[str, str],
    screen_width: int,
    screen_height: int,
) -> str:
    lines = [
        f"#Generated by Codename One skin pipeline from {source.name}",
        f"#Source: {source.url}::{relative_source}",
        f"#Resolution: {screen_width}x{screen_height}",
        "touch=true",
        f"platformName=and",
        f"tablet={'true' if tablet else 'false'}",
        "systemFontFamily=DroidSans",
        "proportionalFontFamily=DroidSans",
        "monospaceFontFamily=DroidSansMono",
        "smallFontSize=11",
        "mediumFontSize=14",
        "largeFontSize=20",
        f"overrideNames={_determine_override_names(tablet)}",
    ]
    diagonal = hardware.get("hw.device.display_diagonal") or hardware.get("device.display_diagonal")
    if diagonal:
        try:
            diagonal_value = float(diagonal)
            lines.insert(2, f"#Diagonal: {diagonal_value}\"")
        except ValueError:
            pass
    lines.insert(2, f"#Device: {device_name}")
    dpi = hardware.get("hw.lcd.density") or hardware.get("hw.display.density")
    if dpi:
        lines.append(f"dpi={dpi}")
    if pixel_ratio:
        formatted = f"{pixel_ratio:.12f}".rstrip("0").rstrip(".")
        lines.append(f"pixelRatio={formatted}")
        ppi_value = pixel_ratio * 25.4
        lines.append(f"ppi={ppi_value:.2f}")
    return "\n".join(lines) + "\n"


def _write_android_resources(zip_file: ZipFile) -> None:
    if ANDROID_THEME_TEMPLATE.exists():
        zip_file.write(ANDROID_THEME_TEMPLATE, arcname="androidTheme.res")
    for name, path in DEFAULT_ANDROID_FONTS.items():
        if path.exists():
            zip_file.write(path, arcname=name)


def _convert_skin_directory(
    *,
    skin_dir: Path,
    target_zip: Path,
    source: AndroidSkinSource,
    relative_source: str,
    device_name: str,
    hardware: Dict[str, str],
) -> None:
    layout_path = _locate_layout_file(skin_dir)
    if layout_path is None:
        raise RuntimeError("Missing layout file")
    layout = _parse_layout_file(layout_path)
    portrait = _extract_orientation(layout, "portrait", skin_dir)
    landscape = _extract_orientation(layout, "landscape", skin_dir)
    if portrait is None:
        raise RuntimeError("Unable to resolve portrait orientation assets")
    if landscape is None:
        landscape = portrait.rotate_clockwise()

    portrait_overlay = _render_overlay(
        portrait.width,
        portrait.height,
        (portrait.screen_x, portrait.screen_y, portrait.screen_width, portrait.screen_height),
    )
    landscape_overlay = _render_overlay(
        landscape.width,
        landscape.height,
        (landscape.screen_x, landscape.screen_y, landscape.screen_width, landscape.screen_height),
    )

    pixel_ratio = _derive_pixel_ratio(hardware)
    if pixel_ratio is None:
        raise RuntimeError("Unable to determine pixel density for skin")

    tablet = _is_tablet(portrait.screen_width, portrait.screen_height)

    properties = _build_skin_properties(
        device_name=device_name,
        source=source,
        relative_source=relative,
        pixel_ratio=pixel_ratio,
        tablet=tablet,
        hardware=hardware,
        screen_width=portrait.screen_width,
        screen_height=portrait.screen_height,
    )

    target_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target_zip, "w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("skin.png", portrait.image_bytes)
        zf.writestr("skin_l.png", landscape.image_bytes)
        zf.writestr("skin_map.png", portrait_overlay)
        zf.writestr("skin_map_l.png", landscape_overlay)
        zf.writestr("skin.properties", properties)
        _write_android_resources(zf)


def _github_repo_from_url(url: str) -> Optional[Tuple[str, str]]:
    parsed = urlparse(url)
    if parsed.netloc != "github.com":
        return None
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _branch_candidates(base_url: str) -> List[str]:
    owner_repo = _github_repo_from_url(base_url)
    candidates: List[str] = []
    if owner_repo:
        owner, repo = owner_repo
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            request = Request(api_url, headers=_github_headers(api_url))
            with urlopen(request) as response:  # type: ignore[arg-type]
                payload = json.load(response)
            default_branch = payload.get("default_branch")
            if isinstance(default_branch, str) and default_branch:
                candidates.append(default_branch)
        except Exception:  # pragma: no cover - network dependent
            pass

    for branch in ("main", "master", "dev", "develop"):
        if branch not in candidates:
            candidates.append(branch)
    return candidates


def _download_android_skin_repo(source: AndroidSkinSource) -> Tuple[Path, Path]:
    parsed = urlparse(source.url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme for Android skin source: {source.url}")

    tmp_root = Path(tempfile.mkdtemp(prefix="android-skins-"))
    archive_path = tmp_root / "repo.zip"
    errors: List[str] = []

    base_urls: Tuple[str, ...] = (source.url, *source.alternate_urls)

    for base_url in base_urls:
        base = base_url.rstrip("/")
        branch_candidates = _branch_candidates(base)
        archive_candidates: List[str]
        if base.endswith(".zip"):
            archive_candidates = [base]
        else:
            archive_candidates = [
                f"{base}/archive/refs/heads/{branch}.zip" for branch in branch_candidates
            ]

        for candidate in archive_candidates:
            try:
                request = Request(candidate, headers=_github_headers(candidate))
                with urlopen(request) as response, archive_path.open("wb") as fh:  # type: ignore[arg-type]
                    shutil.copyfileobj(response, fh)
                with ZipFile(archive_path) as zf:
                    zf.extractall(tmp_root)
                    top_level: List[Path] = []
                    for name in zf.namelist():
                        if not name:
                            continue
                        root = Path(name.split("/", 1)[0])
                        if root not in top_level:
                            top_level.append(root)
                    if source.subdirectory:
                        candidate_dir = tmp_root / source.subdirectory
                        if candidate_dir.exists():
                            repo_root = candidate_dir
                        elif len(top_level) == 1:
                            candidate_dir = tmp_root / top_level[0] / source.subdirectory
                            repo_root = (
                                candidate_dir if candidate_dir.exists() else tmp_root / top_level[0]
                            )
                        elif top_level:
                            repo_root = tmp_root / top_level[0]
                        else:
                            repo_root = tmp_root
                    elif len(top_level) == 1:
                        repo_root = tmp_root / top_level[0]
                    else:
                        repo_root = tmp_root
                return repo_root, tmp_root
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(f"{_sanitize_url(candidate)}: {exc}")

    # Zip downloads failed, try shallow git clones as fallbacks
    for attempt_index, base_url in enumerate(base_urls):
        branch_candidates = _branch_candidates(base_url)
        for branch in branch_candidates:
            clone_dir = tmp_root / f"repo-{attempt_index}-{branch}"
            try:
                clone_url = _authenticated_git_url(base_url)
                env = os.environ.copy()
                env.setdefault("GIT_TERMINAL_PROMPT", "0")
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--single-branch",
                        "--filter=blob:none",
                        "--branch",
                        branch,
                        clone_url,
                        str(clone_dir),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
            except subprocess.CalledProcessError as exc:  # pragma: no cover - network dependent
                stderr = exc.stderr.strip()
                stdout = exc.stdout.strip()
                details = stderr or stdout or str(exc)
                errors.append(f"git clone ({_sanitize_url(base_url)}@{branch}): {details}")
                continue
            except FileNotFoundError as exc:  # pragma: no cover - git missing
                errors.append(f"git clone unavailable: {exc}")
                break
            else:
                repo_root = clone_dir
                if source.subdirectory:
                    candidate_dir = clone_dir / source.subdirectory
                    if candidate_dir.exists():
                        repo_root = candidate_dir
                return repo_root, tmp_root

    shutil.rmtree(tmp_root, ignore_errors=True)
    raise RuntimeError(
        f"Failed to download Android emulator skins from {source.url}. Attempts: " + "; ".join(errors)
    )


def _iter_android_skin_directories(root: Path, allowed_roots: Tuple[str, ...]) -> Iterator[Path]:
    seen: set[Path] = set()
    for marker in ("hardware.ini", "skin.ini", "layout"):
        for path in root.rglob(marker):
            parent = path.parent
            try:
                relative_parts = parent.relative_to(root).parts
            except ValueError:
                continue
            if not relative_parts:
                continue
            if relative_parts[0] in EXCLUDED_TOP_LEVEL:
                continue
            if allowed_roots and relative_parts[0] not in allowed_roots:
                continue
            if parent not in seen:
                seen.add(parent)
                yield parent


def _resolve_sources() -> Tuple[List[ResolvedSource], List[str]]:
    resolved: List[ResolvedSource] = []
    errors: List[str] = []
    for spec in ANDROID_SKIN_SOURCES:
        try:
            root, tmp_root = _download_android_skin_repo(spec)
            cleanup = lambda tmp=tmp_root: shutil.rmtree(tmp, ignore_errors=True)
            resolved.append(ResolvedSource(spec=spec, root=root, cleanup=cleanup))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(f"{spec.name}: {exc}")
    return resolved, errors


def process_skins(
    *,
    output_dir: Path,
    metadata_path: Path,
    dry_run: bool = False,
    force: bool = False,
) -> Tuple[List[SkinGeneration], List[str], List[str]]:
    output_dir = output_dir.resolve()
    metadata_path = metadata_path.resolve()
    metadata = _load_metadata(metadata_path)

    resolved_sources, resolve_errors = _resolve_sources()
    generated: List[SkinGeneration] = []
    skipped: List[str] = []
    errors: List[str] = resolve_errors
    used_names: set[str] = set()

    try:
        for resolved_source in resolved_sources:
            spec = resolved_source.spec
            for skin_dir in sorted(
                _iter_android_skin_directories(resolved_source.root, spec.allowed_roots),
                key=lambda p: p.relative_to(resolved_source.root).as_posix(),
            ):
                relative = skin_dir.relative_to(resolved_source.root).as_posix()
                metadata_key = f"{spec.metadata_prefix}{relative}" if spec.metadata_prefix else relative
                relative_parts = skin_dir.relative_to(resolved_source.root).parts
                prefix = spec.slug if spec.slug else None
                skin_name = _derive_skin_name(relative_parts, used_names, prefix)
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
                            "source": relative,
                            "fingerprint": fingerprint,
                            "archive": _relative_to_repo(existing_archive),
                            "source_repository": spec.url,
                            "skin": skin_name,
                        }
                    skipped.append(skin_name)
                    continue

                if dry_run:
                    generated.append(
                        SkinGeneration(
                            name=skin_name,
                            source_dir=skin_dir,
                            source_relative=f"{spec.name}:{relative}",
                            archive_path=archive_path,
                        )
                    )
                    continue

                hardware = _parse_ini_file(skin_dir / "hardware.ini")
                try:
                    _convert_skin_directory(
                        skin_dir=skin_dir,
                        target_zip=archive_path,
                        source=spec,
                        relative_source=relative,
                        device_name=skin_name,
                        hardware=hardware,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(f"{spec.name}::{relative}: {exc}")
                    continue

                metadata[metadata_key] = {
                    "generated_at": _current_utc_isoformat(),
                    "source": relative,
                    "fingerprint": fingerprint,
                    "archive": _relative_to_repo(archive_path),
                    "source_repository": spec.url,
                    "skin": skin_name,
                }
                generated.append(
                    SkinGeneration(
                        name=skin_name,
                        source_dir=skin_dir,
                        source_relative=f"{spec.name}:{relative}",
                        archive_path=archive_path,
                    )
                )
    finally:
        for resolved in resolved_sources:
            try:
                resolved.cleanup()
            except Exception:  # pylint: disable=broad-except
                pass

    if not dry_run:
        ordered = dict(sorted(metadata.items()))
        _save_metadata(metadata_path, ordered)

    return generated, skipped, errors


def _find_existing_archive(name: str) -> Optional[Path]:
    ota_dir = REPO_ROOT / "OTA"
    candidate = ota_dir / f"{name}.skin"
    if candidate.exists():
        return candidate
    return None


def _write_report(report_path: Path, generated: List[SkinGeneration], skipped: List[str], errors: List[str]) -> None:
    report_payload = {
        "generated": [
            {
                "skin": entry.name,
                "archive": entry.archive_path.as_posix(),
                "source": entry.source_relative,
            }
            for entry in generated
        ],
        "skipped": sorted(skipped),
        "errors": errors,
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

    generated, skipped, errors = process_skins(
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

    if errors:
        print("Encountered issues:\n - " + "\n - ".join(errors))

    if args.report_file:
        _write_report(args.report_file, generated, skipped, errors)

    if errors and not args.dry_run:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
