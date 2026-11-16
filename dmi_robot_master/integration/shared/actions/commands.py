"""Validated actions using the existing master controller and wire protocol."""

from dmi_robot_common.command_validation import validate_command
from dmi_robot_common.DmiMessages import DmiMessages
from dmi_robot_master.DmiControllerMaster import DmiControllerMaster


class RobotCommands:
    def __init__(
        self, controller: DmiControllerMaster, xy_limits_mm: tuple[int, int],
        timeout_seconds: float = 60.0,
    ) -> None:
        if len(xy_limits_mm) != 2 or any(
            type(value) is not int or not 0 < value < 2**31
            for value in xy_limits_mm
        ):
            raise ValueError("Configure two positive integer XY limits in mm")
        if not 0 < timeout_seconds < float("inf"):
            raise ValueError("Timeout must be finite and positive")
        self.controller = controller
        self.xy_limits_mm = xy_limits_mm
        self.timeout_seconds = timeout_seconds

    def _execute(self, command: DmiMessages, data: list[int]) -> tuple[bool, list[int]]:
        validate_command(command, data, self.xy_limits_mm)
        return self.controller.manage_action(DmiControllerMaster.Action(
            command, data, DmiMessages.DONE, 0, self.timeout_seconds, 0.001,
        ))

    def move(self, x_mm: int, y_mm: int) -> tuple[bool, list[int]]:
        """Move to absolute XY with Z requested at zero; no press."""
        return self._execute(DmiMessages.MOVE, [x_mm, y_mm, 0])

    def press(self, x_mm: int, y_mm: int, duration_ms: int) -> tuple[bool, list[int]]:
        """Request one press. Failure never retries; DONE is not UI verification."""
        return self._execute(DmiMessages.MOVE_AND_CLICK, [x_mm, y_mm, duration_ms])
