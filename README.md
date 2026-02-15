# Norske Forskningsgrupper

Søkbar webapp for norske forskningsgrupper via [Nasjonalt vitenarkiv (NVA) API](https://api.nva.unit.no).

## Bruk
Åpne `index.html` i en nettleser. Ingen build-steg eller avhengigheter.

## Funksjonalitet
- Fritekstsøk mot NVA organisasjons-API (Cristin-data)
- Filter på enhetstype (forskningsgrupper, institutter, fakulteter, institusjoner)
- Brødsmulesti med full organisasjonshierarki
- Detaljvisning med publikasjoner fra NVA søke-API
- Lenke til NVA for videre utforsking
- Paginering
- Mørkt/lyst tema
- Mobilvennlig

## API
- Organisasjonssøk: `https://api.nva.unit.no/cristin/organization?query=...`
- Enhetsdetaljer: `https://api.nva.unit.no/cristin/organization/{cristin-id}`
- Publikasjonssøk: `https://api.nva.unit.no/search/resources?unit=...`
