"""Backward-compatible entry point for MyFancyQR v1 users.

    python qr_generator.py https://example.com out.png -pc navy

is equivalent to ``python -m myfancyqr ...`` (or ``myfancyqr ...`` once the
package is installed). The implementation lives in :mod:`myfancyqr.cli`.
"""

from myfancyqr.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
