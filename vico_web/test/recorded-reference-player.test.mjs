import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {RecordedReferencePlayer} from '../src/recorded-reference.mjs';

const bytes=Buffer.from('good');
const reference={schema:'vico.recorded.reference.v1',scope:'REFERENCE_ONLY',id:'reference-a',
  title:'Reference A',file:'assets/recorded-references/a.wav',sampleRate:48000,channels:1,frames:1,
  source:{author:'Author',license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/'},
  identity:{vehicle:'Test vehicle',state:'UNKNOWN',synchronizedRpmLoad:false,OEMQualification:false},
  automaticLoop:false,sha256:createHash('sha256').update(bytes).digest('hex')};
globalThis.fetch=async()=>new Response(bytes);
globalThis.document={createElement:()=>({})};

test('verified reference playback only becomes available after SHA verification',async()=>{
  const player=new RecordedReferencePlayer(reference,fetch,new URL('http://localhost/'));
  assert.equal(player.verified,false);
  await player.play();
  assert.equal(player.verified,true);
  await player.prepare();
  assert.equal(player.verified,true);
  const playable=await player.play();
  assert.equal(playable.verified,true);
  assert.equal(playable.loop,false);
  assert.equal(Buffer.from(playable.bytes).toString(),bytes.toString());
});
