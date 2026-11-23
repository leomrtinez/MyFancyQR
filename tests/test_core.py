from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from myfancyqr import core
from myfancyqr.core import (
    BUILTIN_LOGOS,
    QRConfig,
    analyse,
    build_matrix,
    contrast_ratio,
    decode_check,
    infer_format,
    parse_color,
    render,
    resolve_logo,
    save,
    to_svg,
)

from .conftest import requires_cv2, requires_qrcode

URL = "https://github.com/leomrtinez/MyFancyQR"


# -- colours ----------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("black", (0, 0, 0)),
        ("LimeGreen", (50, 205, 50)),
        ("rebeccapurple", (102, 51, 153)),  # CSS4-only name, supported in v1 via matplotlib
        ("#0a3d91", (10, 61, 145)),
        ("#fff", (255, 255, 255)),
        ("rgb(10, 61, 145)", (10, 61, 145)),
        ((1, 2, 3), (1, 2, 3)),
        ((1, 2, 3, 128), (1, 2, 3)),
    ],
)
def test_parse_color(value, expected):
    assert parse_color(value) == expected


@pytest.mark.parametrize("value", ["", "notacolour", "#12", (300, 0, 0), (1, 2)])
def test_parse_color_rejects_invalid(value):
    with pytest.raises(ValueError):
        parse_color(value)


def test_contrast_ratio_bounds():
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert contrast_ratio((120, 120, 120), (120, 120, 120)) == pytest.approx(1.0)


# -- configuration ----------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": ""},
        {"box_size": 0},
        {"border": -1},
        {"error_correction": "X"},
        {"logo_scale": 0.9},
        {"logo_backdrop": "hexagon"},
        {"invert_logo": "sometimes"},
        {"fill_color": "nope"},
    ],
)
def test_config_validation(kwargs):
    base = {"data": URL}
    base.update(kwargs)
    with pytest.raises(ValueError):
        QRConfig(**base)


def test_auto_error_correction_matches_v1():
    assert QRConfig(URL).ecc == "L"
    assert QRConfig(URL, logo="Github").ecc == "H"
    assert QRConfig(URL, logo="Github", error_correction="q").ecc == "Q"


# -- logos ------------------------------------------------------------------

def test_builtin_logos_exist():
    assert {"Github", "Scholar", "Wikipedia"} <= set(BUILTIN_LOGOS)
    for path in BUILTIN_LOGOS.values():
        assert path.is_file()


def test_resolve_logo(tmp_path):
    assert resolve_logo("github") == BUILTIN_LOGOS["Github"]
    custom = tmp_path / "mine.png"
    Image.new("RGBA", (10, 20)).save(custom)
    assert resolve_logo(str(custom)) == custom
    with pytest.raises(FileNotFoundError):
        resolve_logo("Youtube")  # declared but missing in v1


def test_logo_keeps_aspect_ratio(tmp_path):
    wide = tmp_path / "wide.png"
    Image.new("RGBA", (400, 100), (255, 0, 0, 255)).save(wide)
    logo = core._load_logo(QRConfig(URL, logo=str(wide)), 200)
    assert logo.size == (200, 50)


def test_auto_invert_on_dark_background(tmp_path):
    dark_logo = tmp_path / "dark.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 255)).save(dark_logo)
    on_black = core._load_logo(QRConfig(URL, logo=str(dark_logo), back_color="#101010", fill_color="white"), 10)
    on_white = core._load_logo(QRConfig(URL, logo=str(dark_logo)), 10)
    assert on_black.getpixel((5, 5))[:3] == (255, 255, 255)
    assert on_white.getpixel((5, 5))[:3] == (0, 0, 0)
    never = core._load_logo(
        QRConfig(URL, logo=str(dark_logo), back_color="black", fill_color="white", invert_logo="never"), 10
    )
    assert never.getpixel((5, 5))[:3] == (0, 0, 0)


# -- encoding ---------------------------------------------------------------

@requires_qrcode
def test_matrix_size_matches_version():
    m = build_matrix(QRConfig(URL))
    assert m.size == 17 + 4 * m.version
    assert m.error_correction == "L"


@requires_qrcode
def test_data_overflow_is_a_value_error():
    with pytest.raises(ValueError, match="too long"):
        build_matrix(QRConfig("x" * 5000, error_correction="H"))


# -- raster rendering -------------------------------------------------------

def test_render_geometry_and_colours():
    cfg = QRConfig(URL, fill_color="#0a3d91", back_color="#fff6e5", box_size=10, border=4)
    m = build_matrix(cfg)
    img = render(cfg, m)
    assert img.mode == "RGB"
    assert img.size == ((m.size + 8) * 10,) * 2
    assert img.getpixel((0, 0)) == (255, 246, 229)            # quiet zone
    assert img.getpixel((4 * 10 + 5, 4 * 10 + 5)) == (10, 61, 145)  # finder pattern corner


@requires_cv2
@pytest.mark.parametrize("logo", [None, *BUILTIN_LOGOS])
def test_render_decodes(logo):
    cfg = QRConfig(URL, box_size=10, logo=logo)
    assert decode_check(render(cfg), URL) is True


@requires_cv2
@pytest.mark.parametrize("backdrop", ["circle", "square", "none"])
def test_render_decodes_all_backdrops(backdrop):
    cfg = QRConfig(URL, box_size=10, logo="Github", logo_backdrop=backdrop)
    assert decode_check(render(cfg), URL) is True


@requires_cv2
def test_inverted_code_decodes():
    cfg = QRConfig(URL, box_size=10, fill_color="white", back_color="black", logo="Wikipedia")
    assert decode_check(render(cfg), URL) is True


@requires_cv2
def test_decode_check_detects_mismatch():
    assert decode_check(render(QRConfig(URL, box_size=8)), "something else") is False


# -- SVG --------------------------------------------------------------------

SVG_NS = {"s": "http://www.w3.org/2000/svg"}


def test_svg_honours_style():
    cfg = QRConfig(URL, fill_color="#0a3d91", back_color="#fff6e5", box_size=12, border=2)
    m = build_matrix(cfg)
    root = ET.fromstring(to_svg(cfg, m).split("?>", 1)[1])
    total = m.size + 4
    assert root.get("width") == str(total * 12)
    assert root.get("viewBox") == f"0 0 {total} {total}"
    assert root.find("s:rect", SVG_NS).get("fill") == "#fff6e5"
    assert root.find("s:path", SVG_NS).get("fill") == "#0a3d91"
    assert root.find("s:image", SVG_NS) is None


def test_svg_embeds_logo():
    svg = to_svg(QRConfig(URL, logo="Github"))
    root = ET.fromstring(svg.split("?>", 1)[1])
    image = root.find("s:image", SVG_NS)
    assert image is not None and image.get("href").startswith("data:image/png;base64,")
    assert root.find("s:circle", SVG_NS) is not None


def test_svg_matches_raster_modules():
    """Every dark module of the raster must be covered by the SVG path."""
    cfg = QRConfig(URL, box_size=1, border=0)
    m = build_matrix(cfg)
    path = ET.fromstring(to_svg(cfg, m).split("?>", 1)[1]).find("s:path", SVG_NS).get("d")
    dark = set()
    for seg in path.split("M")[1:]:
        xy, rest = seg.split("h", 1)
        x, y = map(int, xy.split())
        length = int(rest.split("v", 1)[0])
        dark.update((x + i, y) for i in range(length))
    expected = {(x, y) for y, row in enumerate(m.modules) for x, v in enumerate(row) if v}
    assert dark == expected


# -- saving -----------------------------------------------------------------

@pytest.mark.parametrize(
    "name, fmt, expected",
    [
        ("out", None, "out.png"),
        ("out.png", None, "out.png"),
        ("out.png", "pdf", "out.pdf"),
        ("out.v2", "jpg", "out.v2.jpg"),
        ("out.JPEG", None, "out.JPEG"),
    ],
)
def test_save_paths(tmp_path, name, fmt, expected):
    written = save(QRConfig(URL, box_size=4), tmp_path / name, fmt)
    assert written == tmp_path / expected
    assert written.stat().st_size > 0


@pytest.mark.parametrize("fmt", core.SUPPORTED_FORMATS)
def test_save_every_format(tmp_path, fmt):
    written = save(QRConfig(URL, box_size=4, logo="Scholar"), tmp_path / "code", fmt)
    head = written.read_bytes()[:16]
    if fmt == "svg":
        assert head.startswith(b"<?xml")
    elif fmt == "pdf":
        assert head.startswith(b"%PDF")
    elif fmt == "eps":
        assert head.startswith(b"%!PS")
    else:
        with Image.open(written) as im:
            assert im.size[0] == im.size[1] > 0


def test_save_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        save(QRConfig(URL), tmp_path / "x", "gif")


def test_save_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        save(QRConfig(URL), tmp_path / "nope" / "x.png")


def test_infer_format():
    assert infer_format("a.TIFF") == "tiff"
    assert infer_format("a") == "png"
    assert infer_format(Path("a.txt"), default="jpg") == "jpg"


# -- diagnostics ------------------------------------------------------------

def test_analyse_clean_config():
    cfg = QRConfig(URL, box_size=10)
    info = analyse(cfg)
    assert info.warnings == []
    assert info.pixel_size == info.modules_with_border * 10
    assert info.modules_with_border == info.modules + 8
    assert info.contrast_ratio == pytest.approx(21.0)
    assert info.data_bytes == len(URL)


def test_analyse_warnings():
    info = analyse(QRConfig(URL, border=1, fill_color="#dddddd", back_color="white"))
    joined = " ".join(info.warnings)
    assert "Quiet zone" in joined and "Low contrast" in joined

    inv = analyse(QRConfig(URL, fill_color="white", back_color="black"))
    assert any("inverted" in w for w in inv.warnings)
    assert inv.inverted

    risky = analyse(QRConfig(URL, logo="Github", error_correction="L", logo_scale=0.3))
    assert any("logo hides" in w for w in risky.warnings)

    safe = analyse(QRConfig(URL, logo="Github"))
    assert not any("logo hides" in w for w in safe.warnings)
    assert 0 < safe.logo_coverage < 0.15
