"""Core rendering API for MyFancyQR.

This module is deliberately free of any CLI or GUI concern: it turns a
:class:`QRConfig` into a QR code image (raster or SVG), and reports
diagnostics about it (version, size, contrast, logo coverage, decodability).

The pipeline is split in two steps so that each can be tested on its own:

1. :func:`build_matrix` encodes the data into a boolean module matrix
   (this is the only step that depends on the ``qrcode`` library);
2. :func:`render` / :func:`to_svg` draw that matrix, the quiet zone and the
   optional centre logo.

Typical use::

    from myfancyqr import QRConfig, render, save

    cfg = QRConfig("https://example.com", fill_color="#0a3d91", logo="Github")
    img = render(cfg)            # PIL.Image.Image, RGB
    save(cfg, "example.png")     # format inferred from the extension
"""

from __future__ import annotations

import base64
import io
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageColor, ImageDraw, ImageOps

__all__ = [
    "BUILTIN_LOGOS",
    "ERROR_CORRECTION_LEVELS",
    "SUPPORTED_FORMATS",
    "QRConfig",
    "QRInfo",
    "QRMatrix",
    "analyse",
    "build_matrix",
    "contrast_ratio",
    "decode_check",
    "infer_format",
    "parse_color",
    "relative_luminance",
    "render",
    "resolve_logo",
    "save",
    "to_hex",
    "to_svg",
]

#: Output formats accepted by :func:`save`.
SUPPORTED_FORMATS: tuple[str, ...] = (
    "png", "pdf", "svg", "jpg", "jpeg", "bmp", "webp", "tiff", "eps",
)

#: Error-correction levels and the approximate share of codewords each can
#: restore (ISO/IEC 18004).
ERROR_CORRECTION_LEVELS: dict[str, float] = {"L": 0.07, "M": 0.15, "Q": 0.25, "H": 0.30}

LOGO_DIR = Path(__file__).resolve().parent / "logos"

#: Logos shipped with the package, addressable by name (case-insensitive).
BUILTIN_LOGOS: dict[str, Path] = {
    p.stem: p for p in sorted(LOGO_DIR.glob("*.png"))
}

LOGO_BACKDROPS = ("circle", "square", "none")
INVERT_MODES = ("auto", "always", "never")

#: Recommended minimum quiet zone, in modules (ISO/IEC 18004).
MIN_QUIET_ZONE = 4
#: Below this contrast ratio, cheap scanners start to fail.
MIN_CONTRAST = 4.0
#: Background relative luminance under which ``invert_logo="auto"`` inverts.
DARK_BACKGROUND_LUMINANCE = 0.2

RGB = tuple[int, int, int]


# --------------------------------------------------------------------------
# Colours
# --------------------------------------------------------------------------

def parse_color(value: str | Sequence[int]) -> RGB:
    """Parse a colour into an ``(r, g, b)`` tuple.

    Accepts CSS4 colour names (``"limegreen"``), hex strings (``"#0a3d91"``,
    ``"#fff"``), CSS functional notations (``"rgb(10, 61, 145)"``) and
    3- or 4-item sequences of ints. Alpha is discarded: a QR code needs
    opaque modules.
    """
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("empty colour")
        try:
            rgba = ImageColor.getrgb(text)
        except ValueError:
            raise ValueError(
                f"unknown colour {value!r} (use a CSS colour name or a hex code such as '#1d1d1f')"
            ) from None
    else:
        rgba = tuple(int(c) for c in value)
        if len(rgba) not in (3, 4) or not all(0 <= c <= 255 for c in rgba):
            raise ValueError(f"invalid RGB(A) colour {value!r}")
    return (rgba[0], rgba[1], rgba[2])


def to_hex(rgb: RGB) -> str:
    """Return ``#rrggbb`` for an RGB tuple."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def relative_luminance(rgb: RGB) -> float:
    """WCAG 2.x relative luminance of an sRGB colour, in [0, 1]."""
    def channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: RGB, b: RGB) -> float:
    """WCAG contrast ratio between two colours, in [1, 21]."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class QRConfig:
    """Everything needed to draw one QR code.

    Parameters
    ----------
    data:
        Text or URL to encode.
    fill_color, back_color:
        Module ("pixel") and background colours; anything
        :func:`parse_color` accepts.
    box_size:
        Size of one module, in output pixels.
    border:
        Quiet zone around the code, in modules. ISO/IEC 18004 recommends at
        least 4; MyFancyQR v1 used 1, which the CLI keeps as its default.
    error_correction:
        ``"L"``, ``"M"``, ``"Q"``, ``"H"`` or ``None`` for automatic
        (``"L"`` without a logo, ``"H"`` with one, as in v1).
    logo:
        Built-in logo name (see :data:`BUILTIN_LOGOS`) or path to an image.
    logo_scale:
        Logo bounding-box size as a fraction of the code width (quiet zone
        excluded).
    logo_backdrop:
        ``"circle"`` (v1 look), ``"square"`` or ``"none"``.
    logo_ring:
        Thickness of the ring drawn around the backdrop, in pixels.
        ``None`` scales it with ``box_size`` (3 px at the default 25 px).
    invert_logo:
        ``"auto"`` inverts the logo colours on dark backgrounds (v1 only did
        it for pure black), ``"always"`` or ``"never"``.
    dpi:
        Resolution written into raster/PDF metadata; it changes the physical
        print size, not the pixels.
    """

    data: str
    fill_color: str | Sequence[int] = "black"
    back_color: str | Sequence[int] = "white"
    box_size: int = 25
    border: int = MIN_QUIET_ZONE
    error_correction: str | None = None
    logo: str | Path | None = None
    logo_scale: float = 0.25
    logo_backdrop: str = "circle"
    logo_ring: int | None = None
    invert_logo: str = "auto"
    dpi: int = 300

    def __post_init__(self) -> None:
        if not isinstance(self.data, str) or self.data == "":
            raise ValueError("data must be a non-empty string")
        if not isinstance(self.box_size, int) or not 1 <= self.box_size <= 200:
            raise ValueError("box_size must be an integer between 1 and 200")
        if not isinstance(self.border, int) or not 0 <= self.border <= 50:
            raise ValueError("border must be an integer between 0 and 50")
        if self.error_correction is not None and self.error_correction.upper() not in ERROR_CORRECTION_LEVELS:
            raise ValueError("error_correction must be one of L, M, Q, H or None")
        if not 0.05 <= float(self.logo_scale) <= 0.4:
            raise ValueError("logo_scale must be between 0.05 and 0.4")
        if self.logo_backdrop not in LOGO_BACKDROPS:
            raise ValueError(f"logo_backdrop must be one of {', '.join(LOGO_BACKDROPS)}")
        if self.invert_logo not in INVERT_MODES:
            raise ValueError(f"invert_logo must be one of {', '.join(INVERT_MODES)}")
        if self.logo_ring is not None and not 0 <= int(self.logo_ring) <= 100:
            raise ValueError("logo_ring must be between 0 and 100 pixels")
        if not 36 <= int(self.dpi) <= 2400:
            raise ValueError("dpi must be between 36 and 2400")
        # Fail early on bad colours rather than at draw time.
        parse_color(self.fill_color)
        parse_color(self.back_color)

    # Convenience accessors -------------------------------------------------
    @property
    def fill_rgb(self) -> RGB:
        return parse_color(self.fill_color)

    @property
    def back_rgb(self) -> RGB:
        return parse_color(self.back_color)

    @property
    def has_logo(self) -> bool:
        return self.logo not in (None, "", "None", "none")

    @property
    def ecc(self) -> str:
        """Effective error-correction level after resolving ``None``."""
        if self.error_correction:
            return self.error_correction.upper()
        return "H" if self.has_logo else "L"

    @property
    def ring_px(self) -> int:
        if self.logo_ring is not None:
            return int(self.logo_ring)
        return max(1, round(self.box_size * 0.12))

    def with_(self, **changes) -> "QRConfig":
        """Return a copy with some fields changed (validated again)."""
        return replace(self, **changes)

    def to_dict(self) -> dict:
        d = asdict(self)
        if isinstance(d["logo"], Path):
            d["logo"] = str(d["logo"])
        return d


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class QRMatrix:
    """Encoded QR symbol, quiet zone excluded."""

    modules: tuple[tuple[bool, ...], ...]
    version: int
    error_correction: str

    @property
    def size(self) -> int:
        return len(self.modules)


def _encode(data: str, ecc: str) -> tuple[list[list[bool]], int]:
    """Encode *data* with the ``qrcode`` library (no quiet zone)."""
    import qrcode
    from qrcode import constants
    from qrcode.exceptions import DataOverflowError

    level = {
        "L": constants.ERROR_CORRECT_L,
        "M": constants.ERROR_CORRECT_M,
        "Q": constants.ERROR_CORRECT_Q,
        "H": constants.ERROR_CORRECT_H,
    }[ecc]
    qr = qrcode.QRCode(version=None, error_correction=level, border=0)
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except DataOverflowError:
        raise ValueError(
            f"data too long for a QR code at error correction {ecc} "
            f"({len(data.encode('utf-8'))} bytes)"
        ) from None
    return qr.get_matrix(), int(qr.version)


def build_matrix(config: QRConfig) -> QRMatrix:
    """Encode ``config.data`` into a module matrix (quiet zone excluded)."""
    rows, version = _encode(config.data, config.ecc)
    modules = tuple(tuple(bool(v) for v in row) for row in rows)
    return QRMatrix(modules=modules, version=version, error_correction=config.ecc)


# --------------------------------------------------------------------------
# Logo handling
# --------------------------------------------------------------------------

def resolve_logo(logo: str | Path) -> Path:
    """Return the file path of a built-in logo name or of a custom image."""
    key = str(logo)
    for name, path in BUILTIN_LOGOS.items():
        if name.lower() == key.lower():
            return path
    path = Path(key).expanduser()
    if not path.is_file():
        known = ", ".join(BUILTIN_LOGOS) or "none"
        raise FileNotFoundError(f"logo not found: {key} (built-in logos: {known})")
    return path


def _invert_preserving_alpha(img: Image.Image) -> Image.Image:
    r, g, b, a = img.convert("RGBA").split()
    rgb = ImageOps.invert(Image.merge("RGB", (r, g, b)))
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def _load_logo(config: QRConfig, box_px: int) -> Image.Image:
    """Load the logo, fit it in a *box_px* square (aspect ratio kept)."""
    path = resolve_logo(config.logo)  # type: ignore[arg-type]
    with Image.open(path) as src:
        logo = src.convert("RGBA")
    logo = ImageOps.contain(logo, (box_px, box_px), Image.Resampling.LANCZOS)
    invert = config.invert_logo == "always" or (
        config.invert_logo == "auto"
        and relative_luminance(config.back_rgb) < DARK_BACKGROUND_LUMINANCE
    )
    if invert:
        logo = _invert_preserving_alpha(logo)
    return logo


@dataclass(frozen=True)
class _LogoGeometry:
    """Logo placement in output pixels."""

    logo_box: int          # side of the square the logo is fitted into
    backdrop_radius: float  # circle radius, or half-side of the square backdrop
    ring: int
    center: float


def _logo_geometry(config: QRConfig, n_modules: int) -> _LogoGeometry:
    code_px = n_modules * config.box_size
    total_px = (n_modules + 2 * config.border) * config.box_size
    logo_box = max(1, round(code_px * config.logo_scale))
    if config.logo_backdrop == "circle":
        radius = logo_box * 0.65  # v1 proportion: slightly larger than the logo
    else:
        radius = logo_box * 0.5 + max(2, round(logo_box * 0.08))
    ring = config.ring_px if config.logo_backdrop != "none" else 0
    return _LogoGeometry(logo_box, radius, ring, total_px / 2.0)


def _logo_coverage(config: QRConfig, n_modules: int) -> float:
    """Share of the code area hidden by the logo and its backdrop."""
    if not config.has_logo:
        return 0.0
    geo = _logo_geometry(config, n_modules)
    code_area = float(n_modules * config.box_size) ** 2
    outer = geo.backdrop_radius + geo.ring
    if config.logo_backdrop == "circle":
        area = 3.141592653589793 * outer * outer
    elif config.logo_backdrop == "square":
        area = (2 * outer) ** 2
    else:  # opaque pixels of the logo bounding box, approximated by the box
        area = float(geo.logo_box) ** 2
    return min(1.0, area / code_area)


def _draw_backdrop(canvas: Image.Image, config: QRConfig, geo: _LogoGeometry) -> None:
    """Draw the anti-aliased logo backdrop (ring + disc/square) in place."""
    if config.logo_backdrop == "none":
        return
    ss = 4  # supersampling factor
    outer = geo.backdrop_radius + geo.ring
    side = int(2 * outer) + 4
    big = Image.new("RGBA", (side * ss, side * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    c = side * ss / 2.0

    def shape(r: float, color: RGB) -> None:
        box = [c - r * ss, c - r * ss, c + r * ss, c + r * ss]
        if config.logo_backdrop == "circle":
            draw.ellipse(box, fill=color + (255,))
        else:
            draw.rounded_rectangle(box, radius=r * ss * 0.25, fill=color + (255,))

    if geo.ring > 0:
        shape(outer, config.fill_rgb)
    shape(geo.backdrop_radius, config.back_rgb)
    small = big.resize((side, side), Image.Resampling.LANCZOS)
    origin = round(geo.center - side / 2.0)
    canvas.alpha_composite(small, (origin, origin))


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render(config: QRConfig, matrix: QRMatrix | None = None) -> Image.Image:
    """Render the QR code as an RGB :class:`PIL.Image.Image`."""
    matrix = matrix or build_matrix(config)
    n, q, box = matrix.size, config.border, config.box_size
    total = n + 2 * q

    # Module mask at one pixel per module, then nearest-neighbour upscaling:
    # exact, crisp, and much faster than drawing rectangles.
    mask_small = Image.new("L", (total, total), 0)
    mask_small.putdata([
        255 if (q <= y < q + n and q <= x < q + n and matrix.modules[y - q][x - q]) else 0
        for y in range(total) for x in range(total)
    ])
    mask = mask_small.resize((total * box, total * box), Image.Resampling.NEAREST)

    img = Image.new("RGBA", mask.size, config.back_rgb + (255,))
    img.paste(config.fill_rgb + (255,), (0, 0) + mask.size, mask)

    if config.has_logo:
        geo = _logo_geometry(config, n)
        _draw_backdrop(img, config, geo)
        logo = _load_logo(config, geo.logo_box)
        pos = (round(geo.center - logo.width / 2.0), round(geo.center - logo.height / 2.0))
        img.alpha_composite(logo, pos)

    return img.convert("RGB")


def _runs(row: Iterable[bool]) -> Iterable[tuple[int, int]]:
    """Yield ``(start, length)`` of consecutive dark modules in a row."""
    start = None
    for x, dark in enumerate(list(row) + [False]):
        if dark and start is None:
            start = x
        elif not dark and start is not None:
            yield start, x - start
            start = None


def to_svg(config: QRConfig, matrix: QRMatrix | None = None) -> str:
    """Render the QR code as a standalone SVG document.

    Coordinates are in modules (``viewBox``), so the code scales without
    loss; ``width``/``height`` are set to the pixel size implied by
    ``box_size``. The logo, if any, is embedded as a base64 PNG.
    """
    matrix = matrix or build_matrix(config)
    n, q, box = matrix.size, config.border, config.box_size
    total = n + 2 * q
    fill, back = to_hex(config.fill_rgb), to_hex(config.back_rgb)

    path = "".join(
        f"M{x + q} {y + q}h{length}v1h-{length}z"
        for y, row in enumerate(matrix.modules)
        for x, length in _runs(row)
    )
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total * box}" height="{total * box}" '
        f'viewBox="0 0 {total} {total}">',
        f'<rect width="{total}" height="{total}" fill="{back}"/>',
        f'<path fill="{fill}" shape-rendering="crispEdges" d="{path}"/>',
    ]

    if config.has_logo:
        geo = _logo_geometry(config, n)
        s = 1.0 / box  # pixels -> modules
        c = geo.center * s
        if config.logo_backdrop != "none":
            def shape(r: float, color: str) -> str:
                r *= s
                if config.logo_backdrop == "circle":
                    return f'<circle cx="{c:.4f}" cy="{c:.4f}" r="{r:.4f}" fill="{color}"/>'
                return (f'<rect x="{c - r:.4f}" y="{c - r:.4f}" width="{2 * r:.4f}" height="{2 * r:.4f}" '
                        f'rx="{r * 0.25:.4f}" fill="{color}"/>')

            if geo.ring > 0:
                parts.append(shape(geo.backdrop_radius + geo.ring, fill))
            parts.append(shape(geo.backdrop_radius, back))
        logo = _load_logo(config, geo.logo_box)
        buf = io.BytesIO()
        logo.save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        w, h = logo.width * s, logo.height * s
        parts.append(
            f'<image x="{c - w / 2:.4f}" y="{c - h / 2:.4f}" width="{w:.4f}" height="{h:.4f}" '
            f'href="data:image/png;base64,{b64}"/>'
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------

def infer_format(path: str | Path, default: str = "png") -> str:
    """Return the output format implied by *path*'s extension, or *default*."""
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix if suffix in SUPPORTED_FORMATS else default


def save(config: QRConfig, path: str | Path, fmt: str | None = None,
         matrix: QRMatrix | None = None) -> Path:
    """Render and write the QR code to *path*; return the final path.

    The format is *fmt* if given, otherwise inferred from the extension
    (``png`` when there is none). The extension is added or corrected to
    match the format.
    """
    path = Path(path).expanduser()
    fmt = (fmt or infer_format(path)).lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported format: {fmt} (supported: {', '.join(SUPPORTED_FORMATS)})")
    suffix = path.suffix.lower().lstrip(".")
    if suffix != fmt:
        # "out.png" with fmt="pdf" -> "out.pdf"; "out" or "out.v2" -> "out.pdf" / "out.v2.pdf"
        path = path.with_suffix(f".{fmt}") if suffix in SUPPORTED_FORMATS else path.with_name(f"{path.name}.{fmt}")
    if not path.parent.exists():
        raise FileNotFoundError(f"output directory does not exist: {path.parent}")

    matrix = matrix or build_matrix(config)
    if fmt == "svg":
        path.write_text(to_svg(config, matrix), encoding="utf-8")
        return path

    img = render(config, matrix)
    dpi = (config.dpi, config.dpi)
    if fmt == "png":
        img.save(path, "PNG", dpi=dpi, optimize=True)
    elif fmt in ("jpg", "jpeg"):
        img.save(path, "JPEG", quality=95, subsampling=0, dpi=dpi)
    elif fmt == "webp":
        img.save(path, "WEBP", lossless=True)
    elif fmt == "tiff":
        img.save(path, "TIFF", compression="tiff_lzw", dpi=dpi)
    elif fmt == "bmp":
        img.save(path, "BMP")
    elif fmt == "pdf":
        img.save(path, "PDF", resolution=float(config.dpi))
    elif fmt == "eps":
        img.save(path, "EPS")
    return path


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class QRInfo:
    """Diagnostics for a configuration, as displayed by the GUI."""

    version: int
    modules: int
    modules_with_border: int
    pixel_size: int
    error_correction: str
    data_bytes: int
    contrast_ratio: float
    inverted: bool
    logo_coverage: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def analyse(config: QRConfig, matrix: QRMatrix | None = None) -> QRInfo:
    """Compute size, contrast and robustness diagnostics for *config*."""
    matrix = matrix or build_matrix(config)
    n = matrix.size
    fill, back = config.fill_rgb, config.back_rgb
    ratio = contrast_ratio(fill, back)
    inverted = relative_luminance(fill) > relative_luminance(back)
    coverage = _logo_coverage(config, n)

    warnings: list[str] = []
    if config.border < MIN_QUIET_ZONE:
        warnings.append(
            f"Quiet zone of {config.border} module(s): ISO/IEC 18004 recommends at least {MIN_QUIET_ZONE}."
        )
    if ratio < MIN_CONTRAST:
        warnings.append(f"Low contrast ({ratio:.1f}:1): some scanners may fail below {MIN_CONTRAST:.0f}:1.")
    if inverted:
        warnings.append("Light modules on a dark background: not all scanners read inverted codes.")
    capacity = ERROR_CORRECTION_LEVELS[matrix.error_correction]
    if coverage > 0.5 * capacity:
        warnings.append(
            f"The logo hides {coverage:.0%} of the code, too much for error correction "
            f"{matrix.error_correction} (~{capacity:.0%}): use a smaller logo or level H."
        )

    return QRInfo(
        version=matrix.version,
        modules=n,
        modules_with_border=n + 2 * config.border,
        pixel_size=(n + 2 * config.border) * config.box_size,
        error_correction=matrix.error_correction,
        data_bytes=len(config.data.encode("utf-8")),
        contrast_ratio=round(ratio, 2),
        inverted=inverted,
        logo_coverage=round(coverage, 4),
        warnings=warnings,
    )


def decode_check(img: Image.Image, expected: str, max_side: int = 1000) -> bool | None:
    """Try to read *img* back with OpenCV and compare with *expected*.

    Returns ``True``/``False``, or ``None`` when OpenCV (optional dependency
    ``opencv-python-headless``) is not installed.

    OpenCV's detector is sensitive to the apparent module size, so the image
    is tried at several scales (as a phone sees a code from various
    distances), and inverted too, since many decoders only look for
    dark-on-light symbols. The check passes if any attempt returns
    *expected*; it fails if nothing decodes or something else decodes.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    gray = img.convert("L")
    side = max(gray.size)
    sizes = sorted({min(side, max_side), *(s for s in (640, 400) if s < side)}, reverse=True)
    detector = cv2.QRCodeDetector()
    for size in sizes:
        scaled = gray if size == side else gray.resize((size, size), Image.Resampling.BOX)
        for candidate in (scaled, ImageOps.invert(scaled)):
            try:
                text, _, _ = detector.detectAndDecode(np.asarray(candidate))
            except cv2.error:
                continue
            if text == expected:
                return True
    return False
