import urllib.request
import re

url = 'https://legal-corpus-hub.preview.emergentagent.com/static/js/bundle.js'
print(f"Fetching {url}...")

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    print(f"Downloaded bundle.js ({len(content)} bytes)")
    
    # Extract visible text strings & titles
    strings = re.findall(r'"([^"\\]{3,120})"', content)
    
    keywords = ['nyaya', 'legal', 'corpus', 'vault', 'intelligence', 'search', 'graph', 'clause', 'risk', 'dashboard', 'proactive', 'compliance', 'deadlines', 'briefing', 'model', 'dataset', 'classifier']
    
    matched = [s for s in strings if any(k in s.lower() for k in keywords)]
    
    print("\n--- EXTRACTED UI KEYWORDS & TITLES ---")
    for s in set(matched[:100]):
        print("-", s)
        
except Exception as e:
    print("Error:", e)
