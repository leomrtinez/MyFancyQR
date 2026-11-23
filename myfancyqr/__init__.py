"""MyFancyQR: fancy coloured QR codes from the command line or a desktop GUI."""

from .core import (
    BUILTIN_LOGOS,
    ERROR_CORRECTION_LEVELS,
    SUPPORTED_FORMATS,
    QRConfig,
    QRInfo,
    QRMatrix,
    analyse,
    build_matrix,
    contrast_ratio,
    decode_check,
    infer_format,
    parse_color,
    render,
    resolve_logo,
    save,
    to_hex,
    to_svg,
)

__version__ = "2.0.0.dev0"

__all__ = [
    "BUILTIN_LOGOS",
    "ERROR_CORRECTION_LEVELS",
    "SUPPORTED_FORMATS",
    "QRConfig",
    "QRInfo",
    "QRMatrix",
    "__version__",
    "analyse",
    "build_matrix",
    "contrast_ratio",
    "decode_check",
    "infer_format",
    "parse_color",
    "render",
    "resolve_logo",
    "save",
    "to_hex",
    "to_svg",
]
