"""Shared temporal with lazy public exports."""

__all__ = ['GeometryStabilizer', 'RightDisplayStabilizer', 'LeftDisplayStabilizer']

def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    from dmi_computer_vision.src import dmi
    return getattr(dmi, name)
