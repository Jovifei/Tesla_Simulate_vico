import tempfile
import unittest
from pathlib import Path
from summarize_session import summarize

class SummaryTest(unittest.TestCase):
    def summary(self, data, partial=False):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / ('records.partial.tsv' if partial else 'records.tsv')
            p.write_bytes(data.encode()); return summarize(p)
    def test_exact_ns_and_partial_recovery(self):
        s = self.summary('# vico_session_schema=1\n# GPS=source_ns,receive_ns\nGPS\t9007199254740993\t1\t0\t9007199254740993\t9007199254740994\nGPS\t2', True)
        self.assertEqual(0.000001, s['metrics']['gps_source_to_receive_ms']['mean'])
        self.assertEqual(1, s['rows']); self.assertTrue(s['recoverable_partial']); self.assertEqual(1, s['truncated_tail_lines'])
    def test_70_vs_40_stage(self):
        s = self.summary('# vico_session_schema=1\n# MODEL=publish_ns,consume_ns,raw_speed_mps,selected_speed_mps,model_speed_mps,ui_speed_kmh,source_mode\nMODEL\t3\t1\t0\t0\t100000000\t19.444444444444443\t19.444444444444443\t11.11111111111111\t40\t1\n# end state=COMPLETE written=1\n')
        self.assertAlmostEqual(-30, s['metrics']['model_minus_selected_kmh']['mean'])
        self.assertAlmostEqual(0, s['metrics']['ui_minus_model_kmh']['mean'])
        self.assertEqual(100, s['metrics']['publish_to_consume_ms']['mean'])
        self.assertTrue(s['complete_footer'])
    def test_v2_config_control_model_compatible(self):
        s = self.summary('# vico_session_schema=2\n# CONFIG=config_revision_id,unit_code\nCONFIG\t1\t0\t0\t9007199254740993\t1\n# CONTROL=control_frame_id,publish_ns\nCONTROL\t2\t44\t3\t44\t9007199254740993\n# MODEL=raw_speed_mps,selected_speed_mps,model_speed_mps,ui_speed_kmh\nMODEL\t3\t44\t3\t20\t20\t10\t36\n# end state=COMPLETE written=3\n')
        self.assertEqual(2, s['schema']); self.assertEqual(3, s['rows'])
        self.assertEqual(-36, s['metrics']['model_minus_selected_kmh']['mean'])
        self.assertEqual(1, s['kinds']['CONFIG']); self.assertEqual(1, s['kinds']['CONTROL'])

    def test_mph_display_is_not_mistaken_for_speed_error(self):
        s = self.summary('# vico_session_schema=2\n# UI_ACK=dispatch_ns,received_render_ack_ns,display_speed_kmh,display_unit_code,display_value\nUI_ACK\t100\t1\t0\t1\t2\t70.006464\t2\t43.5\n# end state=COMPLETE written=1\n')
        self.assertEqual({'MPH': 1}, s['display_units'])
        self.assertAlmostEqual(0, s['metrics']['ui_display_normalization_error_kmh']['mean'])

    def test_audio_windows_are_counted_without_inventing_per_block_timings(self):
        s = self.summary('# vico_session_schema=2\n# AUDIO=audio_block_id,render_duration_ns,write_duration_ns,blocks_in_window\nAUDIO\t100\t1\t0\t9007199254740993\t5000000\t10000000\t5\n# end state=COMPLETE written=1\n')
        self.assertEqual({'known_windows': 1, 'covered_blocks': 5}, s['audio_windows'])
        self.assertEqual(1, s['metrics']['render_duration_ms']['count'])
        self.assertEqual(5, s['metrics']['render_duration_ms']['max'])

    def test_reject_unknown_version_and_oversize(self):
        with self.assertRaises(ValueError): self.summary('# vico_session_schema=99\n')
        with self.assertRaises(ValueError): self.summary('# vico_session_schema=1\n' + 'x'*8193)

if __name__ == '__main__': unittest.main()
