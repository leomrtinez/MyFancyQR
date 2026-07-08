import argparse
import sys
from PIL import Image, ImageDraw
import qrcode
import qrcode.image.svg

SUPPORTED_FORMATS = ["png", "pdf", "svg", "jpg", "jpeg", "bmp", "webp", "tiff", "eps"]
AVAILABLE_LOGOS = {"Github": "logo/Github.png",
                    "Scholar": "logo/Scholar.png",
                    "Youtube": "logo/Youtube.png",
                    "Wikipedia": "logo/Wikipedia.png"}  # Example set of available logos

def generate_qrcode_without_logo(data: str, output_path: str = None, fmt: str = "png", box_size: int = 10, border_width: int = 2):
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
        return None


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
    return None




def generate_qrcode_with_logo(
    data: str,
    output_path: str,
    fmt: str = "png",
    box_size: int = 10,
    border_width: int = 2,
    logo_path: str = None,
):
    """
    Generate a QR code with a logo embedded in the center (on a white
    circular background for better contrast), and save it in the
    requested format.
    """
    fmt = fmt.lower()

    if not output_path.endswith(f".{fmt}"):
        output_path = f"{output_path}.{fmt}"

    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {fmt} (use --list-formats to see the list)")

    if fmt == "svg":
        raise ValueError("Logo embedding is not supported for the SVG format")

    if logo_path in AVAILABLE_LOGOS.keys():
        logo_path = AVAILABLE_LOGOS[logo_path]

    # Higher error correction is required so the QR code stays
    # scannable even with part of it covered by the logo
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border_width,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_width, qr_height = qr_img.size

    try:
        logo = Image.open(logo_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Logo file not found: {logo_path}")

    # Resize logo to ~25% of the QR code width
    logo_size = int(qr_width * 0.25)
    logo = logo.resize((logo_size, logo_size))

    # --- Draw a white circle behind the logo for contrast ---
    circle_radius = int(logo_size * 0.65)  # slightly larger than the logo
    circle_center = (qr_width // 2, qr_height // 2)

    draw = ImageDraw.Draw(qr_img)
    draw.ellipse(
        [
            (circle_center[0] - circle_radius, circle_center[1] - circle_radius),
            (circle_center[0] + circle_radius, circle_center[1] + circle_radius),
        ],
        fill="white",
    )

    # Compute position to center the logo
    pos = (
        (qr_width - logo_size) // 2,
        (qr_height - logo_size) // 2,
    )

    # Paste logo (with transparency mask if the logo has an alpha channel)
    if logo.mode in ("RGBA", "LA"):
        qr_img.paste(logo, pos, mask=logo)
    else:
        qr_img.paste(logo, pos)

    if fmt == "png":
        qr_img.save(output_path)
    elif fmt == "pdf":
        qr_img.save(output_path, "PDF")
    elif fmt in ("jpg", "jpeg"):
        qr_img.save(output_path, "JPEG", quality=95)
    elif fmt == "bmp":
        qr_img.save(output_path, "BMP")
    elif fmt == "webp":
        qr_img.save(output_path, "WEBP")
    elif fmt == "tiff":
        qr_img.save(output_path, "TIFF")
    elif fmt == "eps":
        qr_img.save(output_path, "EPS")

    print(f"QR code with logo generated: {output_path}")





def main():
    parser = argparse.ArgumentParser(
        description="Generate a QR code from a text or a link."
    )

    # Input URL or text and output file path are positional arguments
    parser.add_argument("url", default="https://github.com/leomrtinez/MyFancyQR.git", nargs="?", help="Text or URL to encode")
    
    # Output file path is optional; if not provided, it defaults to "qrcode" with the format inferred from the extension or defaulting to PNG.
    parser.add_argument("output", default="qrcode", nargs="?", help="Output file path (e.g. qrcode or qrcode.png). The format will be inferred from the extension if not specified.")

    # Optional arguments for format, box size, border width, and logo inclusion
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

    parser.add_argument(
        "-l",
        "--logo",
        type=str,
        default=None,
        help="Path to the logo image to include in the QR code (default: None)", 
        choices=list(AVAILABLE_LOGOS.keys())
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


    if not args.logo:
        generate_qrcode_without_logo(args.url, args.output, fmt, args.box_size, args.border_width)
    else:
        generate_qrcode_with_logo(args.url, args.output, fmt, args.box_size, args.border_width, args.logo)



if __name__ == "__main__":
    main()