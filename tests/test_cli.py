from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from myfancyqr import cli

from .conftest import requires_cv2

URL = "https://example.com"


@pytest.mark.parametrize(
    "output, fmt, expected",
    [
        ("qrcode", None, ("qrcode.jpg", "jpg")),          # v1 default format
        ("qrcode.png", None, ("qrcode.png", "png")),      # fixed: v1 ignored the extension
        ("file_name", "pdf", ("file_name.pdf", "pdf")),
        ("out.png", "pdf", ("out.pdf", "pdf")),
        ("dir/name.v2", None, ("dir/name.v2.jpg", "jpg")),
    ],
)
def test_resolve_output(output, fmt, expected):
    path, f = cli.resolve_output(output, fmt)
    assert (str(path), f) == (str(Path(expected[0])), expected[1])


def test_v1_colour_rules():
    assert cli.apply_v1_colour_rules("black", "black") == ("black", "white")
    assert cli.apply_v1_colour_rules("white", "white") == ("black", "white")
    assert cli.apply_v1_colour_rules("#000", "black") == ("#000", "white")
    assert cli.apply_v1_colour_rules("orange", "red") == ("orange", "red")


def run(tmp_path, monkeypatch, *argv):
    monkeypatch.chdir(tmp_path)
    return cli.main(list(argv))


def test_default_invocation_writes_jpg(tmp_path, monkeypatch, capsys):
    assert run(tmp_path, monkeypatch, URL) == 0
    assert (tmp_path / "qrcode.jpg").is_file()
    assert "QR code generated: qrcode.jpg" in capsys.readouterr().out


def test_v1_gallery_commands(tmp_path, monkeypatch):
    (tmp_path / "example").mkdir()
    assert run(tmp_path, monkeypatch, URL, "example/basic_colored", "-bc", "orange", "-pc", "red") == 0
    with Image.open(tmp_path / "example/basic_colored.jpg") as im:
        r, g, b = im.convert("RGB").getpixel((2, 2))
        assert r > 200 and 120 < g < 200 and b < 60  # orange quiet zone (JPEG tolerance)
    assert run(tmp_path, monkeypatch, URL, "example/logo", "-l", "Github") == 0
    assert (tmp_path / "example/logo.jpg").is_file()
    assert run(tmp_path, monkeypatch, URL, "example/wiki_r", "--logo", "Wikipedia", "-bc", "black") == 0


def test_extension_and_hex_colours(tmp_path, monkeypatch):
    assert run(tmp_path, monkeypatch, URL, "out.png", "-pc", "#0a3d91", "-bs", "4", "-bw", "4") == 0
    with Image.open(tmp_path / "out.png") as im:
        assert im.format == "PNG"
        assert im.convert("RGB").getpixel((4 * 4 + 1, 4 * 4 + 1)) == (10, 61, 145)


def test_format_flag_overrides_extension(tmp_path, monkeypatch):
    assert run(tmp_path, monkeypatch, URL, "out.png", "-f", "svg") == 0
    assert (tmp_path / "out.svg").read_text().startswith("<?xml")
    assert not (tmp_path / "out.png").exists()


def test_list_options(capsys):
    assert cli.main(["--list-formats"]) == 0
    assert "- svg" in capsys.readouterr().out
    assert cli.main(["--list-logos"]) == 0
    assert "- Github" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        [URL, "x", "-pc", "notacolour"],
        [URL, "x", "-l", "Youtube"],
        [URL, "x", "--logo-size", "80"],
    ],
)
def test_errors_exit_with_status_2(tmp_path, monkeypatch, argv):
    with pytest.raises(SystemExit) as exc:
        run(tmp_path, monkeypatch, *argv)
    assert exc.value.code == 2


def test_quiet_zone_warning_on_stderr(tmp_path, monkeypatch, capsys):
    run(tmp_path, monkeypatch, URL, "q.png")
    assert "Quiet zone" in capsys.readouterr().err


@requires_cv2
def test_check_flag(tmp_path, monkeypatch, capsys):
    assert run(tmp_path, monkeypatch, URL, "c.png", "-bw", "4", "-l", "Github", "--check") == 0
    assert "decodes correctly" in capsys.readouterr().out


def test_qr_generator_shim(tmp_path, monkeypatch):
    import qr_generator

    monkeypatch.chdir(tmp_path)
    assert qr_generator.main([URL, "shim.png"]) == 0
    assert (tmp_path / "shim.png").is_file()
