"""Compaction contracts: semantic fidelity, bounded drift, resets and streaming."""
from copy import deepcopy
import io
import json
import unittest

from dmi_computer_vision.tests.test_validation import frame
from dmi_computer_vision.src.dmi.output.json_writer import CompactWriter, compact_state


class CompactWriterTest(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.writer = CompactWriter(self.stream, {"source": "synthetic"})
        self.index = 0

    def emit(self, item):
        item = deepcopy(item)
        item.update(frame_index=self.index, timestamp=self.index / 10)
        self.writer.process(item)
        self.index += 1
        return json.loads(self.stream.getvalue().splitlines()[-1])

    def test_snapshot_is_compact_preserves_null_unknown_icons_and_coordinates(self):
        item = frame()
        item['right_display']['state'] = 'unknown'
        before = deepcopy(item)
        record = self.emit(item)
        self.assertEqual(record['type'], 'snapshot')
        self.assertEqual(record['right_display']['buttons'], {'digit_1': [30, 30]})
        self.assertEqual(record['right_display']['fields']['input']['value'], '12')
        self.assertEqual(record['left_display']['boxes']['box_1'], {'center': [30, 30], 'icon': None})
        self.assertEqual(record['right_display']['geometry']['corners'], item['right_display']['geometry']['corners'])
        self.assertNotIn('oriented_box', record['right_display']['geometry'])
        self.assertEqual(item, before)

    def test_jitter_suppressed_but_cumulative_movement_emitted(self):
        item = frame()
        self.emit(item)
        for offset in [1, 2, -1, 4, 5]:
            item['right_display']['buttons']['digit_1']['center'] = [30 + offset, 30]
            self.emit(item)
        self.assertEqual(self.writer.records, 2)
        item['right_display']['buttons']['digit_1']['center'] = [36, 30]
        delta = self.emit(item)
        self.assertEqual(delta['type'], 'update')
        self.assertEqual(delta['right_display'], {'buttons': {'digit_1': [36, 30]}})
        self.assertNotIn('left_display', delta)

    def test_values_nulls_titles_icons_and_disappearing_buttons(self):
        item = frame(); self.emit(item)
        item['right_display']['data_field']['value'] = None
        delta = self.emit(item)
        self.assertEqual(delta['right_display'], {'fields': {'driver_id': {'value': None}}})
        item['left_display']['boxes']['box_1']['icon'] = 'level1_icon'
        self.assertEqual(self.emit(item)['left_display'], {'boxes': {'box_1': {'icon': 'level1_icon'}}})
        item['right_display']['title']['text'] = 'Changed'
        self.assertEqual(self.emit(item)['right_display'], {'title': 'Changed'})
        item['right_display']['buttons'] = {}
        record = self.emit(item)
        self.assertEqual(record['type'], 'snapshot')
        self.assertEqual(record['right_display']['buttons'], {})

    def test_state_visibility_and_reset_force_snapshot(self):
        item = frame(); self.emit(item)
        item['right_display']['state'] = 'unknown'
        self.assertEqual(self.emit(item)['type'], 'snapshot')
        item['right_display']['visibility'] = 'occluded'
        self.assertEqual(self.emit(item)['type'], 'snapshot')
        item.update(frame_index=3, timestamp=.3)
        self.writer.process(item, force_snapshot=True)
        self.assertEqual(json.loads(self.stream.getvalue().splitlines()[-1])['type'], 'snapshot')

    def test_flush_before_end_and_invalid_values_do_not_corrupt_prior_lines(self):
        class Stream(io.StringIO):
            flushes = 0
            def flush(self):
                self.flushes += 1
        stream = Stream(); logger = CompactWriter(stream, {})
        item = frame(); logger.process(item)
        self.assertEqual(stream.flushes, 2)
        before = stream.getvalue()
        item.update(frame_index=1, timestamp=float('nan'))
        with self.assertRaises(ValueError): logger.process(item)
        self.assertEqual(stream.getvalue(), before)
        for tolerance in [-1, float('nan'), float('inf'), True]:
            with self.assertRaises(ValueError): CompactWriter(io.StringIO(), {}, geometry_tolerance=tolerance)
        logger.finish(processed_frames=1, stop_reason='interrupted')
        self.assertEqual(json.loads(stream.getvalue().splitlines()[-1])['last_frame'], 0)

    def test_long_unchanged_sequence_has_only_one_snapshot_and_end_coverage(self):
        item = frame()
        for _ in range(1000): self.emit(item)
        self.writer.finish(processed_frames=1000, error=None)
        records = [json.loads(line) for line in self.stream.getvalue().splitlines()]
        self.assertEqual([r['type'] for r in records], ['session_start', 'snapshot', 'session_end'])
        self.assertEqual(records[-1]['last_frame'], 999)
        self.assertAlmostEqual(records[-1]['last_timestamp'], 99.9)

    def test_completed_lines_survive_abrupt_process_exit(self):
        import os
        from pathlib import Path
        import subprocess
        import tempfile
        import sys
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'partial.jsonl'
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
            subprocess.run([sys.executable, '-c',
                'import os,sys; from dmi.output.json_writer import CompactWriter; '
                's=open(sys.argv[1], "w"); w=CompactWriter(s, {"source":"test"}); '
                'w.emit({"type":"snapshot","frame":0}); os._exit(0)', str(output)],
                env=env, check=True)
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([r['type'] for r in records], ['session_start', 'snapshot'])
