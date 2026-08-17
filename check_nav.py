import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for duplicate pbix-modal-overlay IDs
pbix_count = content.count('id="pbix-modal-overlay"')
print(f'pbix-modal-overlay count: {pbix_count}')

# Check switchView calls
import re
sv = re.findall('onclick="switchView', content)
print(f'switchView onclick calls: {len(sv)}')

# Check for tab-view sections
tv = re.findall('id="view-', content)
print(f'tab-view sections: {tv}')

# Check that all views referenced in nav have corresponding sections
nav_views = re.findall("switchView\('(\w+)'", content)
section_ids = re.findall('id="view-(\w+)"', content)
print(f'\nNav references: {set(nav_views)}')
print(f'Section IDs: {set(section_ids)}')
missing = set(nav_views) - set(section_ids)
print(f'Missing sections: {missing}')
