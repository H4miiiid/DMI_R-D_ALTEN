"""Measured glyph-style separation under a common camera colour cast; no OCR."""
import cv2
import numpy as np


def classify(samples: dict, baseline: dict) -> dict:
    """Use two separated glyph populations only when colour and lightness agree.

    A common red/blue channel gain scales both populations alike. Names/order do
    not participate. Without two coherent styles, preserve the original reader.
    """
    features = {}
    for name, (interior, foreground) in samples.items():
        pixels = interior[foreground > 0].astype(float)
        if len(pixels) >= 20:
            features[name] = (float(np.median(pixels[:, 2]/np.maximum(pixels[:, 0], 1))),
                              float(np.median(cv2.cvtColor(interior, cv2.COLOR_BGR2GRAY)[foreground > 0])))
    if len(features) < 4:
        return baseline
    ordered = sorted(features, key=lambda n: features[n][0])
    ratios = np.array([features[n][0] for n in ordered])
    relative_gaps = np.diff(ratios)/np.maximum(ratios[1:], .01)
    split = int(np.argmax(relative_gaps))+1
    low, high = ordered[:split], ordered[split:]
    # Reject isolated outliers, weak separations and incompatible brightness.
    if (min(len(low), len(high)) < 2 or relative_gaps[split-1] < .25
            or min(features[n][1] for n in high) <= max(features[n][1] for n in low)*1.1):
        return baseline
    result = dict(baseline)
    for name in low:
        result[name] = False
    for name in high:
        result[name] = True
    return result
