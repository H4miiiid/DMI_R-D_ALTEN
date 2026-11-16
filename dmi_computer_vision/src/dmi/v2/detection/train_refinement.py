"""Version 2 measured train-control corrections; shared OCR/mapping are injected."""
from collections.abc import Callable

import cv2
import numpy as np
from numpy.typing import NDArray

from dmi_computer_vision.src.dmi.shared.detection.display_geometry import DisplayGeometry, Frame


def refine_train_buttons(
    expanded: Frame, recognized: dict[str, NDArray], *, geometry: DisplayGeometry,
    frame_shape: tuple[int, int], size: tuple[int, int], margin: int, validation: bool,
    edge_buttons: dict | None, recognize_buttons: Callable[..., dict[str, NDArray]],
    refine_cells: Callable[..., dict[str, NDArray]], region_result: Callable[..., dict],
) -> dict[str, NDArray]:
    """Retain valid cells and bound retries to freshly measured outliers."""
    width, height = size
    # Preserve every control that already passes the original-pixel
    # containment check. Reuse this crop for one measured-face retry.
    parent = np.rint(geometry.corners).astype(np.float32)
    def protrusion(points):
        native = region_result(points-margin, geometry, frame_shape)['corners']
        return max(0., -min(cv2.pointPolygonTest(parent, tuple(map(float, p)), True) for p in native))
    invalid_validation = {name for name, points in recognized.items()
                          if validation and name in {'no', 'close'} and protrusion(points) > 1}
    if invalid_validation:
        # One local, freshly recognized alternative. Preserve every
        # already valid fit and accept a replacement only when its
        # measured enclosure agrees better with the measured display.
        alternatives = recognize_buttons(expanded, validation=True, contrast_fallback=True,
            display_bounds=(margin, margin, width-1+margin, height-1+margin),
            search_regions=tuple(recognized[name] for name in sorted(invalid_validation)))
        for name in invalid_validation:
            if name in alternatives and protrusion(alternatives[name]) < protrusion(recognized[name]):
                recognized[name] = alternatives[name]
    measured = recognized.copy() if edge_buttons is not None else {}
    outside = {name: points for name, points in recognized.items()
        if any(cv2.pointPolygonTest(parent, tuple(map(float, p)), True) < -1
               for p in region_result(points-margin, geometry, frame_shape)['corners'])}
    refined = refine_cells(expanded, outside,
        (margin, margin, width-1+margin, height-1+margin)) if outside else {}
    refined = {name: points for name, points in refined.items()
        if all(cv2.pointPolygonTest(parent, tuple(map(float, p)), True) >= -1
               for p in region_result(points-margin, geometry, frame_shape)['corners'])}
    recognized = {name: points for name, points in recognized.items() if name not in outside}
    recognized.update(refined)
    if edge_buttons is not None:
        edge_buttons.update({name: region_result(points-margin, geometry, frame_shape)
                             for name, points in measured.items() if name not in recognized})
    return recognized


def retry_train_label(gray: NDArray, reader: Callable[..., str | None]) -> str | None:
    """One current-pixel Otsu retry; the reader retains its confidence checks."""
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    binary = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    return reader(binary, (0, 0, binary.shape[1], binary.shape[0]))
