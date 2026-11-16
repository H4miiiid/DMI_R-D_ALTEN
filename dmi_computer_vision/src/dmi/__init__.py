"""DMI video understanding, with lazy exports for configuration-only callers."""
from importlib import import_module

# Keep the established public names without loading OpenCV/OCR for settings.
_EXPORTS = {
    'FrameProcessor': ('shared.pipeline.frame_processor', 'FrameProcessor'),
    'VideoRunSummary': ('shared.pipeline.video', 'VideoRunSummary'),
    'DisplayGeometry': ('shared.detection.display_geometry', 'DisplayGeometry'),
    'GeometryStabilizer': ('shared.temporal.smoothing', 'GeometryStabilizer'),
    'RightDisplayStabilizer': ('shared.temporal.smoothing', 'RightDisplayStabilizer'),
    'LeftDisplayStabilizer': ('shared.temporal.left_tracking', 'LeftDisplayStabilizer'),
    'analyze_left_display': ('shared.detection.left_display', 'analyze_left_display'),
    'annotate_frame': ('shared.output.annotation', 'annotate_frame'),
    'analyze_right_display': ('shared.detection.right_display', 'analyze_right_display'),
    'detect_displays': ('shared.detection.display_geometry', 'detect_displays'),
    'process_frame': ('shared.pipeline.frame_processor', 'process_frame'),
    'process_video': ('shared.pipeline.video', 'process_video'),
    'rectify_display': ('shared.detection.display_geometry', 'rectify_display'),
}
__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(f'{__name__}.{module}'), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
