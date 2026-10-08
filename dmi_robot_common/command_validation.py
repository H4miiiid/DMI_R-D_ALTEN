"""Validation of existing integer command payloads; no protocol changes."""

from dmi_robot_common.DmiMessages import DmiMessages


def validate_command(
    command: DmiMessages, data: list[int], xy_limits_mm: tuple[int, int]
) -> None:
    """Reject invalid payloads before robot calls. Upper XY limits are exclusive."""
    lengths = {
        DmiMessages.MOVE: 3,
        DmiMessages.MOVE_AND_CLICK: 3,
        DmiMessages.TAKE_PICTURES: 3,
        DmiMessages.GET_PICTURES: 0,
        DmiMessages.GET_CURRENT_POSITION: 0,
        DmiMessages.INITIALIZE: 0,
        DmiMessages.RETURN_TO_ZERO: 0,
        DmiMessages.ACK: 0,
    }
    if command not in lengths or len(data) != lengths[command]:
        raise ValueError("Unsupported command or incorrect payload length")
    if any(type(value) is not int or not -(2**31) <= value < 2**31 for value in data):
        raise ValueError("Payload values must be signed 32-bit integers")
    if command in (DmiMessages.MOVE, DmiMessages.MOVE_AND_CLICK):
        x_mm, y_mm, third = data
        max_x_mm, max_y_mm = xy_limits_mm
        if not (0 <= x_mm < max_x_mm and 0 <= y_mm < max_y_mm):
            raise ValueError("Absolute XY target is outside configured limits in mm")
        if third < 0:
            raise ValueError("Z or press duration must be nonnegative")
    if command == DmiMessages.TAKE_PICTURES:
        camera, count, duration_ms = data
        if camera < 0 or count <= 0 or duration_ms < 0:
            raise ValueError("Invalid picture request")
