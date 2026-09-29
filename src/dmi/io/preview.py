"""OpenCV live preview adapter."""

import cv2

from dmi.detection.display_geometry import Frame


class LivePreview:
    """Main-thread OpenCV display; coordinates in saved results stay full size."""

    def __init__(self) -> None:
        self._opened = False
        self._name = "DMI live - Q or Escape to stop"

    def show(self, image: Frame) -> bool:
        if not self._opened:
            cv2.namedWindow(self._name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self._name, 1000, 750)
            self._opened = True
        cv2.imshow(self._name, image)
        key = cv2.waitKey(1) & 0xFF
        return key not in (ord('q'), ord('Q'), 27) and cv2.getWindowProperty(
            self._name, cv2.WND_PROP_VISIBLE) >= 1

    def close(self) -> None:
        if self._opened:
            cv2.destroyWindow(self._name)
            self._opened = False
