/** Offline V0 control: actual Vico renderer + unchanged shipped bank, not a vehicle recording.
 * node render_vico_trace.mjs --core ACTUAL/src/core.mjs --dist REAL_BUILD
 *   --capture SCENE --out NEW_DIR --vehicle hellcat_v6 --ambient-pa 101325
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

export function mapLoadProxy(mapPa, ambientPa) {
  if (!Number.isFinite(mapPa) || !Number.isFinite(ambientPa) || ambientPa <= 0)
    throw new Error('MAP must be finite and ambient pressure must be finite and positive');
  return Math.max(.05, Math.min(1, mapPa / ambientPa));
}
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const finite = (value, label) => {
  if (!Number.isFinite(value)) throw new Error(`Nonfinite ${label}`);
  return value;
};
async function sourceGraph(file, result = {}) {
  const real = await fs.realpath(file);
  if (result[real]) return result;
  const bytes = await fs.readFile(real);
  result[real] = sha(bytes);
  const dependencies = [...bytes.toString('utf8').matchAll(/(?:from\s*|import\s*)['"](\.[^'"]+)['"]/g)];
  for (const [, ref] of dependencies) await sourceGraph(path.resolve(path.dirname(real), ref), result);
  return result;
}
function readState(bytes, physicsRate, duration) {
  const lines = bytes.toString('utf8').trim().split(/\r?\n/);
  const header = lines.shift().split(',');
  for (const key of ['t_s', 'rpm', 'map_pa']) if (!header.includes(key)) throw new Error(`Missing state field ${key}`);
  const rows = lines.map((line, row) => {
    const columns = line.split(',');
    if (columns.length !== header.length) throw new Error(`Bad CSV row ${row + 2}`);
    const data = Object.fromEntries(header.map((key, i) => [key, finite(Number(columns[i]), `state ${key}`)]));
    if (data.rpm < 0) throw new Error('Negative measured RPM');
    // Capture records post-step state under the beginning-of-step timestamp.
    // Correct by one actual physics step, never by a guessed sound/RPM phase.
    return {...data, endpoint: data.t_s + 1 / physicsRate};
  });
  if (rows.length < 2) throw new Error('Insufficient actual state rows');
  for (let i = 1; i < rows.length; i++)
    if (rows[i].endpoint <= rows[i - 1].endpoint) throw new Error('Non-increasing capture timestamps');
  if (rows[0].endpoint < 0 || rows[0].endpoint > .02 || Math.abs(rows.at(-1).endpoint - duration) > 2 / physicsRate)
    throw new Error('State endpoint coverage does not match capture duration');
  return rows;
}
function parse(argv) {
  const allowed = new Set(['--core', '--dist', '--capture', '--out', '--vehicle', '--ambient-pa']);
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    if (!allowed.has(key) || !argv[i + 1] || args[key] !== undefined) throw new Error(`Invalid CLI argument ${key}`);
    args[key] = argv[i + 1];
  }
  for (const key of allowed) if (args[key] === undefined) throw new Error(`${key} required`);
  return args;
}
async function main() {
  const started = performance.now(), cpuStarted = process.cpuUsage();
  const args = parse(process.argv.slice(2));
  const corePath = await fs.realpath(path.resolve(args['--core']));
  const dist = await fs.realpath(path.resolve(args['--dist']));
  const capture = await fs.realpath(path.resolve(args['--capture']));
  const out = path.resolve(args['--out']), ambient = Number(args['--ambient-pa']);
  mapLoadProxy(0, ambient);
  const captureBytes = await fs.readFile(path.join(capture, 'capture.json'));
  const stateBytes = await fs.readFile(path.join(capture, 'state.csv'));
  const meta = JSON.parse(captureBytes), duration = finite(Number(meta.duration_s), 'duration');
  const physicsRate = finite(Number(meta.physics_fs), 'physics sample rate');
  if (duration <= 0 || duration > 60 || physicsRate <= 0) throw new Error('Invalid capture timebase');
  const rows = readState(stateBytes, physicsRate, duration);
  const core = await import(pathToFileURL(corePath).href);
  const loaderPath = await fs.realpath(path.resolve(path.dirname(corePath), '../tools/render.mjs'));
  const {diskBank} = await import(pathToFileURL(loaderPath).href);
  const loaded = await diskBank(dist, args['--vehicle']);
  const {bank, identity, testOnly} = loaded;
  if (testOnly !== false || bank.sampleRate !== 48000) throw new Error('V0 requires a real 48k shipped six-car build, not fixtures');
  const renderer = new core.BankRenderer(bank, 'NORMAL_SEAM_ENVELOPE_V1');
  const sourceHashes = await sourceGraph(loaderPath);
  await sourceGraph(corePath, sourceHashes);
  const scriptBytes = await fs.readFile(fileURLToPath(import.meta.url));
  const frames = Math.round(duration * bank.sampleRate);
  const output = Buffer.alloc(frames * 4);
  const state = {timeS: 0, rpm: rows[0].rpm, load: mapLoadProxy(rows[0].map_pa, ambient),
    shiftGain: 1, muted: false, shiftTrigger: false, afterfireTrigger: false};
  const axes = {rpm: [renderer.rpms[0], renderer.rpms.at(-1)], load: [renderer.loads[0], renderer.loads.at(-1)]};
  const counts = {mapProxyLowFrames: 0, mapProxyHighFrames: 0, bankRpmLowFrames: 0, bankRpmHighFrames: 0,
    bankLoadLowFrames: 0, bankLoadHighFrames: 0, initialEndpointHoldFrames: 0, finalEndpointHoldFrames: 0};
  const range = {requestedRpm: [Infinity, -Infinity], mapPa: [Infinity, -Infinity], mappedLoad: [Infinity, -Infinity]};
  const track = (key, value) => { range[key][0] = Math.min(range[key][0], value); range[key][1] = Math.max(range[key][1], value); };
  let at = 0, peak = 0, excess = 0, nonfinite = 0, square = 0;
  const renderStarted = performance.now();
  // One renderer/readhead for the whole scene. No reset, extra warmup or source seed.
  for (let i = 0; i < frames; i++) {
    const t = i / bank.sampleRate;
    while (at + 1 < rows.length && rows[at + 1].endpoint <= t) at++;
    const a = rows[at], b = rows[Math.min(at + 1, rows.length - 1)];
    let mix = b.endpoint > a.endpoint ? (t - a.endpoint) / (b.endpoint - a.endpoint) : 0;
    if (t < rows[0].endpoint) { mix = 0; counts.initialEndpointHoldFrames++; }
    if (t > rows.at(-1).endpoint) { mix = 0; counts.finalEndpointHoldFrames++; }
    mix = Math.max(0, Math.min(1, mix));
    const rpm = a.rpm + mix * (b.rpm - a.rpm), map = a.map_pa + mix * (b.map_pa - a.map_pa);
    const proxy = mapLoadProxy(map, ambient), ratio = map / ambient;
    counts.mapProxyLowFrames += +(ratio < .05); counts.mapProxyHighFrames += +(ratio > 1);
    counts.bankRpmLowFrames += +(rpm < axes.rpm[0]); counts.bankRpmHighFrames += +(rpm > axes.rpm[1]);
    counts.bankLoadLowFrames += +(proxy < axes.load[0]); counts.bankLoadHighFrames += +(proxy > axes.load[1]);
    track('requestedRpm', rpm); track('mapPa', map); track('mappedLoad', proxy);
    state.timeS = t; state.rpm = rpm; state.load = proxy;
    renderer.setState(state);
    const sample = renderer.next();
    if (!Number.isFinite(sample)) { nonfinite++; throw new Error('Nonfinite actual Vico output; no repair permitted'); }
    peak = Math.max(peak, Math.abs(sample)); square += sample * sample;
    if (Math.abs(sample) > core.PEAK_CONTRACT) excess++;
    output.writeFloatLE(sample, i * 4);
  }
  const stats = renderer.stats();
  const cpu = process.cpuUsage(cpuStarted);
  let gitHead = null;
  try { gitHead = execFileSync('git', ['-C', path.dirname(corePath), 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim(); } catch {}
  const receipt = {
    schema: 'vico.offline.v0.engine-sim-control.v1',
    scope: 'VICO_DIGITAL_RENDERER_WITH_GENERIC_ENGINE_SIM_STATE_PROXY_NOT_OEM_OR_PHYSICAL_LOAD_EQUIVALENCE',
    vehicle: bank.vehicleKey, mode: 'NORMAL_SEAM_ENVELOPE_V1', sampleRate: bank.sampleRate, sample_rate: bank.sampleRate,
    frames, duration_s: duration, sha256: sha(output), sourceCommit: gitHead,
    algorithmPortHeaderCommit: core.SOURCE_SHA, corePath, sourceHashes,
    tool: {path: fileURLToPath(import.meta.url), sha256: sha(scriptBytes)}, dist, identity, testOnly,
    capture: {path: capture, model: meta.model, scene: meta.scene, warmup_s: meta.warmup_s,
      capture_json_sha256: sha(captureBytes), state_csv_sha256: sha(stateBytes), physics_fs: physicsRate,
      stateRows: rows.length, firstRawTimestamp_s: rows[0].t_s, lastRawTimestamp_s: rows.at(-1).t_s},
    mapping: {rpm: 'actual captured engine rpm, linearly interpolated between corrected measured endpoints',
      load: 'clamp(actual_MAP_pa / declared_ambient_pa, .05, 1); a named proxy, not Vico/engine-sim physical load equality',
      ambient_pa: ambient, timestampCorrection_s: 1 / physicsRate,
      timebase: 'capture t_s labels beginning of completed physics step; add 1/physics_fs before audio-clock interpolation',
      endpointPolicy: 'hold first actual measured endpoint before first row; no invented RPM/MAP; report held frames',
      note: 'Offline interpolation may use the following measured row and is not a causal live-input predictor',
      bankAxes: axes, counts, measuredRanges: range},
    warmup: {v0_extra_warmup_frames: 0, v0_extra_warmup_seconds: 0,
      stats_scope: 'all output frames only; no pre-output rendering',
      rendererIntrinsicEnvelopeWarmupFrames: bank.sampleRate / 4,
      distinction: 'engine-sim physical warmup is excluded upstream; its state was not captured, so V0 does not invent an equivalent warmup'},
    rendering: {singleRenderer: true, resets: 0, startup: false, shift: false, afterfire: false,
      sourceOrFixedGainChanged: false, postGain: 1, normalization: 'none'},
    stats, outputHealth: {frames, peak, rms: Math.sqrt(square / frames), nonfinite, aboveContractFrames: excess,
      contract: core.PEAK_CONTRACT, valid: nonfinite === 0 && excess === 0 && stats.nonfinite === 0 && stats.hardClips === 0},
    performance: {render_wall_s: (performance.now() - renderStarted) / 1000, total_wall_s: (performance.now() - started) / 1000,
      cpu_user_ms: cpu.user / 1000, cpu_system_ms: cpu.system / 1000, max_rss_kib: process.resourceUsage().maxRSS},
    qualification: 'DESCRIPTIVE_BASELINE_CONTROL_ONLY_NOT_SOUND_FIX_OR_ACOUSTIC_ACCEPTANCE'
  };
  // Never overwrite a result directory or an old capture.
  await fs.mkdir(path.dirname(out), {recursive: true});
  await fs.mkdir(out);
  await fs.writeFile(path.join(out, 'capture.f32le'), output, {flag: 'wx'});
  await fs.writeFile(path.join(out, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n', {flag: 'wx'});
  console.log(JSON.stringify({scene: meta.scene, out, frames, sha256: receipt.sha256, stats, mappingCounts: counts, health: receipt.outputHealth}));
  if (!receipt.outputHealth.valid) throw new Error('Actual Vico output violates safety contract; unchanged evidence retained');
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  main().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; });
