import * as XLSX from 'xlsx';

export function exportToExcel(data, filename = 'doctors') {
  const worksheetData = data.map((doc, index) => ({
    '#': index + 1,
    'Nom / Name': doc.name,
    'Spécialité / Specialty': doc.specialty,
    'Sous-spécialité': doc.subSpecialty || '',
    'Adresse / Address': doc.address || '',
    'Ville / City': doc.city || '',
    'Code Postal': doc.postalCode || '',
    'Département': doc.department || '',
    'Région': doc.region || '',
    'Téléphone / Phone': doc.phone || '',
    'Convention': doc.convention || '',
    'Type': doc.type === 'professionnel_de_sante' ? 'Professionnel' : 'Établissement',
    'Profil / Profile URL': doc.profileUrl || '',
    'Google Maps': doc.mapsUrl || '',
  }));

  const ws = XLSX.utils.json_to_sheet(worksheetData);

  // Auto-fit column widths
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
