import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {buildSite} from '../tools/build.mjs';
import {fixtureSources} from './fixtures.mjs';

test('the published entrypoint has a bundled SVG favicon', async () => {
  const out = path.join(await fs.mkdtemp(path.join(os.tmpdir(), 'vico-web-favicon-')), 'dist');
  const sources = fixtureSources();
  await buildSite({out, testOnly: true, readBlob: async relative => sources.get(relative)});
  const html = await fs.readFile(path.join(out, 'index.html'), 'utf8');
  assert.match(html, /<link rel="icon" type="image\/svg\+xml" href="\.\/favicon\.svg">/);
  assert.match(await fs.readFile(path.join(out, 'favicon.svg'), 'utf8'), /<svg\b/);
});
