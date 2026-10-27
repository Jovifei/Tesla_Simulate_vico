const HASH = /^[a-f0-9]{64}$/i;
const MEASURED = 'MEASURED';

function fail(reasons) {
  return {status: 'INSUFFICIENT_EVIDENCE', reasons: [...new Set(reasons)], trainingRegionCount: 0, holdoutRegionCount: 0};
}

function requiredHash(value, name, reasons) {
  if (typeof value !== 'string' || !HASH.test(value)) reasons.push(`${name} must be a SHA-256 hex string`);
}

function measuredState(region, reasons) {
  const state = region?.state;
  if (!state || state.rpm !== MEASURED || state.load !== MEASURED || state.gear !== MEASURED) {
    reasons.push(`${region?.id ?? 'region'} requires measured rpm, load, and gear`);
  }
  if (state?.phase720?.source !== MEASURED || state.phase720.verified !== true) {
    reasons.push(`${region?.id ?? 'region'} requires verified measured 720-degree phase`);
  }
  const trace = region?.stateTrace;
  requiredHash(trace?.sha256, `${region?.id ?? 'region'} state trace`, reasons);
  if (!Number.isFinite(trace?.sampleRateHz) || trace.sampleRateHz <= 0 || !Number.isSafeInteger(trace.rows) || trace.rows <= 0) {
    reasons.push(`${region?.id ?? 'region'} state trace needs a positive rate and row count`);
  }
  if (trace?.synchronizedToPcm !== true) reasons.push(`${region?.id ?? 'region'} state trace is not synchronized to PCM`);
}

export function validateRecordedStateContract(contract) {
  const reasons = [];
  if (!contract || contract.schema !== 'vico.recorded.state-contract.v1') reasons.push('unsupported state contract schema');
  if (typeof contract?.vehicleKey !== 'string' || !contract.vehicleKey) reasons.push('vehicleKey is required');
  const source = contract?.source;
  if (!source || typeof source !== 'object') reasons.push('source identity is required');
  else {
    if (typeof source.sourceId !== 'string' || !source.sourceId) reasons.push('sourceId is required');
    requiredHash(source.originalSha256, 'original source', reasons);
    requiredHash(source.pcmSha256, 'PCM source', reasons);
    const format = source.format;
    if (!Number.isSafeInteger(format?.sampleRate) || format.sampleRate <= 0 || format.channels !== 1 || format.encoding !== 'F32LE') {
      reasons.push('source format must be mono F32LE with a positive sample rate');
    }
    const license = source.license;
    if (!license || typeof license.spdx !== 'string' || license.redistributionAllowed !== true || typeof license.attribution !== 'string' || !license.attribution) {
      reasons.push('source license must permit redistribution and include attribution');
    }
    const capture = source.capture;
    if (!capture || !capture.micPosition || !capture.environment || capture.micPosition === 'unknown' || capture.environment === 'unknown') {
      reasons.push('capture mic position and environment are required');
    }
  }

  const regions = Array.isArray(contract?.regions) ? contract.regions : [];
  if (!regions.length) reasons.push('at least one measured region is required');
  const ids = new Set();
  let previousEnd = -1;
  for (const region of regions) {
    if (!region || typeof region.id !== 'string' || ids.has(region.id)) reasons.push('region ids must be unique');
    else ids.add(region.id);
    if (!Number.isSafeInteger(region?.startFrame) || !Number.isSafeInteger(region?.endFrame) || region.endFrame <= region.startFrame) {
      reasons.push(`${region?.id ?? 'region'} has invalid frame boundaries`);
    }
    if (Number.isSafeInteger(region?.startFrame) && region.startFrame < previousEnd) reasons.push(`${region.id} overlaps a previous region`);
    if (Number.isSafeInteger(region?.endFrame)) previousEnd = Math.max(previousEnd, region.endFrame);
    measuredState(region, reasons);
  }
  const training = regions.filter(region => region?.role === 'train');
  const holdout = regions.filter(region => region?.role === 'holdout');
  if (!training.length) reasons.push('at least one training region is required');
  if (!holdout.length) reasons.push('an independent holdout region is required');
  const holdoutContract = contract?.holdout;
  requiredHash(holdoutContract?.sourceSha256, 'holdout source', reasons);
  if (holdoutContract?.independent !== true) reasons.push('holdout must be independent');
  const holdoutIds = Array.isArray(holdoutContract?.regionIds) ? holdoutContract.regionIds : [];
  if (!holdoutIds.length || holdoutIds.some(id => !holdout.some(region => region.id === id))) reasons.push('holdout region ids do not match holdout regions');
  if (reasons.length) return {...fail(reasons), vehicleKey: contract?.vehicleKey ?? null};
  return {status: 'ELIGIBLE', reasons: [], vehicleKey: contract.vehicleKey, trainingRegionCount: training.length, holdoutRegionCount: holdout.length};
}
