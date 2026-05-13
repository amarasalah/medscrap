import json
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET

xlsx_path = r'c:\Users\DELL\Desktop\APPLICATIONS\scrapDoc\sante.xlsx'
output_path = r'c:\Users\DELL\Desktop\APPLICATIONS\scrapDoc\public\doctors.json'

dept_map = {
    '01':'Ain','02':'Aisne','03':'Allier','04':'Alpes-de-Haute-Provence','05':'Hautes-Alpes',
    '06':'Alpes-Maritimes','07':'Ardèche','08':'Ardennes','09':'Ariège','10':'Aube',
    '11':'Aude','12':'Aveyron','13':'Bouches-du-Rhône','14':'Calvados','15':'Cantal',
    '16':'Charente','17':'Charente-Maritime','18':'Cher','19':'Corrèze','21':"Côte-d'Or",
    '22':"Côtes-d'Armor",'23':'Creuse','24':'Dordogne','25':'Doubs','26':'Drôme',
    '27':'Eure','28':'Eure-et-Loir','29':'Finistère','30':'Gard','31':'Haute-Garonne',
    '32':'Gers','33':'Gironde','34':'Hérault','35':'Ille-et-Vilaine','36':'Indre',
    '37':'Indre-et-Loire','38':'Isère','39':'Jura','40':'Landes','41':'Loir-et-Cher',
    '42':'Loire','43':'Haute-Loire','44':'Loire-Atlantique','45':'Loiret','46':'Lot',
    '47':'Lot-et-Garonne','48':'Lozère','49':'Maine-et-Loire','50':'Manche','51':'Marne',
    '52':'Haute-Marne','53':'Mayenne','54':'Meurthe-et-Moselle','55':'Meuse','56':'Morbihan',
    '57':'Moselle','58':'Nièvre','59':'Nord','60':'Oise','61':'Orne',
    '62':'Pas-de-Calais','63':'Puy-de-Dôme','64':'Pyrénées-Atlantiques','65':'Hautes-Pyrénées',
    '66':'Pyrénées-Orientales','67':'Bas-Rhin','68':'Haut-Rhin','69':'Rhône','70':'Haute-Saône',
    '71':'Saône-et-Loire','72':'Sarthe','73':'Savoie','74':'Haute-Savoie','75':'Paris',
    '76':'Seine-Maritime','77':'Seine-et-Marne','78':'Yvelines','79':'Deux-Sèvres',
    '80':'Somme','81':'Tarn','82':'Tarn-et-Garonne','83':'Var','84':'Vaucluse',
    '85':'Vendée','86':'Vienne','87':'Haute-Vienne','88':'Vosges','89':'Yonne',
    '90':'Territoire de Belfort','91':'Essonne','92':'Hauts-de-Seine','93':'Seine-Saint-Denis',
    '94':'Val-de-Marne','95':"Val-d'Oise",'97':'DOM-TOM','2A':'Corse-du-Sud','2B':'Haute-Corse'
}

region_map = {
    'Ain':'Auvergne-Rhône-Alpes','Aisne':'Hauts-de-France','Allier':'Auvergne-Rhône-Alpes',
    'Alpes-de-Haute-Provence':"Provence-Alpes-Côte d'Azur",'Hautes-Alpes':"Provence-Alpes-Côte d'Azur",
    'Alpes-Maritimes':"Provence-Alpes-Côte d'Azur",'Ardèche':'Auvergne-Rhône-Alpes',
    'Ardennes':'Grand Est','Ariège':'Occitanie','Aube':'Grand Est','Aude':'Occitanie',
    'Aveyron':'Occitanie','Bouches-du-Rhône':"Provence-Alpes-Côte d'Azur",'Calvados':'Normandie',
    'Cantal':'Auvergne-Rhône-Alpes','Charente':'Nouvelle-Aquitaine','Charente-Maritime':'Nouvelle-Aquitaine',
    'Cher':'Centre-Val de Loire','Corrèze':'Nouvelle-Aquitaine','Corse-du-Sud':'Corse',
    'Haute-Corse':'Corse',"Côte-d'Or":'Bourgogne-Franche-Comté',"Côtes-d'Armor":'Bretagne',
    'Creuse':'Nouvelle-Aquitaine','Dordogne':'Nouvelle-Aquitaine','Doubs':'Bourgogne-Franche-Comté',
    'Drôme':'Auvergne-Rhône-Alpes','Eure':'Normandie','Eure-et-Loir':'Centre-Val de Loire',
    'Finistère':'Bretagne','Gard':'Occitanie','Haute-Garonne':'Occitanie','Gers':'Occitanie',
    'Gironde':'Nouvelle-Aquitaine','Hérault':'Occitanie','Ille-et-Vilaine':'Bretagne',
    'Indre':'Centre-Val de Loire','Indre-et-Loire':'Centre-Val de Loire','Isère':'Auvergne-Rhône-Alpes',
    'Jura':'Bourgogne-Franche-Comté','Landes':'Nouvelle-Aquitaine','Loir-et-Cher':'Centre-Val de Loire',
    'Loire':'Auvergne-Rhône-Alpes','Haute-Loire':'Auvergne-Rhône-Alpes',
    'Loire-Atlantique':'Pays de la Loire','Loiret':'Centre-Val de Loire','Lot':'Occitanie',
    'Lot-et-Garonne':'Nouvelle-Aquitaine','Lozère':'Occitanie','Maine-et-Loire':'Pays de la Loire',
    'Manche':'Normandie','Marne':'Grand Est','Haute-Marne':'Grand Est','Mayenne':'Pays de la Loire',
    'Meurthe-et-Moselle':'Grand Est','Meuse':'Grand Est','Morbihan':'Bretagne','Moselle':'Grand Est',
    'Nièvre':'Bourgogne-Franche-Comté','Nord':'Hauts-de-France','Oise':'Hauts-de-France',
    'Orne':'Normandie','Pas-de-Calais':'Hauts-de-France','Puy-de-Dôme':'Auvergne-Rhône-Alpes',
    'Pyrénées-Atlantiques':'Nouvelle-Aquitaine','Hautes-Pyrénées':'Occitanie',
    'Pyrénées-Orientales':'Occitanie','Bas-Rhin':'Grand Est','Haut-Rhin':'Grand Est',
    'Rhône':'Auvergne-Rhône-Alpes','Haute-Saône':'Bourgogne-Franche-Comté',
    'Saône-et-Loire':'Bourgogne-Franche-Comté','Sarthe':'Pays de la Loire','Savoie':'Auvergne-Rhône-Alpes',
    'Haute-Savoie':'Auvergne-Rhône-Alpes','Paris':'Île-de-France','Seine-Maritime':'Normandie',
    'Seine-et-Marne':'Île-de-France','Yvelines':'Île-de-France','Deux-Sèvres':'Nouvelle-Aquitaine',
    'Somme':'Hauts-de-France','Tarn':'Occitanie','Tarn-et-Garonne':'Occitanie',
    'Var':"Provence-Alpes-Côte d'Azur",'Vaucluse':"Provence-Alpes-Côte d'Azur",
    'Vendée':'Pays de la Loire','Vienne':'Nouvelle-Aquitaine','Haute-Vienne':'Nouvelle-Aquitaine',
    'Vosges':'Grand Est','Yonne':'Bourgogne-Franche-Comté','Territoire de Belfort':'Bourgogne-Franche-Comté',
    'Essonne':'Île-de-France','Hauts-de-Seine':'Île-de-France','Seine-Saint-Denis':'Île-de-France',
    'Val-de-Marne':'Île-de-France',"Val-d'Oise":'Île-de-France','DOM-TOM':'Outre-mer'
}

def format_phone(raw):
    if not raw or raw == 'None':
        return None
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 10:
        return ' '.join([digits[i:i+2] for i in range(0, 10, 2)])
    return raw

def extract_coords(maps_url):
    if not maps_url or maps_url == 'None':
        return None, None
    m = re.search(r'([-\d.]+),([-\d.]+)$', maps_url)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except:
            pass
    return None, None

doctors = []

with ZipFile(xlsx_path) as z:
    with z.open('xl/worksheets/sheet1.xml') as f:
        tree = ET.parse(f)
        ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        rows = tree.findall('.//ns:row', ns)

        for idx, row in enumerate(rows[1:], start=1):  # skip header
            cells = {}
            for cell in row.findall('ns:c', ns):
                ref = cell.attrib.get('r', '')
                col = re.match(r'([A-Z]+)', ref).group(1) if ref else ''
                val_el = cell.find('ns:v', ns)
                val = val_el.text if val_el is not None else ''
                cells[col] = val

            typ = cells.get('A', '')
            if not typ or typ == 'None':
                continue

            name = cells.get('B', '')
            if not name or name == 'None':
                continue

            address = cells.get('I', '')
            if address == 'None':
                address = ''

            # Extract city, postal code, department, region
            city = ''
            postal_code = ''
            department = ''
            region = ''

            if address:
                pc_match = re.search(r'(\d{5})', address)
                if pc_match:
                    postal_code = pc_match.group(1)
                    dept_code = postal_code[:2]
                    if dept_code == '20':
                        dept_code = '2A'
                    department = dept_map.get(dept_code, '')
                    region = region_map.get(department, '')

                city_match = re.search(r'\d{5}\s+(.+)$', address)
                if city_match:
                    city = city_match.group(1).strip()

            lat, lng = extract_coords(cells.get('J', ''))

            phone_raw = cells.get('M', '')
            if phone_raw == 'None':
                phone_raw = ''

            convention = cells.get('O', '')
            if convention == 'None':
                convention = ''

            specialty = cells.get('D', '')
            if specialty == 'None':
                specialty = ''

            sub_specialty = cells.get('G', '')
            if sub_specialty == 'None':
                sub_specialty = ''

            profile_url = cells.get('C', '')
            if profile_url == 'None':
                profile_url = ''

            maps_url = cells.get('J', '')
            if maps_url == 'None':
                maps_url = ''

            doc = {
                'id': idx,
                'type': typ,
                'name': name,
                'profileUrl': profile_url,
                'specialty': specialty,
                'subSpecialty': sub_specialty,
                'address': address,
                'city': city,
                'postalCode': postal_code,
                'department': department,
                'region': region,
                'mapsUrl': maps_url,
                'lat': lat,
                'lng': lng,
                'phone': format_phone(phone_raw),
                'phoneRaw': re.sub(r'\D', '', phone_raw) if phone_raw else '',
                'convention': convention
            }
            doctors.append(doc)

import os
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(doctors, f, ensure_ascii=False, indent=None)

print(f"Converted {len(doctors)} records to {output_path}")
print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")
