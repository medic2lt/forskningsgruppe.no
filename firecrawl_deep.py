#!/usr/bin/env python3
"""
Firecrawl Deep Scraper for forskningsgruppe.no
Uses Firecrawl to discover hidden research groups via deep crawling.
"""

import json
import requests
import time
import re
from datetime import datetime, timezone

FIRECRAWL_URL = "http://localhost:3002"
DATA_FILE = "/home/babayaga/.openclaw/workspace/forskningsgruppe.no/data.json"

# Load existing data to avoid duplicates
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

existing_groups = set()
existing_urls = set()
for group in data['groups']:
    existing_groups.add(group['name'].lower())
    if 'url' in group:
        existing_urls.add(group['url'])

def firecrawl_scrape(url, include_links=False):
    """Scrape single URL with Firecrawl"""
    try:
        payload = {
            "url": url,
            "formats": ["markdown"],
            "includeTags": ["a", "h1", "h2", "h3"],
            "removeBase64Images": True
        }
        if include_links:
            payload["extractorOptions"] = {
                "mode": "llm-extraction",
                "extractionPrompt": "Extract all links related to research groups, departments, or centers. Look for Norwegian terms like 'forskningsgruppe', 'senter', 'institutt', 'faggruppe'."
            }
            
        response = requests.post(f"{FIRECRAWL_URL}/v1/scrape", json=payload, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result["data"]
        return None
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def firecrawl_crawl(base_url, max_pages=20):
    """Crawl entire site section with Firecrawl"""
    try:
        payload = {
            "url": base_url,
            "crawlerOptions": {
                "maxDepth": 3,
                "maxPages": max_pages,
                "includes": [
                    "*/forskning/*",
                    "*/research/*", 
                    "*/fakultet/*",
                    "*/institutt/*",
                    "*/senter/*",
                    "*/center/*",
                    "*/gruppe/*",
                    "*/group/*"
                ]
            },
            "formats": ["markdown"]
        }
        
        response = requests.post(f"{FIRECRAWL_URL}/v1/crawl", json=payload, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result["data"]
        return None
    except Exception as e:
        print(f"Error crawling {base_url}: {e}")
        return None

def extract_groups_from_markdown(markdown_text, base_url):
    """Extract potential research groups from markdown text"""
    groups = []
    
    # Patterns for Norwegian research groups
    patterns = [
        r'(?:^|\n)#{1,4}\s*(.+(?:forskningsgruppe|research group|senter|center|institutt|institute)[^#\n]+)',
        r'\*\*(.+(?:forskningsgruppe|research group|senter|center)[^*]+)\*\*',
        r'(?:^|\n)- (.+(?:forskningsgruppe|research group|senter|center)[^\n]+)'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, markdown_text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            name = match.strip()
            # Clean up common artifacts
            name = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', name)  # Remove markdown links
            name = re.sub(r'[#*\-\s]+$', '', name)  # Remove trailing formatting
            name = name.strip()
            
            if (len(name) > 10 and len(name) < 200 and 
                name.lower() not in existing_groups and
                not any(skip in name.lower() for skip in ['cookie', 'link', 'meny', 'side', 'search', 'søk'])):
                
                groups.append({
                    'name': name,
                    'institution': extract_institution(base_url),
                    'url': base_url,
                    'source': 'firecrawl_deep',
                    'discovered': datetime.now(timezone.utc).isoformat()
                })
                existing_groups.add(name.lower())
                
    return groups

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
        'nhh.no': 'Norges Handelshøyskole'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    return 'Ukjent institusjon'

# Deep crawl targets - research sections of major institutions
DEEP_CRAWL_TARGETS = [
    "https://www.uio.no/forskning/",
    "https://www.ntnu.no/forskning",
    "https://www.uib.no/forskning",
    "https://uit.no/forskning",
    "https://www.uia.no/forskning", 
    "https://www.uis.no/forskning",
    "https://www.usn.no/forskning",
    "https://www.nmbu.no/forskning",
    "https://www.oslomet.no/forskning",
    "https://www.himolde.no/forskning/",
    "https://www.hvl.no/forskning/",
    "https://www.inn.no/forskning",
    "https://www.nord.no/forskning",
    "https://kristiania.no/forskning-og-utviklingsarbeid/",
    "https://www.bi.no/forskning/",
    "https://www.nhh.no/forskning/"
]

def main():
    print("🔥 Firecrawl Deep Discovery for forskningsgruppe.no")
    print(f"⚡ Existing groups: {len(data['groups'])}")
    print(f"🎯 Deep crawl targets: {len(DEEP_CRAWL_TARGETS)}")
    print()
    
    all_new_groups = []
    
    for i, url in enumerate(DEEP_CRAWL_TARGETS, 1):
        print(f"[{i}/{len(DEEP_CRAWL_TARGETS)}] Deep crawling {url}...")
        
        # Try crawling first
        crawl_result = firecrawl_crawl(url, max_pages=15)
        
        if crawl_result:
            for page in crawl_result:
                if 'markdown' in page:
                    groups = extract_groups_from_markdown(page['markdown'], page.get('metadata', {}).get('sourceURL', url))
                    all_new_groups.extend(groups)
                    if groups:
                        print(f"  Found {len(groups)} potential groups from {page.get('metadata', {}).get('sourceURL', 'page')}")
        else:
            # Fallback to single scrape
            print(f"  Crawl failed, trying single scrape...")
            scrape_result = firecrawl_scrape(url, include_links=True)
            if scrape_result and 'markdown' in scrape_result:
                groups = extract_groups_from_markdown(scrape_result['markdown'], url)
                all_new_groups.extend(groups)
                if groups:
                    print(f"  Found {len(groups)} potential groups")
        
        time.sleep(2)  # Be nice to the server
        
    print()
    print(f"🎉 Discovery complete!")
    print(f"📊 New groups found: {len(all_new_groups)}")
    
    if all_new_groups:
        print("\n🔍 New groups discovered:")
        for group in all_new_groups:
            print(f"  + {group['name']} ({group['institution']})")
            
        # Add to existing data
        data['groups'].extend(all_new_groups)
        data['lastUpdated'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Save updated data
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ Data updated: {len(data['groups'])} total groups")
        print(f"📁 Saved to {DATA_FILE}")
        
        # Also save to Obsidian
        obsidian_path = "/home/babayaga/JRFO/Prosjekter/forskningsgrupper/data.json"
        with open(obsidian_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📋 Copied to {obsidian_path}")
    
    print("\n🏁 Firecrawl deep discovery completed!")

if __name__ == "__main__":
    main()