"""Optional entry point ONLY for a client compiled with flet-dropzone."""
import flet as ft
from dmi_gui import DmiControlPanel


async def main(page: ft.Page):
    DmiControlPanel(page, native_drop=True)


if __name__ == "__main__":
    ft.run(main)
