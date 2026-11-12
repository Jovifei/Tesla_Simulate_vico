"""Apply audited offline-only adaptations to a NEW exported copy, never a checkout."""
import hashlib
import json
from pathlib import Path


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Patch anchor must occur exactly once: {old!r}")
    return text.replace(old, new, 1)


def adapt(root):
    root = Path(root).resolve()
    if not (root / 'snapshot' / 'engine' / 'LICENSE').is_file():
        raise ValueError('Not an exported workspace: pristine snapshot is required')
    if (root / 'capture-patches.json').exists():
        raise FileExistsError('Refusing to patch a workspace twice')
    changes = []

    def patch(rel, transform, reason):
        path = root / rel
        before = path.read_bytes()
        text = before.decode('utf-8').replace('\r\n', '\n')
        after = transform(text).encode('utf-8')
        if after == before:
            raise ValueError(f'Patch made no change: {rel}')
        path.write_bytes(after)
        changes.append({'path': rel, 'reason': reason,
                        'before_sha256': hashlib.sha256(before).hexdigest(),
                        'after_sha256': hashlib.sha256(after).hexdigest()})

    patch('upstream/include/scs.h', lambda s: replace_once(s,
          '../dependencies/submodules/simple-2d-constraint-solver/include/scs.h',
          '../../solver/include/scs.h'), 'Point only the exported copy at the exported solver')

    def clock(text):
        old = '''    const double targetLatency = getSynthesizerInputLatencyTarget();
    if (m_synthesizer.getLatency() < targetLatency) {
        m_steps = static_cast<int>((m_steps + 1) * 1.1);
    }
    else if (m_synthesizer.getLatency() > targetLatency) {
        m_steps = static_cast<int>((m_steps - 1) * 0.9);
        if (m_steps < 0) {
            m_steps = 0;
        }
    }
'''
        text = replace_once(text, old,
            '    // Offline clock: fixed physics steps, no realtime queue-latency feedback.\n')
        return replace_once(text, '    m_synthesizer.destroy();',
            '    m_synthesizer.destroy();\n    delete[] m_dynoTorqueSamples;\n    m_dynoTorqueSamples = nullptr;')

    patch('upstream/src/simulator.cpp', clock, 'Fixed offline clock and release dyno buffer; no physics parameter changes')

    def source(text):
        return '#include "../../offline_taps.h"\n' + replace_once(text,
            '    synthesizer().writeInput(m_exhaustFlowStagingBuffer);',
            '    if (offline::source) offline::source(m_engine, m_exhaustFlowStagingBuffer, exhaustSystemCount);\n'
            '    synthesizer().writeInput(m_exhaustFlowStagingBuffer);')

    patch('upstream/src/piston_engine_simulator.cpp', source, 'Read-only physical capture tap')

    def audio(text):
        text = replace_once(text, '#include "../include/delta.h"\n', '')
        text = '#include "../../offline_taps.h"\n#include <stdexcept>\n' + text
        text = replace_once(text, '    float signal = 0;', '    float signal = 0;\n    float rawSum = 0;')
        text = replace_once(text, '        const float r_0 =',
            '        rawSum += m_inputChannels[i].transferBuffer[inputSample];\n        const float r_0 =')
        # Diagnostic guards do not alter valid samples or any DSP coefficients.
        text = replace_once(text, '    int r_int = std::lround(v_leveled);',
            '    if (!std::isfinite(v_leveled) || v_leveled <= -2147483648.0f || v_leveled >= 2147483648.0f)\n'
            '        throw std::runtime_error("Invalid pre-clamp audio value");\n'
            '    int r_int = std::lround(v_leveled);\n'
            '    const bool clipped = r_int > INT16_MAX || r_int < INT16_MIN;')
        return replace_once(text, '    return static_cast<int16_t>(r_int);',
            '    if (offline::audio) offline::audio(rawSum, signal, v_leveled,\n'
            '        static_cast<float>(r_int) / 32768.0f, m_levelingFilter.getAttenuation(), clipped ? 1.0f : 0.0f);\n'
            '    return static_cast<int16_t>(r_int);')

    patch('upstream/src/synthesizer.cpp', audio,
          'Remove unused GUI include; read-only audio tap, exact integer-clamp flag and invalid-value guard; DSP unchanged')
    (root / 'capture-patches.json').write_text(json.dumps(changes, indent=2) + '\n', encoding='utf-8')
    return changes


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace', type=Path)
    print(json.dumps(adapt(parser.parse_args().workspace), indent=2))
