"""Command-line interface (backward compatible with MyFancyQR v1).

Every v1 invocation keeps working, e.g.::

    python qr_generator.py https://example.com example/basic_colored -bc orange -pc red

What changed in v2:

* the output format is really inferred from the extension
  (``out.png`` -> PNG); ``-f`` still wins, and the default stays JPEG;
* colours accept hex codes (``-pc '#0a3d91'``) as well as CSS names;
* logos keep their aspect ratio; SVG output honours colours, box size,
  border and logo;
* new options: ``--error-correction``, ``--logo-size``, ``--logo-backdrop``,
  ``--invert-logo``, ``--list-logos``, ``--check`` and ``--version``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import (
    BUILTIN_LOGOS,
    INVERT_MODES,
    LOGO_BACKDROPS,
    SUPPORTED_FORMATS,
    QRConfig,
    analyse,
    build_matrix,
    decode_check,
    infer_format,
    parse_color,
    render,
    save,
)

DEFAULT_URL = "https://github.com/leomrtinez/MyFancyQR"
DEFAULT_OUTPUT = "qrcode"
DEFAULT_FORMAT = "jpg"   # v1 default when neither -f nor an extension is given
DEFAULT_BORDER = 1       # v1 default; ISO/IEC 18004 recommends 4

BLACK, WHITE = (0, 0, 0), (255, 255, 255)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="myfancyqr",
        description="Generate a fancy coloured QR code from a text or a link.",
        epilog="Built-in logos: " + (", ".join(BUILTIN_LOGOS) or "none"),
    )
    p.add_argument("url", nargs="?", default=DEFAULT_URL, help="text or URL to encode")
    p.add_argument(
        "output", nargs="?", default=DEFAULT_OUTPUT,
        help="output file path, e.g. qrcode or qrcode.png (format inferred from the extension)",
    )
    p.add_argument(
        "-f", "--format", choices=SUPPORTED_FORMATS, default=None,
        help=f"output format; overrides the extension (default: from extension, else {DEFAULT_FORMAT})",
    )
    p.add_argument("-ls", "--list-formats", action="store_true", help="list supported formats and exit")
    p.add_argument("--list-logos", action="store_true", help="list built-in logos and exit")
    p.add_argument("-bs", "--box-size", type=int, default=25, help="size of one module in pixels (default: 25)")
    p.add_argument(
        "-bw", "--border-width", type=int, default=DEFAULT_BORDER,
        help=f"quiet zone in modules (default: {DEFAULT_BORDER}; 4 recommended)",
    )
    p.add_argument("-l", "--logo", default=None, help="built-in logo name or path to an image")
    p.add_argument("-bc", "--back-color", default="white", help="background colour: CSS name or hex (default: white)")
    p.add_argument("-pc", "--pixel-color", default="black", help="module colour: CSS name or hex (default: black)")
    p.add_argument(
        "-ec", "--error-correction", choices=("L", "M", "Q", "H"), type=str.upper, default=None,
        help="error-correction level (default: L, or H with a logo)",
    )
    p.add_argument(
        "--logo-size", type=float, default=25.0,
        help="logo size in %% of the code width, 5-40 (default: 25)",
    )
    p.add_argument("--logo-backdrop", choices=LOGO_BACKDROPS, default="circle", help="shape behind the logo")
    p.add_argument("--invert-logo", choices=INVERT_MODES, default="auto", help="invert logo colours")
    p.add_argument("--check", action="store_true", help="decode the result to verify it (needs opencv)")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def resolve_output(output: str, fmt: str | None) -> tuple[Path, str]:
    """Return ``(path, format)`` following v1 rules, minus the v1 bug.

    ``-f`` wins; otherwise the extension decides; otherwise JPEG. The
    extension is added (``qrcode`` -> ``qrcode.jpg``) or replaced when it
    names another supported format (``out.png -f pdf`` -> ``out.pdf``).
    """
    fmt = fmt or infer_format(output, default=DEFAULT_FORMAT)
    path = Path(output)
    suffix = path.suffix.lower().lstrip(".")
    if suffix != fmt:
        path = path.with_suffix(f".{fmt}") if suffix in SUPPORTED_FORMATS else path.with_name(f"{path.name}.{fmt}")
    return path, fmt


def apply_v1_colour_rules(back: str, pixel: str) -> tuple[str, str]:
    """Apply the v1 convenience rules for identical colours.

    ``-bc black`` with the default black modules gives white modules on
    black; ``-pc white`` with the default white background gives white
    modules on black. Any other combination is left untouched.
    """
    b, f = parse_color(back), parse_color(pixel)
    if b == BLACK and f == BLACK:
        return back, "white"
    if b == WHITE and f == WHITE:
        return "black", pixel
    return back, pixel


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_formats:
        print("Supported formats:")
        for f in SUPPORTED_FORMATS:
            print(f"  - {f}")
        return 0
    if args.list_logos:
        print("Built-in logos:")
        for name in BUILTIN_LOGOS:
            print(f"  - {name}")
        return 0

    try:
        back, pixel = apply_v1_colour_rules(args.back_color, args.pixel_color)
        config = QRConfig(
            data=args.url,
            fill_color=pixel,
            back_color=back,
            box_size=args.box_size,
            border=args.border_width,
            error_correction=args.error_correction,
            logo=args.logo,
            logo_scale=args.logo_size / 100.0,
            logo_backdrop=args.logo_backdrop,
            invert_logo=args.invert_logo,
        )
        path, fmt = resolve_output(args.output, args.format)
        matrix = build_matrix(config)
        written = save(config, path, fmt, matrix=matrix)
    except (ValueError, FileNotFoundError, OSError) as exc:
        parser.error(str(exc))  # exits with status 2

    info = analyse(config, matrix)
    label = "QR code with logo generated" if config.has_logo else "QR code generated"
    print(f"{label}: {written}")
    for w in info.warnings:
        print(f"warning: {w}", file=sys.stderr)

    if args.check:
        ok = decode_check(render(config, matrix), config.data)
        if ok is None:
            print("check: skipped (install opencv-python-headless to enable it)", file=sys.stderr)
        elif ok:
            print("check: decodes correctly")
        else:
            print("check: FAILED to decode the generated code", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
