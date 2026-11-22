import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const [source, expected] = process.argv.slice(2);
if (!source || !/^[a-f0-9]{64}$/.test(expected || '')) throw Error('Usage: node project-v14-registry.mjs SOURCE EXPECTED_SHA256');
const bytes = await readFile(source);
if (createHash('sha256').update(bytes).digest('hex') !== expected) throw Error('M0 source fingerprint mismatch');
const data = JSON.parse(bytes.toString('utf8'));
if (data.schema_version !== '1.0' || !Array.isArray(data.vehicles)) throw Error('Invalid M0 registry');
const root = new URL('../../', import.meta.url);
await writeFile(new URL('vico_web/v14-vehicle-registry.json',root),bytes);
await writeFile(new URL('vico_app/Project/android/app/src/main/assets/v14-vehicle-registry.json',root),bytes);
await writeFile(new URL('vico_web/src/v14-projection.mjs',root),`// Fingerprint of the source M0 registry; it does not approve any package.\nexport const REGISTRY_SHA256 = '${expected}';\n`);
await writeFile(new URL('vico_app/Project/android/app/src/main/java/com/vico/simulator/vehicle/V14Projection.kt',root),
  `package com.vico.simulator.vehicle\n\n// Fingerprint of the source M0 registry; it does not approve any package.\ninternal const val V14_REGISTRY_SHA256 = "${expected}"\n`);
