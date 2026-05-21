// One-shot migration: takes the old flat per-row records in public/doctors.json
// and rewrites them in the unified schema (see schema.md), merging duplicates
// (same lowercased name + city) into single contacts with addresses[]/phones[].
//
// Run: node scripts/migrate-and-dedup.mjs

import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
const dataPath = path.join(__dirname, '..', 'public', 'doctors.json');

const raw = JSON.parse(fs.readFileSync(dataPath, 'utf8'));

function norm(s) {
  return (s || '').toString().trim().toLowerCase();
}

function formatPhone(digits) {
  if (!digits) return null;
  const d = digits.replace(/\D/g, '');
  if (d.length === 10) return d.match(/.{1,2}/g).join(' ');
  return digits;
}

function makeAddress(r) {
  if (!r.address && !r.city) return null;
  return {
    address: r.address || '',
    city: r.city || '',
    postalCode: r.postalCode || '',
    department: r.department || '',
    region: r.region || '',
    lat: r.lat ?? null,
    lng: r.lng ?? null,
    mapsUrl: r.mapsUrl || '',
  };
}

function makePhone(r) {
  if (!r.phoneRaw && !r.phone) return null;
  const rawDigits = (r.phoneRaw || (r.phone || '').replace(/\D/g, '')).trim();
  if (!rawDigits) return null;
  return {
    raw: rawDigits,
    formatted: r.phone || formatPhone(rawDigits) || rawDigits,
  };
}

function addressKey(a) {
  return [norm(a.address), norm(a.city), a.postalCode].join('|');
}

function phoneKey(p) {
  return p.raw;
}

// Group by name + city (any city of the record — old shape is single-city)
const groups = new Map();
for (const r of raw) {
  const key = norm(r.name) + '||' + norm(r.city);
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(r);
}

// Pick best non-empty string from a group (longest wins, ties keep first)
function bestString(rows, field) {
  let best = '';
  for (const r of rows) {
    const v = (r[field] || '').toString();
    if (v.length > best.length) best = v;
  }
  return best;
}

const merged = [];
let idCounter = 1;
for (const rows of groups.values()) {
  const first = rows[0];

  // Collect unique addresses
  const addrMap = new Map();
  for (const r of rows) {
    const a = makeAddress(r);
    if (a) addrMap.set(addressKey(a), a);
  }
  // Collect unique phones
  const phoneMap = new Map();
  for (const r of rows) {
    const p = makePhone(r);
    if (p) phoneMap.set(phoneKey(p), p);
  }

  merged.push({
    id: `fr-${idCounter++}`,
    country: 'FR',
    type: first.type || '',
    name: bestString(rows, 'name') || first.name,
    specialty: bestString(rows, 'specialty'),
    subSpecialty: bestString(rows, 'subSpecialty'),
    profileUrl: bestString(rows, 'profileUrl'),
    email: null,
    phones: [...phoneMap.values()],
    addresses: [...addrMap.values()],
    convention: bestString(rows, 'convention') || null,
  });
}

// Sort by name for stable diffs
merged.sort((a, b) => a.name.localeCompare(b.name, 'fr'));
// Re-number ids in sorted order
merged.forEach((d, i) => { d.id = `fr-${i + 1}`; });

fs.writeFileSync(dataPath, JSON.stringify(merged, null, 0), 'utf8');

console.log(`Input rows:     ${raw.length}`);
console.log(`Output records: ${merged.length}`);
console.log(`Collapsed:      ${raw.length - merged.length}`);
console.log(`Multi-address:  ${merged.filter(d => d.addresses.length > 1).length}`);
console.log(`Multi-phone:    ${merged.filter(d => d.phones.length > 1).length}`);
console.log(`Missing phone:  ${merged.filter(d => d.phones.length === 0).length}`);
console.log(`File size:      ${(fs.statSync(dataPath).size / 1024).toFixed(1)} KB`);
