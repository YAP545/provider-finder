import sys
import json
import re
from pathlib import Path
import pandas as pd
import collect

sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv('data/providers.csv')
print(f'Total rows in providers.csv: {len(df)}')

status_changes = []
info_changes = []

for idx, r in df.iterrows():
    dom = r['website'].split('//')[-1].split('/')[0].lower().removeprefix('www.')
    cache_file = Path(f'data/cache/{dom}.json')
    text = ''
    snippets = []
    if cache_file.exists():
        data = json.loads(cache_file.read_text(encoding='utf-8'))
        text = data.get('text_excerpt', '')
        snippets = data.get('pricing_snippets', [])
    
    # Run extract_pricing
    prices = collect.extract_pricing(text)
    if not prices and snippets:
        for s in snippets:
            p_sub = collect.extract_pricing(s)
            for p in p_sub:
                if p not in prices:
                    prices.append(p)
    
    # Fallback to existing pricing_info if no cache text
    if not prices and not text and r['pricing_info'] != 'Unknown':
        prices = collect.extract_pricing(str(r['pricing_info']))

    prices = prices[:3]
    new_info = '; '.join(prices) if prices else 'Unknown'
    new_status = 'Verified' if new_info != 'Unknown' else 'Unknown'
    
    old_info = str(r['pricing_info'])
    old_status = str(r['pricing_status'])
    
    if old_status != new_status:
        status_changes.append({
            'name': r['name'],
            'old_status': old_status,
            'new_status': new_status,
            'old_info': old_info,
            'new_info': new_info
        })
    elif old_info != new_info:
        info_changes.append({
            'name': r['name'],
            'status': new_status,
            'old_info': old_info,
            'new_info': new_info
        })

print(f'\n--- Rows whose pricing_status CHANGED ({len(status_changes)}) ---')
for c in status_changes:
    print(f"Name: {c['name']}")
    print(f"  Status: {c['old_status']} -> {c['new_status']}")
    print(f"  Old info: {c['old_info']}")
    print(f"  New info: {c['new_info']}\n")

print(f'\n--- Rows whose pricing_status stayed the same but info changed ({len(info_changes)}) ---')
for c in info_changes:
    print(f"Name: {c['name']} [{c['status']}]")
    print(f"  Old info: {c['old_info']}")
    print(f"  New info: {c['new_info']}\n")
