import * as XLSX from 'xlsx';
import { primaryAddress, primaryPhone, COUNTRY_LABELS } from './doctor';

function joinExtra(items, fmt) {
  if (items.length <= 1) return '';
  return items.slice(1).map(fmt).join(' | ');
}

export function exportToExcel(data, filename = 'doctors') {
  const worksheetData = data.map((doc, index) => {
    const addr = primaryAddress(doc);
    const phone = primaryPhone(doc);
    return {
      '#': index + 1,
      'Pays / Country': COUNTRY_LABELS[doc.country] || doc.country || '',
      'Nom / Name': doc.name,
      'Spécialité / Specialty': doc.specialty,
      'Sous-spécialité / Sub-specialty': doc.subSpecialty || '',
      'Adresse / Address': addr?.address || '',
      'Ville / City': addr?.city || '',
      'Code Postal / Postal Code': addr?.postalCode || '',
      'Département / County / Provincia': addr?.department || '',
      'Région / Region / Comunidad': addr?.region || '',
      'Adresses supplémentaires / Extra addresses': joinExtra(doc.addresses || [], a => a.address),
      'Téléphone / Phone': phone?.formatted || '',
      'Téléphones supplémentaires / Extra phones': joinExtra(doc.phones || [], p => p.formatted),
      'Email': doc.email || '',
      'Convention': doc.convention || '',
      'Type': doc.type === 'professionnel_de_sante' ? 'Professionnel' : 'Établissement',
      'Profil / Profile URL': doc.profileUrl || '',
      'Google Maps': addr?.mapsUrl || '',
    };
  });

  const ws = XLSX.utils.json_to_sheet(worksheetData);

  const colWidths = Object.keys(worksheetData[0] || {}).map(key => ({
    wch: Math.max(
      key.length,
      ...worksheetData.slice(0, 100).map(row => String(row[key] || '').length)
    ) + 2
  }));
  ws['!cols'] = colWidths;

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Doctors');

  const date = new Date().toISOString().split('T')[0];
  XLSX.writeFile(wb, `${filename}_${date}.xlsx`);
}
