"""Fail-closed validation of real capture bytes. Python 3.10+ standard library only."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import struct


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_json(path):
    def reject(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    value = json.loads(path.read_text(encoding='utf-8'), parse_constant=reject)
    def finite(item):
        if isinstance(item, float):
            require(math.isfinite(item), 'Nonfinite JSON number')
        elif isinstance(item, dict):
            for child in item.values():
                finite(child)
        elif isinstance(item, list):
            for child in item:
                finite(child)
    finite(value)
    return value


def rows(path, frames, columns):
    size = columns * 4
    require(path.stat().st_size == frames * size, f'{path.name}: byte count mismatch')
    with path.open('rb') as stream:
        while block := stream.read(size * 4096):
            for row in struct.iter_unpack('<' + 'f' * columns, block):
                require(all(math.isfinite(x) for x in row), f'{path.name}: nonfinite sample')
                yield row


def verify(root):
    root = Path(root)
    data = read_json(root / 'capture.json')
    physical = read_json(root / 'physical-validity.json')  # Mandatory, never optional.
    require(data['model'] == 'generic_crossplane_v8_ls_example_NOT_HELLCAT', 'Unexpected model')
    require(data['scene'] == 'smoke', 'Only frozen smoke is included in step 1')
    require(data['qualification'] == 'OFFLINE_SYNTHETIC_MECHANISM_ONLY', 'Unexpected qualification')
    duration = data['duration_s']
    require(isinstance(duration, (int, float)) and 0 < duration <= 60, 'Invalid duration')
    require(abs(duration * 100 - round(duration * 100)) < 1e-9, 'Duration is not 10ms aligned')
    require((data['physics_fs'], data['audio_fs'], data['warmup_s'], data['seed']) ==
            (10000, 44100, 5, 24817), 'Unexpected frozen capture settings')
    ns, na = round(duration * 10000), round(duration * 44100)
    require(data['physics_frames'] == ns and data['audio_frames'] == na, 'Frame count mismatch')
    require(data['all_steps'] == ns + 50000, 'Warmup + capture step count mismatch')
    for row in rows(root / 'pressure-input.f32le', ns, 18):
        require(all(x > 0 for x in row[:16]), 'Absolute cylinder/runner pressure must be positive Pa')
    low, high = math.inf, -math.inf
    for (omega,) in rows(root / 'signed-omega.f32le', ns, 1):
        require(omega < 0, 'Crankshaft must rotate clockwise (signed omega < 0) throughout capture')
        low, high = min(low, omega), max(high, omega)
    require(physical['cw_all_capture'] is True, 'CW summary is false')
    require(physical['initialization'] == 'upstream_starter0.5s_then_hold_dyno', 'Incorrect starter contract')
    require(math.isclose(physical['min_omega_rad_s'], low, rel_tol=1e-13) and
            math.isclose(physical['max_omega_rad_s'], high, rel_tol=1e-13), 'Rotation summary disagrees with bytes')
    require(0 < physical['lit_cylinder_steps'] <= ns * 8, 'No combustion or impossible lit-cylinder aggregate')
    clips, peak = 0, 0.0
    for raw, post, leveled, output, gain, clipped in rows(root / 'audio-taps.f32le', na, 6):
        require(clipped in (0, 1), 'Invalid clamp flag')
        rounded = math.floor(leveled + .5) if leveled >= 0 else math.ceil(leveled - .5)
        require(bool(clipped) == (rounded > 32767 or rounded < -32768), 'Clamp flag mismatch')
        require(output == min(32767, max(-32768, rounded)) / 32768, 'PCM output mismatch')
        require(gain >= 0, 'Negative leveler gain')
        clips += int(clipped)
        peak = max(peak, abs(output))
    require(clips == data['clip_count'] and peak == data['final_peak'], 'Audio summary mismatch')
    tables = {}
    map_max = 0.0
    required_columns = {
        'state.csv': ['t_s', 'rpm', 'target_rpm', 'speed_control', 'throttle_plate', 'map_pa', 'cycle_angle_rad', 'integrated_cycles'],
        'dyno.csv': ['t_s', 'torque_nm'],
    }
    for name, columns in required_columns.items():
        with (root / name).open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames == columns, f'{name}: incorrect columns')
            table = list(reader)
        require(len(table) == round(duration * 100), f'{name}: row count mismatch')
        for index, row in enumerate(table):
            require(None not in row and all(value is not None for value in row.values()), f'{name}: malformed row')
            values = {key: float(value) for key, value in row.items()}
            require(all(math.isfinite(x) for x in values.values()), f'{name}: nonfinite value')
            require(abs(values['t_s'] - (index + 1) * .01) < 1e-10, f'{name}: endpoint timing mismatch')
            if name == 'state.csv':
                require(0 < values['map_pa'] < 2 * 101325, 'Gross NA manifold-pressure sanity failure')
                require(values['rpm'] > 0, 'Nonpositive RPM')
                require(values['target_rpm'] == 910 and values['speed_control'] == .08, 'Frozen smoke setpoint changed')
                map_max = max(map_max, values['map_pa'])
        tables[name] = {'rows': len(table), 'first_t_s': .01, 'last_t_s': duration}
    files = ['capture.json', 'physical-validity.json', 'pressure-input.f32le',
             'signed-omega.f32le', 'audio-taps.f32le', 'state.csv', 'dyno.csv']
    return {'status': 'BASIC_OFFLINE_SANITY_ONLY_NOT_ACOUSTIC_OR_OEM_QUALIFICATION',
            'physics_frames': ns, 'audio_frames': na, 'all_streams_finite': True,
            'absolute_pressures_positive': True, 'signed_rotation_all_negative': True,
            'min_omega_rad_s': low, 'max_omega_rad_s': high,
            'clip_count': clips, 'final_peak': peak, 'map_max_pa': map_max, 'tables': tables,
            'sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.capture)
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'clip_count': result['clip_count']}))
