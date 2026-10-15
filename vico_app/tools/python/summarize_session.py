#!/usr/bin/env python3
"""Streaming, offline-only summary of schema-1/2 Vico session TSV; does not infer road accuracy."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

class Stats:
    def __init__(self):
        self.n = 0; self.total = 0; self.low = None; self.high = None
        self.bins = Counter()
    def add(self, value):
        if not math.isfinite(value): return
        self.n += 1; self.total += value
        self.low = value if self.low is None else min(self.low, value)
        self.high = value if self.high is None else max(self.high, value)
        bound = next((b for b in (0, 5, 10, 20, 50, 100, 250, 500, 1000, 5000) if value <= b), 'above_5000')
        self.bins[str(bound)] += 1
    def result(self):
        return dict(count=self.n, mean=self.total / self.n if self.n else None, min=self.low, max=self.high,
                    upper_bound_buckets=dict(self.bins))

def summarize(path):
    schemas = {}; counts = Counter(); invalid = Counter(); metrics = {}; modes = Counter()
    display_units = Counter()
    audio_windows = Counter()
    footer = None; schema = None; rows = 0; unit_candidates = 0; truncated = 0
    def metric(name, value):
        metrics.setdefault(name, Stats()).add(value)
    with Path(path).open('rb') as source:
        # readline cap prevents a damaged/untrusted file from defeating bounded memory.
        while True:
            raw = source.readline(8193)
            if not raw: break
            if len(raw) > 8192: raise ValueError('Record exceeds schema-1/2 maximum line size')
            if not raw.endswith(b'\n'):
                truncated += 1; break
            try: line = raw.decode('utf-8').rstrip('\r\n')
            except UnicodeDecodeError:
                invalid['encoding'] += 1; continue
            if line.startswith('# vico_session_schema='):
                schema = line.split('=', 1)[1].split()[0]
                if schema not in ('1', '2'): raise ValueError('Unsupported schema ' + schema)
            elif line.startswith('# end '):
                footer = dict(item.split('=', 1) for item in line[6:].split())
            elif line.startswith('# '):
                name, sep, value = line[2:].partition('=')
                if name in ('CONFIG', 'CONTROL', 'GPS', 'IMU', 'MODEL', 'UI_ACK', 'EVENT', 'AUDIO') and sep:
                    schemas[name] = value.split(',')
            else:
                columns = line.split('\t'); kind = columns[0]
                if schema not in ('1', '2') or kind not in schemas or len(columns) != len(schemas[kind]) + 4:
                    invalid['shape'] += 1; continue
                try:
                    for x in columns[1:4]:
                        if int(x) < 0: raise ValueError()
                    fields = {}
                    for name, value in zip(schemas[kind], columns[4:]):
                        v = None if not value else int(value) if (name.endswith(('_ns', '_id')) or name == 'blocks_in_window') else float(value)
                        if isinstance(v, float) and not math.isfinite(v): raise ValueError()
                        fields[name] = v
                except ValueError:
                    invalid['number'] += 1; continue
                counts[kind] += 1; rows += 1
                def latency(a, b, key):
                    if fields.get(a) is None or fields.get(b) is None: return
                    delta = fields[b] - fields[a]
                    if delta < 0: invalid[key + '_negative'] += 1
                    else: metric(key, delta / 1e6)
                if kind in ('GPS', 'IMU'):
                    latency('source_ns', 'receive_ns', kind.lower() + '_source_to_receive_ms')
                if kind == 'MODEL':
                    latency('publish_ns', 'consume_ns', 'publish_to_consume_ms')
                    mode = fields.get('source_mode')
                    modes[str(int(mode)) if mode in (0, 1, 2, 3, 4) else 'UNKNOWN_OR_OTHER'] += 1
                    raw_speed = fields.get('raw_speed_mps'); selected = fields.get('selected_speed_mps')
                    model = fields.get('model_speed_mps'); ui = fields.get('ui_speed_kmh')
                    if raw_speed is not None and selected is not None:
                        metric('selected_minus_raw_kmh', (selected - raw_speed) * 3.6)
                        if abs(raw_speed) > 1 and min(abs(selected/raw_speed-3.6), abs(selected/raw_speed-1/3.6)) < 0.05:
                            unit_candidates += 1
                    if selected is not None and model is not None: metric('model_minus_selected_kmh', (model-selected)*3.6)
                    if model is not None and ui is not None: metric('ui_minus_model_kmh', ui-model*3.6)
                if kind == 'UI_ACK':
                    latency('dispatch_ns', 'received_render_ack_ns', 'ui_ack_roundtrip_ms')
                    unit = fields.get('display_unit_code')
                    display_units[{1: 'KMH', 2: 'MPH'}.get(unit, 'UNKNOWN')] += 1
                    value = fields.get('display_value'); normalized = fields.get('display_speed_kmh')
                    if value is not None and normalized is not None and unit in (1, 2):
                        metric('ui_display_normalization_error_kmh', normalized - value * (1.609344 if unit == 2 else 1))
                if kind == 'AUDIO':
                    blocks = fields.get('blocks_in_window')
                    if blocks is None: audio_windows['unknown_windows'] += 1
                    elif blocks <= 0: invalid['audio_window_blocks'] += 1
                    else:
                        audio_windows['known_windows'] += 1
                        audio_windows['covered_blocks'] += blocks
                    for key in ('render_duration_ns', 'write_duration_ns'):
                        if fields.get(key) is not None: metric(key.replace('_ns', '_ms'), fields[key] / 1e6)
    if schema not in ('1', '2'): raise ValueError('Missing supported schema header')
    return dict(schema=int(schema), complete_footer=footer is not None, recoverable_partial=footer is None or '.partial.' in str(path),
                rows=rows, kinds=dict(counts), invalid=dict(invalid), truncated_tail_lines=truncated,
                footer=footer, metrics={k:v.result() for k,v in metrics.items()}, source_modes=dict(modes),
                possible_unit_ratio_rows=unit_candidates, display_units=dict(display_units), audio_windows=dict(audio_windows),
                limits=['Synthetic/local pipeline evidence only; external synchronized reference speed is required for road accuracy.',
                        'UI acknowledgement roundtrip is not display photon or speaker/acoustic latency.',
                        'AUDIO with blocks_in_window reports render/write/peak window maxima and frame/clip sums; audio_block_id identifies the last block.',
                        'Drops and missing footer make counts incomplete; capacity/IO failure must be shown in app.'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('path'); args = parser.parse_args()
    print(json.dumps(summarize(args.path), indent=2, ensure_ascii=False))
