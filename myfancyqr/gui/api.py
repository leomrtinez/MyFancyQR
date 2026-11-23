"""Python side of the GUI: the object exposed to JavaScript.

The same :class:`Api` instance backs both front ends:

* the pywebview window (``window.pywebview.api.<method>(...)``), where file
  dialogs and the clipboard are native;
* the browser dev server (``POST /api/<method>``), where dialogs are
  replaced by uploads/downloads.

Every public method takes and returns plain JSON-compatible values and
never raises: errors come back as ``{"ok": False, "error": "..."}`` so the
UI can show them inline.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from .. import __version__
from ..core import (
    BUILTIN_LOGOS,
    SUPPORTED_FORMATS,
    QRConfig,
    QRMatrix,
    analyse,
    build_matrix,
    decode_check,
    render,
    save,
    to_hex,
)

#: GUI defaults (the CLI keeps v1 defaults; the GUI follows ISO 18004).
DEFAULT_PARAMS: dict[str, Any] = {
    "data": "https://github.com/leomrtinez/MyFancyQR",
    "fill": "#1d1d1f",
    "back": "#ffffff",
    "boxSize": 25,
    "border": 4,
    "ecc": "auto",
    "logo": None,
    "logoScale": 25,
    "logoBackdrop": "circle",
    "invertLogo": "auto",
    "format": "png",
}

#: Formats offered in the format bar (``jpeg`` is an alias of ``jpg``).
GUI_FORMATS = [f for f in SUPPORTED_FORMATS if f != "jpeg"]

FILE_TYPES = {
    "png": "PNG image (*.png)",
    "svg": "SVG vector image (*.svg)",
    "pdf": "PDF document (*.pdf)",
    "jpg": "JPEG image (*.jpg;*.jpeg)",
    "webp": "WebP image (*.webp)",
    "tiff": "TIFF image (*.tif;*.tiff)",
    "bmp": "BMP image (*.bmp)",
    "eps": "EPS document (*.eps)",
}

#: Longest side of the preview image sent to the UI, in pixels.
PREVIEW_MAX = 760

_CALLABLE_FROM_JS = (
    "get_state", "render", "choose_logo", "upload_logo", "export",
    "copy_image", "reveal", "list_presets", "save_preset", "delete_preset",
)


def presets_file() -> Path:
    """Platform-appropriate location of the presets JSON file."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "MyFancyQR"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "MyFancyQR"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "myfancyqr"
    return base / "presets.json"


def config_from_params(params: dict[str, Any]) -> QRConfig:
    """Translate UI parameters (camelCase, percentages) into a QRConfig."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    ecc = str(p["ecc"]).upper()
    return QRConfig(
        data=str(p["data"]),
        fill_color=str(p["fill"]),
        back_color=str(p["back"]),
        box_size=int(p["boxSize"]),
        border=int(p["border"]),
        error_correction=None if ecc == "AUTO" else ecc,
        logo=p["logo"] or None,
        logo_scale=float(p["logoScale"]) / 100.0,
        logo_backdrop=str(p["logoBackdrop"]),
        invert_logo=str(p["invertLogo"]),
    )


def _png_data_url(img) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=False, compress_level=3)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _error(exc: BaseException) -> dict:
    msg = str(exc) or exc.__class__.__name__
    return {"ok": False, "error": msg[:1].upper() + msg[1:]}


class Api:
    """Methods callable from the web UI."""

    def __init__(self, browser_mode: bool = False, presets_path: Path | None = None):
        self._browser_mode = browser_mode
        # Private attributes: pywebview exposes every public attribute of the
        # js_api object to JavaScript, so nothing but the API stays public.
        self._window = None             # set by app.py once the window exists
        self._unified_titlebar = False  # set by app.py when the macOS titlebar is merged
        self._presets_path = presets_path or presets_file()
        self._matrix_cache: dict[tuple[str, str], QRMatrix] = {}
        self._lock = threading.Lock()
        self._upload_dir: Path | None = None

    # -- internals ----------------------------------------------------------
    def _matrix(self, cfg: QRConfig) -> QRMatrix:
        key = (cfg.data, cfg.ecc)
        with self._lock:
            m = self._matrix_cache.get(key)
        if m is None:
            m = build_matrix(cfg)
            with self._lock:
                if len(self._matrix_cache) > 64:
                    self._matrix_cache.clear()
                self._matrix_cache[key] = m
        return m

    def _dialog(self, kind: str, **kwargs):
        import webview  # only reached in native mode

        file_dialog = getattr(webview, "FileDialog", None)
        dialog_type = getattr(file_dialog, kind) if file_dialog else getattr(webview, f"{kind}_DIALOG")
        result = self._window.create_file_dialog(dialog_type, **kwargs)
        if isinstance(result, (list, tuple)):
            result = result[0] if result else None
        return result or None

    # -- state ----------------------------------------------------------------
    def get_state(self) -> dict:
        try:
            import cv2  # noqa: F401
            scan = True
        except ImportError:
            scan = False
        return {
            "ok": True,
            "version": __version__,
            "platform": sys.platform,
            "browserMode": self._browser_mode,
            "unifiedTitlebar": self._unified_titlebar,
            "defaults": DEFAULT_PARAMS,
            "logos": list(BUILTIN_LOGOS),
            "formats": GUI_FORMATS,
            "scanAvailable": scan,
        }

    # -- rendering ------------------------------------------------------------
    def render(self, params: dict) -> dict:
        """Render a preview and the diagnostics for *params*."""
        try:
            cfg = config_from_params(params)
            matrix = self._matrix(cfg)
            info = analyse(cfg, matrix)
            total = info.modules_with_border
            preview_box = max(1, min(cfg.box_size, math.ceil(PREVIEW_MAX / total)))
            img = render(cfg.with_(box_size=preview_box), matrix)
            return {
                "ok": True,
                "image": _png_data_url(img),
                "info": info.to_dict(),
                "decodes": decode_check(img, cfg.data),
                "fillHex": to_hex(cfg.fill_rgb),
                "backHex": to_hex(cfg.back_rgb),
                "logoName": Path(str(cfg.logo)).stem if cfg.has_logo else None,
            }
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            return _error(exc)

    # -- logos ----------------------------------------------------------------
    def choose_logo(self) -> dict:
        """Native file dialog (pywebview only)."""
        if self._browser_mode or self._window is None:
            return {"ok": False, "error": "Use the upload button in browser mode."}
        try:
            path = self._dialog(
                "OPEN", file_types=("Images (*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff;*.bmp)",)
            )
            if not path:
                return {"ok": True, "cancelled": True}
            return {"ok": True, "path": str(path), "name": Path(path).stem}
        except Exception as exc:  # noqa: BLE001
            return _error(exc)

    def upload_logo(self, filename: str, data_url: str) -> dict:
        """Store an image sent by the browser and return its temporary path."""
        try:
            header, _, payload = data_url.partition(",")
            if ";base64" not in header:
                raise ValueError("expected a base64 data URL")
            if self._upload_dir is None:
                self._upload_dir = Path(tempfile.mkdtemp(prefix="myfancyqr-logos-"))
            safe = "".join(c for c in Path(filename).name if c.isalnum() or c in "._-") or "logo.png"
            target = self._upload_dir / safe
            target.write_bytes(base64.b64decode(payload))
            from PIL import Image

            with Image.open(target) as im:
                im.verify()
            return {"ok": True, "path": str(target), "name": target.stem}
        except Exception as exc:  # noqa: BLE001
            return _error(exc)

    # -- export -----------------------------------------------------------------
    def export(self, params: dict) -> dict:
        """Save the code: native save dialog, or a download in browser mode."""
        try:
            cfg = config_from_params(params)
            fmt = str((params or {}).get("format", "png")).lower()
            if fmt not in SUPPORTED_FORMATS:
                raise ValueError(f"unsupported format: {fmt}")
            matrix = self._matrix(cfg)
            if self._browser_mode or self._window is None:
                with tempfile.TemporaryDirectory() as tmp:
                    written = save(cfg, Path(tmp) / "qrcode", fmt, matrix=matrix)
                    payload = base64.b64encode(written.read_bytes()).decode("ascii")
                mime = "image/svg+xml" if fmt == "svg" else "application/octet-stream"
                return {"ok": True, "download": f"data:{mime};base64,{payload}", "filename": written.name}
            path = self._dialog(
                "SAVE", save_filename=f"qrcode.{fmt}", file_types=(FILE_TYPES.get(fmt, f"(*.{fmt})"),)
            )
            if not path:
                return {"ok": True, "cancelled": True}
            written = save(cfg, path, fmt, matrix=matrix)
            return {"ok": True, "path": str(written)}
        except Exception as exc:  # noqa: BLE001
            return _error(exc)

    def copy_image(self, params: dict) -> dict:
        """Copy the full-resolution PNG to the clipboard (macOS)."""
        try:
            cfg = config_from_params(params)
            buf = io.BytesIO()
            render(cfg, self._matrix(cfg)).save(buf, "PNG")
            png = buf.getvalue()
            if sys.platform != "darwin" or self._browser_mode:
                return {"ok": False, "error": "Copy is only available in the macOS app.",
                        "fallbackImage": "data:image/png;base64," + base64.b64encode(png).decode("ascii")}
            try:
                from AppKit import NSPasteboard, NSPasteboardTypePNG
                from Foundation import NSData

                board = NSPasteboard.generalPasteboard()
                board.clearContents()
                if not board.setData_forType_(NSData.dataWithBytes_length_(png, len(png)), NSPasteboardTypePNG):
                    raise RuntimeError("pasteboard refused the image")
            except Exception:  # noqa: BLE001 - PyObjC missing or refused: use AppleScript
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(png)
                try:
                    script = f'set the clipboard to (read (POSIX file "{tmp.name}") as «class PNGf»)'
                    subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
                finally:
                    os.unlink(tmp.name)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return _error(exc)

    def reveal(self, path: str) -> dict:
        """Show an exported file in Finder (macOS) or the file manager."""
        try:
            target = Path(path)
            if not target.exists():
                raise FileNotFoundError(f"{path} no longer exists")
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", str(target)], check=True)
            elif os.name == "nt":
                subprocess.run(["explorer", "/select,", str(target)], check=False)
            else:
                subprocess.run(["xdg-open", str(target.parent)], check=True)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return _error(exc)

    # -- presets ----------------------------------------------------------------
    def _read_presets(self) -> dict[str, dict]:
        try:
            data = json.loads(self._presets_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def list_presets(self) -> dict:
        return {"ok": True, "presets": self._read_presets()}

    def save_preset(self, name: str, params: dict) -> dict:
        try:
            name = str(name).strip()
            if not name:
                raise ValueError("give the preset a name")
            config_from_params(params)  # validate before storing
            keep = {k: params[k] for k in DEFAULT_PARAMS if k in params and k != "data"}
            presets = self._read_presets()
            presets[name] = keep
            self._presets_path.parent.mkdir(parents=True, exist_ok=True)
            self._presets_path.write_text(json.dumps(presets, indent=2, sort_keys=True), encoding="utf-8")
            return {"ok": True, "presets": presets}
        except Exception as exc:  # noqa: BLE001
            return _error(exc)

    def delete_preset(self, name: str) -> dict:
        try:
            presets = self._read_presets()
            presets.pop(str(name), None)
            if self._presets_path.exists():
                self._presets_path.write_text(json.dumps(presets, indent=2, sort_keys=True), encoding="utf-8")
            return {"ok": True, "presets": presets}
        except Exception as exc:  # noqa: BLE001
            return _error(exc)


def callable_from_js(name: str) -> bool:
    return name in _CALLABLE_FROM_JS
