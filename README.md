# 📷 MyFancyQR

MyFancyQR is a lightweight command-line tool that generates fancy colored QR codes from any text or URL, with support for multiple output formats (PNG, SVG, PDF, JPEG, and more) and customizable styling options.

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
- Customizable box size, border width, logo and even colors
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
conda install matplotlib
```
</details>




Otherwise you can also install it via pip:

<details>
<summary>📦 Using pip</summary>

```bash
pip install qrcode[pil] matplotlib

```
</details>

## ⚙️ Configuration

| Argument                    | Default  | Description                                                          |
|-----------------------------|----------|----------------------------------------------------------------------|
| `url`                       | —        | Text or URL to encode **(required)**                                 |
| `output`                    | `qrcode` | Output file path                                                     |
| `--list-formats`            | —        | List all supported output formats                                    |
| `-l`, `--logo`              | `None`   | Include a logo in the QR code. Some are provided in the `logo` repo  |
| `-f`, `--format`            | `.jpg`   | Output format (auto-detected from the file extension if omitted)     |
| `-bw`, `--border-width`     | `1`      | Width of the white border surrounding the QR code                    |
| `-bs`, `--box-size`         | `25`     | Size (in pixels) of each box/module of the QR code                   |
| `-bc`, `--back-color`       | `white`  | Background color for the QR code (choice between all matplotlib [colors](https://matplotlib.org/stable/gallery/color/named_colors.html))  |
| `-fc`, `--fill-color`       | `black`  | Fill color for the QR code (choice between all matplotlib [colors](https://matplotlib.org/stable/gallery/color/named_colors.html)) |
|

## 🚀 Usage

```bash
# The most simple way to use it. If no output is specified, the default file_name is qrcode
python qr_generator.py https://example.com

# Standard generation. If no format is specified (neither via extension nor option), the defaults format will be set to .jpg
python qr_generator.py https://example.com file_name

# Force a format different from the extension
python qr_generator.py https://example.com file_name --format pdf

# See available formats
python qr_generator.py --list-formats

# Other options
python qr_generator.py https://example.com --format pdf --box-size 15 --border-width 1 file_name

```

### About Logo Add-ons

MyFancyQR allows you to embed a logo in the center of your QR code. Several ready-to-use logos are available in the `./logo` directory.

To use one of the built-in logos, simply specify its name with the `--logo` option:

```bash
# List all available built-in logos
python qr_generator.py --help

# Example: Generate a QR code pointing to a GitHub repository
python qr_generator.py https://github.com/user/repo --logo Github
```

You can also use your own custom logo by providing the path to a PNG file:


```bash
# Example: Generate a QR code pointing to a Wikipedia page
python qr_generator.py https://en.wikipedia.org/wiki/QR_code --logo /Volumes/My_Disk/Images/logo_wikipedia.png file_name

```

**Note:** Custom logos must be provided as `.png` files.

**Warning:** For best results, use a high-resolution image. Small logos may appear pixelated when embedded into the QR code.

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