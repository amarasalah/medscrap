# Unified doctor schema

All countries (FR, GB, ES) and all scrapers write to this shape. The UI and
`exportExcel.js` only know this shape.

```jsonc
{
  "id": "fr-1234",                    // string, namespaced "<country>-<n>"
  "country": "FR",                    // ISO 3166-1 alpha-2: FR | GB | ES
  "type": "professionnel_de_sante",   // or "health_institution"
  "name": "Dr Cerruti Arnaud",
  "specialty": "Chirurgien urologue",
  "subSpecialty": "Chirurgie urologique",
  "profileUrl": "https://...",
  "email": null,                      // always present, almost always null
  "phones": [                         // distinct phone numbers
    { "raw": "0241405050", "formatted": "02 41 40 50 50" }
  ],
  "addresses": [                      // distinct practice locations
    {
      "address": "2 Rue des Rolletières, 49400 Saumur",
      "city": "Saumur",
      "postalCode": "49400",
      "department": "Maine-et-Loire",  // FR département / GB county / ES provincia
      "region": "Pays de la Loire",    // FR région / GB region / ES comunidad
      "lat": 47.246332,
      "lng": -0.063109,
      "mapsUrl": "https://www.google.com/maps/..."
    }
  ],
  "convention": "Conventionné secteur 1"  // FR only; null elsewhere
}
```

## Notes

- `phones` and `addresses` are arrays even when there's just one entry — the UI
  picks the first as primary and lists the rest in the modal.
- `id` is namespaced (`fr-`, `gb-`, `es-`) so merging country files never
  collides.
- Filtering by city / department / region matches **any** address.
- `convention` is FR-specific (Sécu sectors 1/2). `null` for GB/ES.
- `email` is reserved. Public registries don't publish it; only fill when a
  source genuinely exposes one.
