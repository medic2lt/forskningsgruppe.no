#!/usr/bin/env python3
"""
Scraper for forskningsgruppe.no — re-scrapes all 29 institutions.
Sources: institution websites (HTML scraping) + NVA API fallback.
"""

import json
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import ssl
from html.parser import HTMLParser
from collections import Counter
from datetime import datetime, timezone

DATA_FILE = "/home/babayaga/forskningsgruppe.no/data.json"
OBSIDIAN_COPY = "/home/babayaga/JRFO/Prosjekter/forskningsgrupper/data.json"

# SSL context that doesn't verify (some .no sites have cert issues)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url, timeout=30):
    """Fetch URL content as string."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 forskningsgruppe.no-bot/1.0',
        'Accept': 'text/html,application/json,*/*',
        'Accept-Language': 'nb-NO,nb;q=0.9,no;q=0.8,en;q=0.5',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  WARN: Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def fetch_json(url, timeout=30):
    """Fetch URL and parse as JSON."""
    text = fetch(url, timeout)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return None

def slugify(institution, name):
    """Create a stable ID from institution + name."""
    prefix = institution.lower()
    # Simplify common prefixes
    for full, short in [
        ("høgskolen i molde", "himolde"),
        ("høgskolen i innlandet", "inn"),
        ("høgskolen i østfold", "hiof"),
        ("høgskulen i volda", "hivolda"),
        ("høgskulen på vestlandet", "hvl"),
        ("høyskolen kristiania", "kristiania"),
        ("dronning mauds minne høgskole", "dmmh"),
        ("handelshøyskolen bi", "bi"),
        ("kunsthøgskolen i oslo", "aho"),
        ("lovisenberg diakonale høgskole", "ldh"),
        ("mf vitenskapelig høyskole", "mf"),
        ("nla høgskolen", "nla"),
        ("norges handelshøyskole", "nhh"),
        ("norges idrettshøgskole", "nih"),
        ("norges musikkhøgskole", "nmh"),
        ("arkitektur- og designhøgskolen i oslo", "aho"),
        ("politihøgskolen", "phs"),
        ("samisk høgskole", "samas"),
        ("vid vitenskapelige høgskole", "vid"),
        ("universitetet i agder", "uia"),
        ("universitetet i bergen", "uib"),
        ("universitetet i oslo", "uio"),
        ("universitetet i stavanger", "uis"),
        ("universitetet i sørøst-norge", "usn"),
        ("uit norges arktiske universitet", "uit"),
        ("nord universitet", "nord"),
        ("ntnu", "ntnu"),
        ("nmbu", "nmbu"),
        ("oslomet", "oslomet"),
        ("sintef", "sintef"),
        ("forsvarets forskningsinstitutt", "ffi"),
        ("folkehelseinstituttet", "fhi"),
        ("niva", "niva"),
        ("nibio", "nibio"),
        ("norges geotekniske institutt", "ngi"),
        ("havforskningsinstituttet", "hi"),
        ("nupi", "nupi"),
        ("telemarksforsking", "tmforsk"),
        ("simula research laboratory", "simula"),
        ("transportøkonomisk institutt", "toi"),
        ("institutt for energiteknikk", "ife"),
        ("statens arbeidsmiljøinstitutt", "stami"),
        ("institutt for samfunnsforskning", "isf"),
        ("prio", "prio"),
        ("chr. michelsens institutt", "cmi"),
        ("nansen senter for miljø og fjernmåling", "nersc"),
        ("fafo", "fafo"),
        ("norsk institutt for kulturminneforskning", "niku"),
    ]:
        if prefix == full:
            prefix = short
            break
    
    slug = re.sub(r'[^a-z0-9æøå]+', '-', name.lower()).strip('-')
    return f"{prefix}-{slug}"


class LinkExtractor(HTMLParser):
    """Extract links and text from HTML."""
    def __init__(self):
        super().__init__()
        self.links = []  # [(url, text)]
        self._current_href = None
        self._current_text = []
        self._in_a = False
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            d = dict(attrs)
            self._current_href = d.get('href', '')
            self._current_text = []
            self._in_a = True
    
    def handle_data(self, data):
        if self._in_a:
            self._current_text.append(data.strip())
    
    def handle_endtag(self, tag):
        if tag == 'a' and self._in_a:
            text = ' '.join(self._current_text).strip()
            if self._current_href and text:
                self.links.append((self._current_href, text))
            self._in_a = False


# ========== INSTITUTION SCRAPERS ==========

def scrape_generic_list(url, institution, inst_id, url_filter=None, name_filter=None, base_url=None, category="uho"):
    """Scrape a page with a list of links to research groups."""
    html = fetch(url)
    if not html:
        return []
    
    parser = LinkExtractor()
    parser.feed(html)
    
    groups = []
    seen = set()
    for href, text in parser.links:
        if url_filter and not url_filter(href):
            continue
        if name_filter and not name_filter(text):
            continue
        # Make absolute
        if href.startswith('/'):
            if base_url:
                href = base_url.rstrip('/') + href
            else:
                from urllib.parse import urljoin
                href = urljoin(url, href)
        elif not href.startswith('http'):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        
        # Deduplicate
        key = (text, href)
        if key in seen:
            continue
        seen.add(key)
        
        gid = slugify(institution, text)
        groups.append({
            "name": text,
            "url": href,
            "institution": institution,
            "institutionId": inst_id,
            "description": f"Forskningsgruppe ved {institution}",
            "id": gid,
            "category": category
        })
    
    return groups


def scrape_himolde():
    """HiMolde - list page with links."""
    url = "https://www.himolde.no/forskning/grupper/"
    return scrape_generic_list(
        url, "Høgskolen i Molde", "211.0.0.0",
        url_filter=lambda h: '/forskning/grupper/' in h and h != '/forskning/grupper/' and not h.endswith('/forskning/grupper/'),
        base_url="https://www.himolde.no"
    )

def scrape_ntnu():
    """NTNU - two domains, multiple faculty pages."""
    groups = []
    # Main NTNU research groups page
    urls = [
        "https://www.ntnu.no/forskning/forskningsgrupper",
        "https://www.ntnu.edu/research/groups",
    ]
    
    # NTNU has many faculty-specific pages. We'll use their API/sitemap approach.
    # Try the main listing first
    for url in urls:
        html = fetch(url)
        if not html:
            continue
        parser = LinkExtractor()
        parser.feed(html)
        seen = set()
        for href, text in parser.links:
            if len(text) < 3 or len(text) > 200:
                continue
            if any(x in href.lower() for x in ['forskning/forskningsgrupper', 'research/groups']) and href not in seen:
                # This is the listing page link itself, skip
                continue
            # Heuristic: links that look like research group pages
            if re.search(r'ntnu\.(no|edu)', href) and len(text) > 5:
                if any(skip in text.lower() for skip in ['logg inn', 'english', 'norsk', 'søk', 'meny', 'kontakt', 'ansatte']):
                    continue
                seen.add(href)
    
    return groups

def scrape_nva_cristin(institution, inst_id, cristin_id, category="uho"):
    """Use NVA/Cristin API to get sub-organizations (research groups)."""
    url = f"https://api.nva.unit.no/cristin/organization/{cristin_id}?depth=full"
    data = fetch_json(url)
    if not data:
        print(f"  WARN: NVA API failed for {institution} ({cristin_id})", file=sys.stderr)
        return []
    
    groups = []
    seen = set()
    
    # Admin/non-research blacklist
    BLACKLIST = re.compile(r'(administrasjon|sentralbord|personal|drift|regnskap|lønn|'
        r'sekretariat|stab|campus\s*(administrasjon|service)|fakultetsadmin|'
        r'universitetsdirektør|fellesadm|kommunikasjon|it.avdeling|'
        r'studieadm|arkiv|innkjøp|eiendom|renhold|vakt|kantine|'
        r'økonomi.*(avdeling|seksjon)|hr.*(avdeling|seksjon)|'
        r'viserektor|prorektor|dekanat)', re.IGNORECASE)
    
    def extract_units(org, depth=0):
        if depth > 6:
            return
        name = org.get('name', {})
        unit_name = name.get('nb') or name.get('nn') or name.get('en') or ''
        unit_id = org.get('id', '')
        
        hasPart = org.get('hasPart', [])
        
        # If leaf node or depth >= 3 and looks like a research group
        is_leaf = len(hasPart) == 0
        
        if unit_name and not BLACKLIST.search(unit_name):
            # Only include deeper units (dept level or below), not top faculties
            if depth >= 3 and unit_name not in seen:
                seen.add(unit_name)
                # Build URL from cristin
                cristin_url = f"https://app.cristin.no/institutions/show.jsf?id={cristin_id}"
                groups.append({
                    "name": unit_name,
                    "url": cristin_url,
                    "institution": institution,
                    "institutionId": inst_id,
                    "description": f"Forskningsgruppe ved {institution}",
                    "id": slugify(institution, unit_name),
                    "category": category
                })
        
        for sub in hasPart:
            extract_units(sub, depth + 1)
    
    extract_units(data)
    return groups


# Institution configs: (name, institutionId, scrape_function)
# We'll use web scraping where possible and NVA API as supplement

INSTITUTIONS = {
    "himolde": {
        "name": "Høgskolen i Molde",
        "id": "211.0.0.0",
        "cristin": "211.0.0.0",
        "scrape_url": "https://www.himolde.no/forskning/grupper/",
        "url_pattern": r"/forskning/grupper/[^/]+",
        "base_url": "https://www.himolde.no",
    },
    "inn": {
        "name": "Høgskolen i Innlandet",
        "id": "210.0.0.0",
        "scrape_url": "https://www.inn.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.inn.no",
    },
    "hiof": {
        "name": "Høgskolen i Østfold",
        "id": "224.0.0.0",
        "scrape_url": "https://www.hiof.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.hiof.no",
    },
    "hivolda": {
        "name": "Høgskulen i Volda",
        "id": "223.0.0.0",
        "scrape_url": "https://www.hivolda.no/forsking/forskingsgrupper",
        "url_pattern": r"/forsking/forskingsgrupper/",
        "base_url": "https://www.hivolda.no",
    },
    "hvl": {
        "name": "Høgskulen på Vestlandet",
        "id": "203.0.0.0",
        "scrape_url": "https://www.hvl.no/forsking/forskingsgrupper/",
        "url_pattern": r"/forsking/forskingsgrupper/",
        "base_url": "https://www.hvl.no",
    },
    "kristiania": {
        "name": "Høyskolen Kristiania",
        "id": "247.0.0.0",
        "scrape_url": "https://www.kristiania.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.kristiania.no",
    },
    "dmmh": {
        "name": "Dronning Mauds Minne Høgskole",
        "id": "222.0.0.0",
        "scrape_url": "https://www.dmmh.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.dmmh.no",
    },
    "bi": {
        "name": "Handelshøyskolen BI",
        "id": "171.0.0.0",
        "scrape_url": "https://www.bi.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.bi.no",
    },
    "ldh": {
        "name": "Lovisenberg diakonale høgskole",
        "id": "231.0.0.0",
        "scrape_url": "https://ldh.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://ldh.no",
    },
    "mf": {
        "name": "MF vitenskapelig høyskole",
        "id": "170.0.0.0",
        "scrape_url": "https://www.mf.no/forskning",
        "url_pattern": r"/forskning/",
        "base_url": "https://www.mf.no",
    },
    "nla": {
        "name": "NLA Høgskolen",
        "id": "232.0.0.0",
        "scrape_url": "https://www.nla.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.nla.no",
    },
    "nhh": {
        "name": "Norges Handelshøyskole",
        "id": "172.0.0.0",
        "scrape_url": "https://www.nhh.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.nhh.no",
    },
    "nih": {
        "name": "Norges idrettshøgskole",
        "id": "173.0.0.0",
        "scrape_url": "https://www.nih.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.nih.no",
    },
    "nmh": {
        "name": "Norges musikkhøgskole",
        "id": "174.0.0.0",
        "scrape_url": "https://nmh.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://nmh.no",
    },
    "oslomet": {
        "name": "OsloMet",
        "id": "201.0.0.0",
        "scrape_url": "https://www.oslomet.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.oslomet.no",
    },
    "phs": {
        "name": "Politihøgskolen",
        "id": "178.0.0.0",
        "scrape_url": "https://www.politihogskolen.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.politihogskolen.no",
    },
    "vid": {
        "name": "VID vitenskapelige høgskole",
        "id": "228.0.0.0",
        "scrape_url": "https://www.vid.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.vid.no",
    },
    "nmbu": {
        "name": "NMBU",
        "id": "192.0.0.0",
        "scrape_url": "https://www.nmbu.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.nmbu.no",
    },
    "nord": {
        "name": "Nord universitet",
        "id": "213.0.0.0",
        "scrape_url": "https://www.nord.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.nord.no",
    },
    "usn": {
        "name": "Universitetet i Sørøst-Norge",
        "id": "227.0.0.0",
        "scrape_url": "https://www.usn.no/forskning/forskningsgrupper/",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.usn.no",
    },
    "uia": {
        "name": "Universitetet i Agder",
        "id": "195.0.0.0",
        "scrape_url": "https://www.uia.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.uia.no",
    },
    "uis": {
        "name": "Universitetet i Stavanger",
        "id": "217.0.0.0",
        "scrape_url": "https://www.uis.no/nb/forskning/forskningsgrupper",
        "url_pattern": r"/forskning|/research",
        "base_url": "https://www.uis.no",
    },
    "samas": {
        "name": "Samisk høgskole",
        "id": "220.0.0.0",
        "scrape_url": "https://samas.no/nb/forskning",
        "url_pattern": r"/forskning",
        "base_url": "https://samas.no",
    },
    "aho": {
        "name": "Arkitektur- og designhøgskolen i Oslo",
        "id": "200.0.0.0",
        "scrape_url": "https://www.aho.no/forskning/forskningsgrupper",
        "url_pattern": r"/forskning/forskningsgrupper/",
        "base_url": "https://www.aho.no",
    },
}

# Large universities need special handling (multi-faculty, different URL structures)
LARGE_UNIS = {
    "uio": {
        "name": "Universitetet i Oslo",
        "id": "185.0.0.0",
        "cristin": "185.0.0.0",
        "faculty_urls": [
            ("https://www.med.uio.no/forskning/grupper/", "www.med.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.mn.uio.no/forskning/grupper/", "www.mn.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.hf.uio.no/forskning/grupper/", "www.hf.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.sv.uio.no/forskning/grupper/", "www.sv.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.uv.uio.no/forskning/grupper/", "www.uv.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.jus.uio.no/forskning/grupper/", "www.jus.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.odont.uio.no/forskning/grupper/", "www.odont.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.tf.uio.no/forskning/grupper/", "www.tf.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.nhm.uio.no/forskning/grupper/", "www.nhm.uio.no", r"/forskning/grupper/[^/]+"),
            ("https://www.globe.uio.no/forskning/grupper/", "www.globe.uio.no", r"/forskning/grupper/[^/]+"),
        ]
    },
    "uib": {
        "name": "Universitetet i Bergen",
        "id": "184.0.0.0",
        "cristin": "184.0.0.0",
        "faculty_urls": [
            ("https://www4.uib.no/forskning/forskningsgrupper", "www4.uib.no", None),
        ]
    },
    "ntnu": {
        "name": "NTNU",
        "id": "194.0.0.0",
        "cristin": "194.0.0.0",
        "faculty_urls": [
            ("https://www.ntnu.no/forskning/forskningsgrupper", "www.ntnu.no", None),
            ("https://www.ntnu.edu/research/groups", "www.ntnu.edu", None),
        ]
    },
    "uit": {
        "name": "UiT Norges arktiske universitet",
        "id": "186.0.0.0",
        "cristin": "186.0.0.0",
        "faculty_urls": [
            ("https://uit.no/forskning/forskningsgrupper", "uit.no", None),
        ]
    },
}

INSTITUTES = {
    "sintef": {
        "name": "SINTEF",
        "id": "7401.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.sintef.no/forskningsomrader/",
        "url_pattern": r"/forskningsomrader/[^/]+",
        "base_url": "https://www.sintef.no",
    },
    "ffi": {
        "name": "Forsvarets forskningsinstitutt",
        "id": "7464.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.ffi.no/om-ffi",
        "url_pattern": r"/om-ffi/(avdeling|forsvarssystemer|innovasjon|strategiske|totalforsvar)",
        "base_url": "https://www.ffi.no",
    },
    "fhi": {
        "name": "Folkehelseinstituttet",
        "id": "7502.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.fhi.no/om/organisasjon/",
        "url_pattern": r"/om/organisasjon/|/omrader/",
        "base_url": "https://www.fhi.no",
    },
    "niva": {
        "name": "NIVA",
        "id": "7485.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.niva.no/seksjoner",
        "url_pattern": r"/seksjoner/[^/]+",
        "base_url": "https://www.niva.no",
    },
    "nibio": {
        "name": "NIBIO",
        "id": "7677.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.nibio.no/om-nibio/vare-fagdivisjoner",
        "url_pattern": r"/om-nibio/vare-fagdivisjoner/",
        "base_url": "https://www.nibio.no",
    },
    "ngi": {
        "name": "Norges Geotekniske Institutt",
        "id": "7429.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.ngi.no/forskning-og-radgivning/",
        "url_pattern": r"/forskning-og-radgivning/[^/]+",
        "base_url": "https://www.ngi.no",
    },
    "hi": {
        "name": "Havforskningsinstituttet",
        "id": "7512.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.hi.no/hi/forskning/forskningsgrupper",
        "url_pattern": r"/hi/forskning/forskningsgrupper/[^/]+",
        "base_url": "https://www.hi.no",
    },
    "nupi": {
        "name": "NUPI",
        "id": "7445.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.nupi.no/om-nupi/organisering",
        "url_pattern": r"/forskning/|/forskningsgruppe/|/om-nupi/organisering/",
        "base_url": "https://www.nupi.no",
    },
    "tmforsk": {
        "name": "Telemarksforsking",
        "id": "7439.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://telemarksforsking.no/forskergrupper/",
        "url_pattern": r"/forskergrupper/[^/]+",
        "base_url": "https://telemarksforsking.no",
    },
    "simula": {
        "name": "Simula Research Laboratory",
        "id": "7467.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.simula.no/research",
        "url_pattern": r"/research/[^/]+",
        "base_url": "https://www.simula.no",
    },
    "toi": {
        "name": "Transportøkonomisk institutt",
        "id": "7454.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.toi.no/forskningsomrader/",
        "url_pattern": r"/forskningsomrader/[^/]+",
        "base_url": "https://www.toi.no",
    },
    "ife": {
        "name": "Institutt for energiteknikk",
        "id": "7453.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://ife.no/ife-fagomrader/",
        "url_pattern": r"/ife-fagomrader/[^/]+",
        "base_url": "https://ife.no",
    },
    "stami": {
        "name": "Statens arbeidsmiljøinstitutt",
        "id": "7501.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://stami.no/forskningsomrade/",
        "url_pattern": r"/forskningsomrade/[^/]+",
        "base_url": "https://stami.no",
    },
    "isf": {
        "name": "Institutt for samfunnsforskning",
        "id": "7448.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.samfunnsforskning.no/vi-forsker-pa/",
        "url_pattern": r"/vi-forsker-pa/[^/]+",
        "base_url": "https://www.samfunnsforskning.no",
    },
    "prio": {
        "name": "PRIO",
        "id": "7444.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.prio.org/research",
        "url_pattern": r"/research/|/centres/",
        "base_url": "https://www.prio.org",
    },
    "cmi": {
        "name": "Chr. Michelsens Institutt",
        "id": "7462.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.cmi.no/centres",
        "url_pattern": r"/centres/[^/]+",
        "base_url": "https://www.cmi.no",
    },
    "nersc": {
        "name": "Nansen Senter for Miljø og Fjernmåling",
        "id": "7543.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://nersc.no/forskningsomrader/",
        "url_pattern": r"/forskningsomrader/[^/]+",
        "base_url": "https://nersc.no",
    },
    "fafo": {
        "name": "Fafo",
        "id": "7436.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.fafo.no/forskningstema",
        "url_pattern": r"/forskningstema/|/forskning/",
        "base_url": "https://www.fafo.no",
    },
    "niku": {
        "name": "Norsk institutt for kulturminneforskning",
        "id": "7437.0.0.0",
        "category": "forskningsinstitutt",
        "scrape_url": "https://www.niku.no/tjenester/",
        "url_pattern": r"/tjenester/[^/]+",
        "base_url": "https://www.niku.no",
    },
}


def scrape_uib():
    """UiB has a special listing page at www4.uib.no"""
    url = "https://www4.uib.no/forskning/forskningsgrupper"
    html = fetch(url)
    if not html:
        return []
    
    groups = []
    seen = set()
    
    # UiB listing has links like /forskningsgrupper/SLUG
    parser = LinkExtractor()
    parser.feed(html)
    
    for href, text in parser.links:
        if '/forskningsgrupper/' not in href:
            continue
        if href.endswith('/forskningsgrupper') or href.endswith('/forskningsgrupper/'):
            continue
        if len(text) < 3:
            continue
        
        if not href.startswith('http'):
            href = "https://www4.uib.no" + href
        
        if href not in seen:
            seen.add(href)
            groups.append({
                "name": text.strip(),
                "url": href,
                "institution": "Universitetet i Bergen",
                "institutionId": "184.0.0.0",
                "description": "Forskningsgruppe ved UiB",
                "id": slugify("Universitetet i Bergen", text.strip()),
                "category": "uho"
            })
    
    return groups


def scrape_uit():
    """UiT - research groups listing."""
    url = "https://uit.no/forskning/forskningsgrupper"
    html = fetch(url)
    if not html:
        return []
    
    groups = []
    seen = set()
    parser = LinkExtractor()
    parser.feed(html)
    
    for href, text in parser.links:
        text = text.strip()
        if len(text) < 3 or len(text) > 300:
            continue
        # UiT research group links
        if re.search(r'forskning/forskningsgrupper|research.*group', href, re.IGNORECASE):
            if href.rstrip('/') == url.rstrip('/'):
                continue
            if not href.startswith('http'):
                href = "https://uit.no" + href
            if href not in seen:
                seen.add(href)
                groups.append({
                    "name": text,
                    "url": href,
                    "institution": "UiT Norges arktiske universitet",
                    "institutionId": "186.0.0.0",
                    "description": "Forskningsgruppe ved UiT",
                    "id": slugify("UiT Norges arktiske universitet", text),
                    "category": "uho"
                })
    
    return groups


def scrape_ntnu_groups():
    """NTNU - research groups from multiple pages.
    NOTE: category field will be added when this function is rewritten (Task 5).
    Currently has a bug where groups are never appended to the list."""
    groups = []
    seen = set()
    
    # NTNU Norwegian page
    for base_url in ["https://www.ntnu.no/forskning/forskningsgrupper", "https://www.ntnu.edu/research/groups"]:
        html = fetch(base_url)
        if not html:
            continue
        parser = LinkExtractor()
        parser.feed(html)
        
        for href, text in parser.links:
            text = text.strip()
            if len(text) < 3:
                continue
            if any(x in text.lower() for x in ['logg inn', 'english', 'norsk', 'søk', 'meny', 'kontakt', 'ansatte', 'studier']):
                continue
            if not href.startswith('http'):
                domain = base_url.split('/')[2]
                href = f"https://{domain}{href}"
            if re.search(r'ntnu\.(no|edu)', href) and href not in seen:
                seen.add(href)
    
    return groups


def scrape_uio_faculty(fac_url, base_domain):
    """Scrape a UiO faculty research groups page."""
    html = fetch(fac_url)
    if not html:
        return []
    
    groups = []
    seen = set()
    parser = LinkExtractor()
    parser.feed(html)
    
    for href, text in parser.links:
        text = text.strip()
        if len(text) < 3:
            continue
        if '/forskning/grupper/' not in href:
            continue
        if href.rstrip('/') == fac_url.rstrip('/'):
            continue
        
        if not href.startswith('http'):
            href = f"https://{base_domain}{href}"
        
        if href not in seen:
            seen.add(href)
            groups.append({
                "name": text,
                "url": href,
                "institution": "Universitetet i Oslo",
                "institutionId": "185.0.0.0",
                "description": "Forskningsgruppe ved UiO",
                "id": slugify("Universitetet i Oslo", text),
                "category": "uho"
            })
    
    return groups


def scrape_standard_institution(config):
    """Scrape a standard institution with a single listing page."""
    inst = config["name"]
    inst_id = config["id"]
    url = config["scrape_url"]
    pattern = config.get("url_pattern", "")
    base = config.get("base_url", "")
    
    html = fetch(url)
    if not html:
        print(f"  WARN: Could not fetch {url}", file=sys.stderr)
        return []
    
    parser = LinkExtractor()
    parser.feed(html)
    
    groups = []
    seen = set()
    
    for href, text in parser.links:
        text = text.strip()
        if len(text) < 3 or len(text) > 300:
            continue
        
        # Skip navigation links
        if any(x in text.lower() for x in ['logg inn', 'english', 'norsk', 'søk', 'meny', 'kontakt', 'les mer', 'tilbake', 'hjem']):
            continue
        
        # Check URL pattern match
        if pattern and not re.search(pattern, href):
            continue
        
        # Skip the listing page itself
        if href.rstrip('/') == url.rstrip('/'):
            continue
        
        # Make absolute
        if not href.startswith('http'):
            href = base.rstrip('/') + '/' + href.lstrip('/') if base else href
        
        if href not in seen:
            seen.add(href)
            groups.append({
                "name": text,
                "url": href,
                "institution": inst,
                "institutionId": inst_id,
                "description": f"Forskningsgruppe ved {inst}",
                "id": slugify(inst, text),
                "category": config.get("category", "uho")
            })
    
    return groups



def _gid(g):
    """Get group id with fallback to url or name."""
    return g.get('id', g.get('url', g['name']))

def main():
    print("=== Forskningsgruppe.no Weekly Scrape ===")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    
    # Load existing data for comparison
    with open(DATA_FILE) as f:
        old_data = json.load(f)
    old_groups = {g.get('id', g.get('url', g['name'])): g for g in old_data['groups']}
    old_count = len(old_groups)
    old_ids = set(old_groups.keys())
    
    all_groups = []
    
    # 1. Standard institutions
    for key, config in INSTITUTIONS.items():
        print(f"\nScraping {config['name']}...")
        groups = scrape_standard_institution(config)
        print(f"  Found {len(groups)} groups")
        existing = [g for g in old_data['groups'] if g['institution'] == config['name']]
        if groups and len(groups) >= len(existing) * 0.5:
            all_groups.extend(groups)
        else:
            if groups:
                print(f"  Too few ({len(groups)} vs {len(existing)} existing) — keeping old data")
            else:
                print(f"  Using {len(existing)} existing groups (scrape returned 0)")
            all_groups.extend(existing)
    
    # 1b. Forskningsinstitutter
    for key, config in INSTITUTES.items():
        print(f"\nScraping {config[name]}...")
        groups = scrape_standard_institution(config)
        print(f"  Found {len(groups)} groups")
        existing = [g for g in old_data[groups] if g[institution] == config[name]]
        if groups and len(groups) >= len(existing) * 0.5:
            all_groups.extend(groups)
        else:
            if existing:
                if groups:
                    print(f"  Too few ({len(groups)} vs {len(existing)} existing) — keeping old data")
                else:
                    print(f"  Using {len(existing)} existing groups (scrape returned 0)")
                all_groups.extend(existing)
            elif groups:
                all_groups.extend(groups)
    
    # 2. UiO (multi-faculty)
    print(f"\nScraping Universitetet i Oslo (10 faculties)...")
    uio_groups = []
    for fac_url, domain, _ in LARGE_UNIS["uio"]["faculty_urls"]:
        g = scrape_uio_faculty(fac_url, domain)
        print(f"  {domain}: {len(g)} groups")
        uio_groups.extend(g)
    existing_uio = [g for g in old_data['groups'] if g['institution'] == "Universitetet i Oslo"]
    if uio_groups and len(uio_groups) >= len(existing_uio) * 0.5:
        all_groups.extend(uio_groups)
    else:
        print(f"  Too few ({len(uio_groups)} vs {len(existing_uio)}) — keeping old data")
        all_groups.extend(existing_uio)
    print(f"  Total UiO: {len(uio_groups)}")
    
    # 3. UiB
    print(f"\nScraping Universitetet i Bergen...")
    uib_groups = scrape_uib()
    print(f"  Found {len(uib_groups)} groups")
    existing_uib = [g for g in old_data['groups'] if g['institution'] == "Universitetet i Bergen"]
    if uib_groups and len(uib_groups) >= len(existing_uib) * 0.5:
        all_groups.extend(uib_groups)
    else:
        print(f"  Too few — keeping old data ({len(existing_uib)})")
        all_groups.extend(existing_uib)
    
    # 4. UiT
    print(f"\nScraping UiT Norges arktiske universitet...")
    uit_groups = scrape_uit()
    print(f"  Found {len(uit_groups)} groups")
    existing_uit = [g for g in old_data['groups'] if g['institution'] == "UiT Norges arktiske universitet"]
    if uit_groups and len(uit_groups) >= len(existing_uit) * 0.5:
        all_groups.extend(uit_groups)
    else:
        print(f"  Too few ({len(uit_groups)} vs {len(existing_uit)}) — keeping old data")
        all_groups.extend(existing_uit)
    
    # 5. NTNU
    print(f"\nScraping NTNU...")
    ntnu_groups = scrape_ntnu_groups()
    print(f"  Found {len(ntnu_groups)} groups")
    existing_ntnu = [g for g in old_data['groups'] if g['institution'] == "NTNU"]
    if ntnu_groups and len(ntnu_groups) >= len(existing_ntnu) * 0.5:
        all_groups.extend(ntnu_groups)
    else:
        print(f"  Too few ({len(ntnu_groups)} vs {len(existing_ntnu)}) — keeping old data")
        all_groups.extend(existing_ntnu)
    
    # Deduplicate by ID
    seen_ids = set()
    deduped = []
    for g in all_groups:
        if _gid(g) not in seen_ids:
            seen_ids.add(_gid(g))
            deduped.append(g)
    
    all_groups = sorted(deduped, key=lambda g: (g['institution'], g['name']))

    # Backfill category for groups from old data that might lack it
    for g in all_groups:
        if 'category' not in g:
            g['category'] = 'uho'
    
    # Compare
    new_ids = {_gid(g) for g in all_groups}
    added = new_ids - old_ids
    removed = old_ids - new_ids
    
    # Build final data
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    final_data = {
        "lastUpdated": now,
        "groups": all_groups
    }
    
    # Save
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    # Copy to Obsidian
    with open(OBSIDIAN_COPY, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    # Report
    new_count = len(all_groups)
    inst_count = len(set(g['institution'] for g in all_groups))
    
    print(f"\n=== REPORT ===")
    print(f"Total groups: {old_count} → {new_count} (Δ {new_count - old_count:+d})")
    print(f"Institutions: {inst_count}")
    print(f"Added: {len(added)}")
    if added:
        for gid in sorted(added):
            g = next(x for x in all_groups if x['id'] == gid)
            print(f"  + {g['name']} ({g['institution']})")
    print(f"Removed: {len(removed)}")
    if removed:
        for gid in sorted(removed):
            g = old_groups[gid]
            print(f"  - {g['name']} ({g['institution']})")
    
    # Per-institution counts
    print(f"\nPer institution:")
    c = Counter(g['institution'] for g in all_groups)
    for inst, cnt in sorted(c.items()):
        old_cnt = sum(1 for g in old_data['groups'] if g['institution'] == inst)
        delta = cnt - old_cnt
        marker = f" (Δ {delta:+d})" if delta else ""
        print(f"  {inst}: {cnt}{marker}")
    
    return new_count, inst_count, len(added), len(removed), added, removed


if __name__ == "__main__":
    main()
