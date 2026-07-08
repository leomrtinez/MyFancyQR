# 📷 MyFancyQR

MyFancyQR is a lightweight command-line tool that generates QR codes from any text or URL, with support for multiple output formats (PNG, SVG, PDF, JPEG, and more) and customizable styling options.

![License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue.svg)

## 📑 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Configuration](#️-configuration)
- [Usage](#-usage)
- [Contributing](#-contributing)
- [License](#-license)
- [Contact](#-contact)

## ✨ Features

- Generate QR codes from any text or URL
- Export to multiple formats: PNG, SVG, PDF, JPEG, BMP, WEBP, TIFF, or EPS (terminal preview)
- Customizable box size and border width
- Simple, dependency-light CLI

## 📥 Installation

Clone the repository:

```bash
git clone git@github.com:leomrtinez/MyFancyQR.git
cd MyFancyQR
```

### Requirements


If you already have a Conda environment:
<details>
<summary>🐍 Using Conda</summary>

You will need the following packages:

```bash
conda install conda-forge::qrcode
conda install anaconda::pillow
```
</details>




Otherwise you can also install it via pip:

<details>
<summary>📦 Using pip</summary>

```bash
pip install qrcode[pil]
```
</details>

## ⚙️ Configuration

| Argument                    | Default  | Description                                                          |
|-----------------------------|----------|----------------------------------------------------------------------|
| `url`                       | —        | Text or URL to encode **(required)**                                 |
| `output`                    | `qrcode` | Output file path                                                     |
| `--list-formats`            | —        | List all supported output formats                                    |
| `-l`, `--logo`              | `None`   | Include a logo in the QR code. Some are provided in the `logo` repo  |
| `-f`, `--format`            | `.png`   | Output format (auto-detected from the file extension if omitted)     |
| `-bw`, `--border-width`     | `2`      | Width of the white border surrounding the QR code                    |
| `-bs`, `--box-size`         | `10`     | Size (in pixels) of each box/module of the QR code                   |

## 🚀 Usage

```bash
# See available formats
python qr_generator.py --list-formats

# Standard generation (format inferred from the extension)
python qr_generator.py "https://example.com" file_name.pdf

# Force a format different from the extension
python qr_generator.py "https://example.com" file_name --format pdf

# If no format is specified (neither via extension nor option), the output defaults to .png
python qr_generator.py "https://example.com" file_name

# Other options
python qr_generator.py "https://example.com" --format pdf --box-size 15 --border-width 1 file_name
```

## 🤝 Contributing

Contributions are welcome! If you'd like to help improve MyFancyQR:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to your branch (`git push origin feature/my-feature`)
5. Open a Pull Request

Please make sure to open an issue first for major changes, so we can discuss what you'd like to do.

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.
See the [LICENSE](LICENSE) file for details.

## 📬 Contact

Maintained by [@leomrtinez](https://github.com/leomrtinez)   
📧 Email: [click_to_send@gmail.com](mailto:martinez.leo.work@gmail.com)   
🐞 For bugs or feature requests, please [open an issue](https://github.com/leomrtinez/MyFancyQR/issues).