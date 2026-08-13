import urllib.request
import re

url = 'https://legal-corpus-hub.preview.emergentagent.com/static/js/bundle.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

# Search for react component routes, titles, placeholders, navigation tabs
routes = re.findall(r'path:"([^"]+)"', content)
print("ROUTES:", routes)

# Search for navigation items
nav_matches = re.findall(r'\{[^{}]*name:"([^"]+)"[^{}]*\}', content)
print("NAV MATCHES:", nav_matches)

# Search for headings and titles
titles = re.findall(r'title:"([^"]+)"', content)
print("TITLES:", set(titles[:30]))

# Search for text in strings
strings = re.findall(r'"([A-Z][A-Za-z0-9\s—\-\.]{4,60})"', content)
filtered_strings = sorted(list(set([s for s in strings if any(w in s.lower() for w in ['nyaya', 'nova', 'vault', 'matter', 'research', 'map', 'deadline', 'intelligence', 'corpus', 'risk', 'statute', 'precedent', 'command'])])))

print("\n--- BRANDING & SECTION HEADINGS ---")
for s in filtered_strings[:60]:
    print("  •", s)
