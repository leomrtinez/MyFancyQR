"""Shared fixtures.

The real encoder is the ``qrcode`` library. When it is not installed (e.g. in
a minimal CI image), the ``encoder`` fixture substitutes OpenCV's QR encoder
so that the rendering, SVG, logo and diagnostics code paths can still be
exercised end to end. Tests that need ``qrcode`` itself are marked with
``requires_qrcode``.
"""

from __future__ import annotations

import importlib.util

import pytest

from myfancyqr import core

HAS_QRCODE = importlib.util.find_spec("qrcode") is not None
HAS_CV2 = importlib.util.find_spec("cv2") is not None

requires_qrcode = pytest.mark.skipif(not HAS_QRCODE, reason="qrcode library not installed")
requires_cv2 = pytest.mark.skipif(not HAS_CV2, reason="opencv not installed")


def _opencv_encode(data: str, ecc: str):
    import cv2
    import numpy as np

    params = cv2.QRCodeEncoder_Params()
    params.correction_level = {
        "L": cv2.QRCodeEncoder_CORRECT_LEVEL_L,
        "M": cv2.QRCodeEncoder_CORRECT_LEVEL_M,
        "Q": cv2.QRCodeEncoder_CORRECT_LEVEL_Q,
        "H": cv2.QRCodeEncoder_CORRECT_LEVEL_H,
    }[ecc]
    img = cv2.QRCodeEncoder.create(params).encode(data)
    dark = img < 128
    ys, xs = np.nonzero(dark)
    sym = dark[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]  # strip quiet zone
    n = sym.shape[0]
    version = (n - 17) // 4
    return sym.tolist(), version


@pytest.fixture(autouse=True)
def encoder(monkeypatch):
    """Use OpenCV as a stand-in encoder when ``qrcode`` is unavailable."""
    if HAS_QRCODE:
        yield "qrcode"
    elif HAS_CV2:
        monkeypatch.setattr(core, "_encode", _opencv_encode)
        yield "opencv"
    else:
        pytest.skip("neither qrcode nor opencv is installed")
