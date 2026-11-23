# Changelog

## 2.0.0 (unreleased)

The single script becomes the `myfancyqr` package. Every v1 command line keeps working through `qr_generator.py`.

### Added
- Python API: `QRConfig`, `render`, `to_svg`, `save`, `analyse`, `decode_check`.
- CLI options `--error-correction`, `--logo-size`, `--logo-backdrop`, `--invert-logo`, `--list-logos`, `--check`, `--version`.
- Warnings for a small quiet zone, low contrast, inverted colours and a logo too large for the error-correction level.
- `pyproject.toml` (installable package, `myfancyqr` command) and `environment.yml`.
- Test suite (`pytest`).

### Fixed
- The output format is now inferred from the file extension, as documented; v1 always used the `-f` default (`jpg`).
- Hex colours are accepted; v1 only knew CSS colour names.
- Logos keep their aspect ratio; v1 squeezed them into a square.
- SVG output honours colours, box size, border and logo; v1 ignored them and refused logos.
- Automatic logo inversion works for any dark background, not only `black`.
- Removed the `Youtube` built-in logo, whose file did not exist.

### Changed
- Built-in logos moved from `logo/` to `myfancyqr/logos/`.
- `matplotlib` is no longer required; Pillow parses colour names.
- Python 3.10 or later.

## 1.0 — tag `v1-final`

Original command-line script.
