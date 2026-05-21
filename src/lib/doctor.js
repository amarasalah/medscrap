// Accessors over the unified doctor shape (see scripts/schema.md).

export function primaryAddress(d) {
  return d?.addresses?.[0] || null;
}

export function primaryPhone(d) {
  return d?.phones?.[0] || null;
}

export function allCities(d) {
  return (d?.addresses || []).map(a => a.city).filter(Boolean);
}

export function allRegions(d) {
  return (d?.addresses || []).map(a => a.region).filter(Boolean);
}

export function allDepartments(d) {
  return (d?.addresses || []).map(a => a.department).filter(Boolean);
}

export function matchesAnyAddress(d, predicate) {
  return (d?.addresses || []).some(predicate);
}

export function searchableText(d) {
  const addrs = (d?.addresses || []).map(a => a.address).join(' ');
  const phones = (d?.phones || []).map(p => p.formatted + ' ' + p.raw).join(' ');
  return [d?.name, addrs, phones, d?.email].filter(Boolean).join(' ').toLowerCase();
}

export const COUNTRY_LABELS = {
  FR: 'France',
  GB: 'United Kingdom',
  ES: 'España',
};
