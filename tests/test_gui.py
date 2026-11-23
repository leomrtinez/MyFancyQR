"""Tests for the GUI's Python side (no window, no browser needed)."""

from __future__ import annotations

import base64
import io
import json
import sys
import threading
import types
import urllib.request

import pytest
from PIL import Image

from myfancyqr.gui import api as gui_api
from myfancyqr.gui.api import DEFAULT_PARAMS, Api, config_from_params


@pytest.fixture
def api(tmp_path):
    return Api(browser_mode=True, presets_path=tmp_path / "presets.json")


def test_config_from_params_defaults_and_mapping():
    cfg = config_from_params({"ecc": "q", "logo": "Github", "logoScale": 20})
    assert cfg.error_correction == "Q"
    assert cfg.logo == "Github" and cfg.logo_scale == pytest.approx(0.20)
    assert cfg.border == DEFAULT_PARAMS["border"] == 4
    assert config_from_params({"ecc": "auto", "logo": None}).error_correction is None


def test_state_exposes_logos_and_formats(api):
    state = api.get_state()
    assert state["ok"] and state["browserMode"]
    assert "Github" in state["logos"]
    assert "jpeg" not in state["formats"] and "svg" in state["formats"]


def test_render_returns_preview_and_info(api):
    res = api.render({"data": "https://example.com", "fill": "navy", "logo": "Github"})
    assert res["ok"], res
    assert res["image"].startswith("data:image/png;base64,")
    img = Image.open(io.BytesIO(base64.b64decode(res["image"].split(",", 1)[1])))
    assert max(img.size) <= gui_api.PREVIEW_MAX + 200
    assert res["fillHex"] == "#000080"
    assert res["info"]["error_correction"] == "H"
    assert res["logoName"] == "Github"


def test_render_reports_errors_instead_of_raising(api):
    res = api.render({"fill": "notacolour"})
    assert res["ok"] is False and "colour" in res["error"].lower()


def test_presets_roundtrip(api, tmp_path):
    assert api.list_presets()["presets"] == {}
    res = api.save_preset("Navy", {**DEFAULT_PARAMS, "fill": "#0a3d91", "data": "secret"})
    assert res["ok"] and res["presets"]["Navy"]["fill"] == "#0a3d91"
    assert "data" not in res["presets"]["Navy"]  # the content is not part of a style
    assert json.loads((tmp_path / "presets.json").read_text())["Navy"]["fill"] == "#0a3d91"
    assert api.save_preset("  ", DEFAULT_PARAMS)["ok"] is False
    assert api.save_preset("Bad", {"fill": "nope"})["ok"] is False
    assert api.delete_preset("Navy")["presets"] == {}


def test_upload_logo_and_use_it(api):
    buf = io.BytesIO()
    Image.new("RGBA", (64, 32), (200, 0, 0, 255)).save(buf, "PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    res = api.upload_logo("../../evil name.png", data_url)
    assert res["ok"], res
    assert "/" not in res["name"] and ".." not in res["path"].split("myfancyqr-logos-")[1]
    assert api.render({"logo": res["path"]})["ok"]
    assert api.upload_logo("x.png", "data:text/plain,hello")["ok"] is False


@pytest.mark.parametrize("fmt", ["png", "svg", "pdf"])
def test_export_in_browser_mode_returns_download(api, fmt):
    res = api.export({**DEFAULT_PARAMS, "format": fmt})
    assert res["ok"] and res["filename"] == f"qrcode.{fmt}"
    assert res["download"].startswith("data:")


def test_copy_outside_macos_offers_fallback(api):
    res = api.copy_image(DEFAULT_PARAMS)
    assert res["ok"] is False and res["fallbackImage"].startswith("data:image/png")


def test_dev_server_api_and_static_files():
    from myfancyqr.gui.devserver import make_server

    server = make_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        resp = urllib.request.urlopen(f"{base}/")
        assert resp.url.endswith("/index.html?mode=browser")  # redirect adds the mode flag
        assert "<title>MyFancyQR</title>" in resp.read().decode()
        req = urllib.request.Request(
            f"{base}/api/render", data=json.dumps([{"data": "hello"}]).encode(), method="POST"
        )
        assert json.loads(urllib.request.urlopen(req).read())["ok"] is True
        bad = urllib.request.Request(f"{base}/api/_matrix", data=b"[]", method="POST")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(bad)
        assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_app_main_with_stub_pywebview(monkeypatch):
    """main() wires the window without needing a real pywebview/macOS."""
    from myfancyqr.gui import app

    calls = {}

    class Event:
        def __init__(self):
            self.handlers = []

        def __iadd__(self, fn):
            self.handlers.append(fn)
            return self

    class Window:
        def __init__(self):
            self.events = types.SimpleNamespace(before_show=Event(), shown=Event())

    def create_window(title, **kwargs):
        calls["title"], calls["kwargs"] = title, kwargs
        calls["window"] = Window()
        return calls["window"]

    def start(debug=False):
        for fn in calls["window"].events.before_show.handlers:
            fn()  # PyObjC absent here: must degrade silently
        calls["started"] = True

    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(create_window=create_window, start=start))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert app.main([]) == 0
    assert calls["started"] and calls["title"] == "MyFancyQR"
    assert calls["kwargs"]["vibrancy"] is True
    assert calls["kwargs"]["url"].endswith("index.html")
    assert isinstance(calls["kwargs"]["js_api"], Api)
    assert len(calls["window"].events.before_show.handlers) == 1


def test_app_main_without_pywebview(monkeypatch, capsys):
    from myfancyqr.gui import app

    monkeypatch.setitem(sys.modules, "webview", None)  # makes "import webview" fail
    assert app.main([]) == 1
    assert "pip install" in capsys.readouterr().err
