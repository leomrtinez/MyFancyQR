"""Launch the MyFancyQR desktop window (pywebview).

    python -m myfancyqr.gui                 # native window
    python -m myfancyqr.gui --browser       # same UI in the default browser
    python -m myfancyqr.gui --native-titlebar   # keep the standard macOS title bar

On macOS the window uses the system vibrancy material behind a transparent
web view, and its title bar is merged into the content (traffic lights over
the sidebar) to match the glass design. Both tweaks are best-effort: if
PyObjC refuses them, the app falls back to a standard window.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .. import __version__
from .api import Api

STATIC_DIR = Path(__file__).resolve().parent / "static"
log = logging.getLogger("myfancyqr.gui")


def _unify_macos_titlebar(window, api: Api) -> None:
    """Hide the title and let the content extend under the traffic lights."""
    try:
        from AppKit import NSWindowStyleMaskFullSizeContentView, NSWindowTitleHidden
        from PyObjCTools import AppHelper
    except ImportError:
        log.info("PyObjC not available: keeping the standard title bar")
        return

    def apply() -> None:
        try:
            ns_window = window.native
            ns_window.setTitlebarAppearsTransparent_(True)
            ns_window.setTitleVisibility_(NSWindowTitleHidden)
            ns_window.setStyleMask_(ns_window.styleMask() | NSWindowStyleMaskFullSizeContentView)
            ns_window.setMovableByWindowBackground_(True)
            # The page reads this flag through get_state(). Do not call
            # window.evaluate_js() here: it blocks waiting for the main thread,
            # which is the thread we are running on.
            api._unified_titlebar = True
        except Exception:  # noqa: BLE001 - cosmetic only
            log.exception("could not merge the title bar; keeping the standard one")

    AppHelper.callAfter(apply)  # AppKit must be touched on the main thread


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="myfancyqr-gui", description="MyFancyQR desktop interface.")
    p.add_argument("--browser", action="store_true", help="serve the UI on http://127.0.0.1 instead of a window")
    p.add_argument("--port", type=int, default=8765, help="port for --browser (default: 8765)")
    p.add_argument("--no-open", action="store_true", help="with --browser, do not open a browser tab")
    p.add_argument("--native-titlebar", action="store_true", help="macOS: keep the standard title bar")
    p.add_argument("--debug", action="store_true", help="enable the web inspector and verbose logs")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    if args.browser:
        from .devserver import serve

        return serve(port=args.port, open_browser=not args.no_open)

    try:
        import webview
    except ImportError:
        print(
            "The GUI needs pywebview:\n"
            '    pip install "pywebview>=5"     (or: pip install -e ".[gui]")\n'
            "Alternatively run it in your browser: python -m myfancyqr.gui --browser",
            file=sys.stderr,
        )
        return 1

    api = Api(browser_mode=False)
    is_mac = sys.platform == "darwin"
    window = webview.create_window(
        "MyFancyQR",
        url=str(STATIC_DIR / "index.html"),
        js_api=api,
        width=1180,
        height=760,
        min_size=(960, 640),
        vibrancy=is_mac,
        background_color="#ECECEC",
        text_select=False,
    )
    api._window = window

    if is_mac and not args.native_titlebar:
        event = getattr(window.events, "before_show", None) or window.events.shown
        event += lambda: _unify_macos_titlebar(window, api)

    webview.start(debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
