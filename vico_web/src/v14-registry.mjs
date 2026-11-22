// The fingerprint is supplied by the M0 projection, never by the network response.
export function permittedPackage(registry, legacyKey, actualSha, verifyOwner = () => false) {
  if (registry?.schema_version !== '1.0' || !Array.isArray(registry.vehicles) ||
      !/^[a-f0-9]{64}$/.test(actualSha || '')) return false;
  const matches = registry.vehicles.filter(v => v?.legacy_key === legacyKey);
  if (matches.length !== 1) return false;
  const vehicle = matches[0];
  if (vehicle.catalog_status !== 'TARGET_LOCKED' || vehicle.readiness_status !== 'ACOUSTIC_CALIBRATED' ||
      !Array.isArray(vehicle.sound_packages)) return false;
  return vehicle.sound_packages.some(p => {
    const a = p?.owner_audition;
    return typeof p.route_id === 'string' && p.route_id.length > 0 &&
      typeof p.package_id === 'string' && p.package_id.length > 0 && p.package_sha256 === actualSha &&
      a?.status === 'PASS' && a.route_id === p.route_id && a.package_id === p.package_id &&
      a.package_sha256 === actualSha && typeof a.evidence_ref === 'string' && a.evidence_ref.trim().length > 0 &&
      verifyOwner(a, p, vehicle) === true;
  });
}

export async function loadV14Registry(base, expectedSha, checkedFetch) {
  if (!/^[a-f0-9]{64}$/.test(expectedSha || '')) return null;
  try {
    const bytes = await checkedFetch(new URL('v14-vehicle-registry.json', base), expectedSha, {maxBytes:65536});
    const registry = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes));
    return registry?.schema_version === '1.0' && Array.isArray(registry.vehicles) ? registry : null;
  } catch (_) { return null; }
}
