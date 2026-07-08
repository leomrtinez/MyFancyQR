import argparse
import sys

import qrcode
import qrcode.image.svg

SUPPORTED_FORMATS = ["png", "pdf", "svg", "jpg", "jpeg", "bmp", "webp", "tiff", "eps"]


def generate_qrcode(data: str, output_path: str = None, fmt: str = "png", box_size: int = 10, border_width: int = 2):
    """
    Generate a QR code from a text/URL and save it in the requested format.
    """
    if not output_path.endswith(f".{fmt}"):
        output_path = f"{output_path}.{fmt}"


    fmt = fmt.lower()

    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {fmt} (use --list-formats to see the list)")

    if fmt == "svg":
        # Native vector generation (scalable without quality loss)
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(data, image_factory=factory)
        img.save(output_path)
        print(f"QR code generated: {output_path}")
        return


    # Bitmap formats (handled via Pillow)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border_width,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    if fmt == "png":
        img.save(output_path)
    elif fmt == "pdf":
        # Pillow can't save mode "1" (pure black & white) directly as PDF
        img.convert("RGB").save(output_path, "PDF")
    elif fmt in ("jpg", "jpeg"):
        img.convert("RGB").save(output_path, "JPEG", quality=95)
    elif fmt == "bmp":
        img.save(output_path, "BMP")
    elif fmt == "webp":
        img.save(output_path, "WEBP")
    elif fmt == "tiff":
        img.save(output_path, "TIFF")
    elif fmt == "eps":
        img.convert("RGB").save(output_path, "EPS")

    print(f"QR code generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a QR code from a text or a link."
    )
    parser.add_argument("url", default="https://github.com/leomrtinez/MyFancyQR.git", nargs="?", help="Text or URL to encode")
    parser.add_argument("output", default="qrcode", nargs="?", help="Output file path (e.g. qrcode or qrcode.png). The format will be inferred from the extension if not specified.")

    parser.add_argument(
        "-f", "--format",
        help="Output format (auto-detected from the file extension if not provided)", 
        default="png",
        choices=SUPPORTED_FORMATS
    )

    parser.add_argument(
        "-ls",
        "--list-formats",
        action="store_true",
        help="Show the list of supported formats and exit"
    )

    parser.add_argument(
        "-bs",
        "--box-size",
        type=int,
        default=10,
        help="Box size for the QR code (default: 10)"
    )

    parser.add_argument(
        "-bw",
        "--border-width",
        type=int,
        default=2,
        help="Border width for the QR code (default: 2)"
    )

    args = parser.parse_args()

    if args.list_formats:
        print("Supported formats:")
        for f in SUPPORTED_FORMATS:
            print(f"  - {f}")
        sys.exit(0)

    if not args.url:
        parser.error("the 'url' argument is required (unless using --list-formats)")
    
    # ASCII mode doesn't need an output file
    fmt = args.format
    if not fmt:
        if args.output:
            fmt = args.output.rsplit(".", 1)[-1]  # infer format from the extension
        else :
            fmt = "png"  # default format


    if not args.output:
        parser.error("the 'output' argument is required")

    generate_qrcode(args.url, args.output, fmt, args.box_size, args.border_width)


if __name__ == "__main__":
    main()