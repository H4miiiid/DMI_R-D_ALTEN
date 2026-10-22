"""Launch live detection and label commands using saved deployment settings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


DEFAULT_CONFIG = Path(__file__).with_name('run_robot.json')
OUTPUT_ROOT = Path('/tmp/dmi_robot')
PATH_OPTIONS = {'robot_config', 'calibration', 'calibration_context', 'hardware_checks'}
VALUE_OPTIONS = PATH_OPTIONS | {
    'bridge_url', 'processing', 'rotation', 'transport', 'mode',
    'evidence_tolerance_px', 'max_x_mm', 'max_y_mm',
}
FLAG_OPTIONS = {'preview'}


def session_arguments(config_path: Path, name: str) -> list[str]:
    """Translate one deployment config into the existing press_label CLI."""
    if not name or name in {'.', '..'} or '/' in name or '\\' in name:
        raise ValueError('Use a single output folder name, for example test_01')
    config_path = config_path.expanduser().resolve()
    with config_path.open(encoding='utf-8') as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValueError('Launcher configuration must be a JSON object')
    unknown = config.keys() - VALUE_OPTIONS - FLAG_OPTIONS
    if unknown:
        raise ValueError(f'Unknown launcher settings: {", ".join(sorted(unknown))}')
    missing = sorted(key for key in VALUE_OPTIONS if config.get(key) in (None, ''))
    if missing:
        raise ValueError(f'Configure {config_path} first; missing: {", ".join(missing)}')
    directory = OUTPUT_ROOT / name
    for path in (directory, directory.with_name(name + '_progress.log'),
                 directory.with_name(name + '_button_tests.jsonl')):
        if path.exists():
            raise ValueError(f'Choose a new test name; output already exists: {path}')
    arguments = ['--output-dir', str(directory)]
    for key in sorted(VALUE_OPTIONS):
        value = config[key]
        if isinstance(value, (dict, list, bool)):
            raise ValueError(f'{key} must be a scalar value')
        if key in PATH_OPTIONS:
            path = Path(str(value)).expanduser()
            if not path.is_absolute():
                path = config_path.parent / path
            path = path.resolve()
            if not path.is_file():
                raise ValueError(f'{key} file does not exist: {path}')
            value = path
        arguments.extend(('--' + key.replace('_', '-'), str(value)))
    preview = config.get('preview', True)
    if type(preview) is not bool:
        raise ValueError('preview must be true or false')
    if preview:
        arguments.append('--preview')
    return arguments


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_name', help='New test folder under /tmp/dmi_robot')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        arguments = session_arguments(args.config, args.output_name)
    except (OSError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    # Reuse the complete existing session, including all physical execution gates.
    from dmi_robot_master.integration.press_label import main as press_main
    return press_main(arguments)


if __name__ == '__main__':
    raise SystemExit(main())
