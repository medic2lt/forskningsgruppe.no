#!/usr/bin/env python3
"""
Targeted Firecrawl scraping for specific research pages that might be missed.
"""

import json
import requests
import time
import re
from datetime import datetime, timezone

FIRECRAWL_URL = "http://localhost:3002"
DATA_FILE = "/home/babayaga/.openclaw/workspace/forskningsgruppe.no/data.json"

# Load existing data
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

existing_groups = {group['name'].lower() for group in data['groups']}

def firecrawl_scrape(url):
    """Scrape URL with Firecrawl"""
    try:
        payload = {
            "url": url,
            "formats": ["markdown", "html"],
            "onlyMainContent": True
        }
        
        response = requests.post(f"{FIRECRAWL_URL}/v1/scrape", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result["data"]
        return None
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def extract_groups_advanced(markdown, html, url):
    """Advanced group extraction using multiple strategies"""
    groups = []
    institution = extract_institution(url)
    
    # Strategy 1: Look for organized lists and sections
    section_patterns = [
        r'(?:^|\n)#{1,4}\s*([^#\n]*(?:group|gruppe|center|senter|institutt|institute)[^#\n]{5,100})',
        r'(?:^|\n)#{1,4}\s*([^#\n]*(?:forskning|research)[^#\n]{10,100})',
    ]
    
    # Strategy 2: HTML structure analysis if available
    if html:
        # Look for navigation menus, department lists, etc.
        nav_patterns = [
            r'<a[^>]+href="([^"]*(?:group|gruppe|center|senter|institutt)[^"]*)"[^>]*>([^<]+)</a>',
            r'<h[1-6][^>]*>([^<]*(?:group|gruppe|center|senter)[^<]*)</h[1-6]>',
        ]
        
        for pattern in nav_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:  # URL and text
                    name = match[1].strip()
                    group_url = match[0] if match[0].startswith('http') else url + match[0]
                else:
                    name = match.strip()
                    group_url = url
                    
                if is_valid_group_name(name):
                    groups.append({
                        'name': name,
                        'institution': institution,
                        'url': group_url,
                        'source': 'firecrawl_targeted_html',
                        'discovered': datetime.now(timezone.utc).isoformat()
                    })
    
    # Strategy 3: Markdown patterns
    for pattern in section_patterns:
        matches = re.findall(pattern, markdown, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            name = clean_group_name(match)
            if is_valid_group_name(name):
                groups.append({
                    'name': name,
                    'institution': institution,
                    'url': url,
                    'source': 'firecrawl_targeted_md',
                    'discovered': datetime.now(timezone.utc).isoformat()
                })
    
    return groups

def clean_group_name(name):
    """Clean up group name"""
    name = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', name)  # Remove markdown links
    name = re.sub(r'<[^>]+>', '', name)  # Remove HTML tags
    name = re.sub(r'[#*\-\s]+$', '', name)  # Remove trailing formatting
    name = re.sub(r'^[#*\-\s]+', '', name)  # Remove leading formatting
    return name.strip()

def is_valid_group_name(name):
    """Check if this is a valid group name"""
    if not name or len(name) < 8 or len(name) > 200:
        return False
    
    # Already exists
    if name.lower() in existing_groups:
        return False
        
    # Skip common navigation/UI elements
    skip_terms = [
        'cookie', 'link', 'meny', 'menu', 'side', 'page', 'search', 'søk', 
        'home', 'hjem', 'contact', 'kontakt', 'about', 'om oss', 'login', 'logg inn',
        'forskning og utvikling', 'research and development', 'forskningsområder',
        'research areas', 'publikasjoner', 'publications', 'nyheter', 'news'
    ]
    
    if any(skip.lower() in name.lower() for skip in skip_terms):
        return False
        
    # Must contain research-related terms
    research_terms = [
        'group', 'gruppe', 'center', 'centre', 'senter', 'senteret', 
        'institutt', 'institute', 'lab', 'laboratorium', 'enhet', 'unit',
        'forskning', 'research', 'faggruppe', 'team', 'prosjekt', 'project'
    ]
    
    if not any(term.lower() in name.lower() for term in research_terms):
        return False
        
    return True

def extract_institution(url):
    """Extract institution name from URL"""
    domain_mapping = {
        'uio.no': 'Universitetet i Oslo',
        'ntnu.no': 'NTNU', 
        'uib.no': 'Universitetet i Bergen',
        'uit.no': 'UiT Norges arktiske universitet',
        'uia.no': 'Universitetet i Agder',
        'uis.no': 'Universitetet i Stavanger', 
        'usn.no': 'Universitetet i Sørøst-Norge',
        'nmbu.no': 'NMBU',
        'oslomet.no': 'OsloMet',
        'himolde.no': 'Høgskolen i Molde',
        'hvl.no': 'Høgskulen på Vestlandet',
        'inn.no': 'Høgskolen i Innlandet',
        'nord.no': 'Nord universitet',
        'kristiania.no': 'Høyskolen Kristiania',
        'bi.no': 'Handelshøyskolen BI',
        'nhh.no': 'Norges Handelshøyskole',
        'mf.no': 'MF vitenskapelig høyskole',
        'aho.no': 'Arkitektur- og designhøgskolen i Oslo',
        'nih.no': 'Norges idrettshøgskole',
        'nmh.no': 'Norges musikkhøgskole'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    return 'Ukjent institusjon'

# Targeted URLs - specific pages that might have hidden groups
TARGETED_URLS = [
    # Faculty/department pages that might list research groups
    "https://www.uio.no/om/organisasjon/",
    "https://www.ntnu.no/organisasjon", 
    "https://www.himolde.no/om/organisasjon/",
    "https://www.hvl.no/om-hvl/organisasjon/",
    "https://www.inn.no/om-oss/organisasjon/",
    "https://kristiania.no/om-kristiania/organisasjon/",
    "https://www.bi.no/om-bi/organisasjon/",
    
    # Research portals and directories
    "https://www.forskningsradet.no/siteassets/publikasjoner/1254032542897.pdf",
    "https://www.forskningsradet.no/om-forskningsradet/organisasjon/",
    
    # Institution-specific research directories
    "https://www.uio.no/forskning/tverrfak/",
    "https://www.ntnu.no/forskning/strategiske-forskningsomraader",
    "https://www.uib.no/forskning/strategiske-forskningsomraader",
    "https://www.himolde.no/forskning/grupper/",
    "https://www.hvl.no/forskning/forskingsgrupper/",
    "https://www.inn.no/forskning/forskningsgrupper/",
    
    # Department-specific pages
    "https://www.himolde.no/studier/handelshogskole/",
    "https://www.himolde.no/studier/helse-og-sosialfag/",
    "https://www.himolde.no/studier/samfunns-og-naeringsutvikling/",
]

def main():
    print("🎯 Targeted Firecrawl Discovery for forskningsgruppe.no")
    print(f"⚡ Existing groups: {len(data['groups'])}")  
    print(f"🔍 Targeted URLs: {len(TARGETED_URLS)}")
    print()
    
    all_new_groups = []
    
    for i, url in enumerate(TARGETED_URLS, 1):
        print(f"[{i}/{len(TARGETED_URLS)}] Scraping {url}...")
        
        result = firecrawl_scrape(url)
        if result:
            markdown = result.get('markdown', '')
            html = result.get('html', '')
            
            if markdown or html:
                groups = extract_groups_advanced(markdown, html, url)
                if groups:
                    print(f"  ✅ Found {len(groups)} potential groups")
                    for group in groups:
                        print(f"    + {group['name']}")
                    all_new_groups.extend(groups)
                else:
                    print(f"  ⚪ No new groups found")
            else:
                print(f"  ❌ No content extracted")
        else:
            print(f"  ❌ Failed to scrape")
            
        time.sleep(1)  # Be nice
    
    print()
    print(f"🎉 Targeted discovery complete!")
    print(f"📊 Total new groups found: {len(all_new_groups)}")
    
    if all_new_groups:
        print("\n🆕 New groups discovered:")
        for group in all_new_groups:
            print(f"  + {group['name']} ({group['institution']})")
            existing_groups.add(group['name'].lower())
            
        # Add to data
        data['groups'].extend(all_new_groups)
        data['lastUpdated'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Save
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        obsidian_path = "/home/babayaga/JRFO/Prosjekter/forskningsgrupper/data.json"
        with open(obsidian_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ Updated: {len(data['groups'])} total groups")
    else:
        print("\n⚪ No new groups found in targeted scraping")
    
    print("\n🏁 Targeted discovery completed!")

if __name__ == "__main__":
    main()