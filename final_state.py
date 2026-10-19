import sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
df = pd.read_csv('data/providers.csv')
print('Row count:', len(df))
print()
print('pricing_status counts:')
print(df['pricing_status'].value_counts().to_string())
print()
shortlisted = df[df['shortlisted']].sort_values('suitability_score', ascending=False)
print('Shortlist (' + str(len(shortlisted)) + '):')
for idx, r in shortlisted.iterrows():
    cat = r['category']
    name = r['name']
    score = r['suitability_score']
    ps = r['pricing_status']
    print('  [' + cat + '] ' + name + ' | score=' + str(score) + ' | pricing=' + ps)
