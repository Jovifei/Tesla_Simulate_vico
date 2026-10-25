"""Only patch the archived experimental copy; never the original engine-sim."""
from pathlib import Path
import hashlib, json

root = Path(__file__).resolve().parent
changes = []
def patch(rel, transform):
    p = root / rel
    before = p.read_bytes()
    text = before.decode().replace('\r\r\n', '\n').replace('\r\n', '\n').replace('\r', '\n')
    after = transform(text).encode()
    p.write_bytes(after)
    changes.append(dict(path=rel, before=hashlib.sha256(before).hexdigest(),
                        after=hashlib.sha256(after).hexdigest()))

patch('upstream/include/scs.h', lambda s: s)
def clock(s):
    start = s.index('    const double targetLatency = getSynthesizerInputLatencyTarget();')
    end = s.index('    if (m_steps > 0)', start)
    s = s[:start] + '    // Offline adapter: exact dt, without realtime queue-latency speed changes.\n\n' + s[end:]
    s = s.replace('    m_synthesizer.destroy();',
                  '    m_synthesizer.destroy();\n    delete[] m_dynoTorqueSamples;\n    m_dynoTorqueSamples = nullptr;')
    return s
patch('upstream/src/simulator.cpp', clock)
def source(s):
    s = '#include "../../offline_taps.h"\n' + s
    return s.replace('    synthesizer().writeInput(m_exhaustFlowStagingBuffer);',
        '    if (offline::source) offline::source(m_engine, m_exhaustFlowStagingBuffer, exhaustSystemCount);\n'
        '    synthesizer().writeInput(m_exhaustFlowStagingBuffer);')
patch('upstream/src/piston_engine_simulator.cpp', source)
def audio(s):
    s = '#include "../../offline_taps.h"\n' + s
    s = s.replace('    float signal = 0;', '    float signal = 0;\n    float rawSum = 0;')
    s = s.replace('        const float r_0 =',
                  '        rawSum += m_inputChannels[i].transferBuffer[inputSample];\n        const float r_0 =')
    s = s.replace('    return static_cast<int16_t>(r_int);',
        '    if (offline::audio) offline::audio(rawSum, signal, v_leveled,\n'
        '        static_cast<float>(r_int) / 32768.0f, m_levelingFilter.getAttenuation(),\n'
        '        (v_leveled > INT16_MAX || v_leveled < INT16_MIN) ? 1.0f : 0.0f);\n'
        '    return static_cast<int16_t>(r_int);')
    return s
patch('upstream/src/synthesizer.cpp', audio)
(root / 'capture-patches.json').write_text(json.dumps(changes, indent=2)+'\n')
print(json.dumps({'experimental_patches': len(changes), 'original_repo_modified': False}))
