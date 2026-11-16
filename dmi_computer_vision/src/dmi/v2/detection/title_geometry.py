"""Version 2 lock geometry from the current measured title glyph bounds."""
import numpy as np
from numpy.typing import NDArray


def tight_title_quad(x1: int, y1: int, x2: int, y2: int) -> NDArray[np.float32]:
    """Convert half-open glyph extents to the existing inclusive title corners."""
    return np.array([[x1, y1], [x2-1, y1], [x2-1, y2-1], [x1, y2-1]], np.float32)
