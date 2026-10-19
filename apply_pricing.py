"""
Apply updated pricing extraction to all 50 rows using cached data.
Rebuilds strengths/limitations and shortlist.
"""
import sys
import json
import re
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Import project modules
import collect
import evaluate
import config
import export

CACHE = Path("data/cache")

# ------------------------------------------------------------------
# Backup first
# ------------------------------------------------------------------
from pathlib import Path as P
backup_dir = P("data/backup")
backup_dir.mkdir(parents=True, exist_ok=True)
import shutil
for fname in ["data/providers.csv", "data/providers.xlsx"]:
    if Path(fname).exists():
        shutil.copy2(fname, backup_dir / Path(fname).name)
print("Backup done.")

# ------------------------------------------------------------------
# Load existing data
# ------------------------------------------------------------------
df = pd.read_csv("data/providers.csv")
print(f"Loaded {len(df)} rows from data/providers.csv")
assert len(df) == 50, f"Expected 50 rows, got {len(df)}"

rows = df.to_dict("records")

# ------------------------------------------------------------------
# Re-extract pricing for each row using cached text
# ------------------------------------------------------------------
before_after = []

for r in rows:
    # Determine cache file from website
    dom = r["website"].split("//")[-1].split("/")[0].lower().removeprefix("www.")
    cache_file = CACHE / f"{dom}.json"

    text = ""
    snippets = []
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            text = data.get("text_excerpt", "")
            snippets = data.get("pricing_snippets", [])
        except Exception:
            pass

    # Run extract_pricing on full text
    prices = collect.extract_pricing(text)

    # If no hits from text, try individual pricing snippets
    if not prices and snippets:
        for snip in snippets:
            found = collect.extract_pricing(snip)
            for p in found:
                if p not in prices:
                    prices.append(p)
                if len(prices) >= 3:
                    break

    prices = prices[:3]

    old_pricing_info = str(r.get("pricing_info", ""))
    old_pricing_status = str(r.get("pricing_status", ""))

    new_pricing_info = "; ".join(prices) if prices else "Unknown"
    new_pricing_status = "Verified" if prices else "Unknown"
    new_pricing_url = r["website"] if prices else ""

    changed = (old_pricing_info != new_pricing_info or old_pricing_status != new_pricing_status)
    if changed:
        before_after.append({
            "name": r["name"],
            "old_status": old_pricing_status,
            "new_status": new_pricing_status,
            "old_info": old_pricing_info,
            "new_info": new_pricing_info,
        })

    # Update row
    r["pricing_info"] = new_pricing_info
    r["pricing_status"] = new_pricing_status
    r["pricing_source_url"] = new_pricing_url

    # ------------------------------------------------------------------
    # Rebuild strengths and limitations to match new pricing_status
    # ------------------------------------------------------------------
    strengths = str(r.get("strengths", ""))
    limitations = str(r.get("limitations", ""))

    if new_pricing_status == "Verified":
        # Should mention verified rates; if it doesn't add it
        if "verified rates" not in strengths and "public pricing" not in strengths.lower():
            # Check if strengths ends with period
            strengths = strengths.rstrip(".") + " Publishes verified rates."
        # Remove "Pricing not publicly listed" from limitations if present
        limitations = limitations.replace("Pricing not publicly listed on the site. ", "")
        limitations = limitations.replace("Pricing not publicly listed on the site.", "").strip()
    else:
        # Remove any "verified rates" or "Publishes verified rates" from strengths
        strengths = re.sub(r"\s*and publishes verified rates\.", ".", strengths, flags=re.I)
        strengths = re.sub(r"\s*Publishes verified rates\.", "", strengths, flags=re.I).strip()
        # Ensure "Pricing not publicly listed on the site." is in limitations
        pricing_notice = "Pricing not publicly listed on the site."
        if pricing_notice not in limitations:
            limitations = (pricing_notice + " " + limitations).strip()

    r["strengths"] = strengths.strip()
    r["limitations"] = limitations.strip()

# ------------------------------------------------------------------
# Print before/after table
# ------------------------------------------------------------------
print(f"\n--- Rows with pricing changes ({len(before_after)}) ---")
for c in before_after:
    print(f"\n  {c['name']}")
    print(f"    Status : {c['old_status']} -> {c['new_status']}")
    print(f"    Old    : {c['old_info'][:80]}")
    print(f"    New    : {c['new_info']}")

# ------------------------------------------------------------------
# Rebuild shortlist
# ------------------------------------------------------------------
rows = evaluate.add_shortlist(rows)
shortlisted = [r["name"] for r in rows if r["shortlisted"]]
print(f"\n--- Shortlist ({len(shortlisted)}) ---")
for name in shortlisted:
    r = next(x for x in rows if x["name"] == name)
    print(f"  [{r['category']}] {r['name']} | score={r['suitability_score']}")

# ------------------------------------------------------------------
# Save
# ------------------------------------------------------------------
export.export(rows)
df_new = pd.read_csv("data/providers.csv")
print(f"\nSaved. Row count: {len(df_new)} (expected 50)")
assert len(df_new) == 50, f"Row count mismatch! {len(df_new)}"

# ------------------------------------------------------------------
# Verify pricing_status consistency
# ------------------------------------------------------------------
print("\n--- Verifying pricing_status vs strengths/limitations ---")
errors = 0
for r in rows:
    s = str(r.get("strengths", "")).lower()
    ps = str(r.get("pricing_status", ""))
    if ps == "Verified":
        if "verified rates" not in s and "public pricing" not in s:
            print(f"  WARNING: {r['name']} is Verified but strengths don't mention rates: {s[:80]}")
            errors += 1
    else:
        if "verified rates" in s or "public pricing" in s:
            print(f"  ERROR: {r['name']} is {ps} but strengths mention pricing: {s[:80]}")
            errors += 1
print(f"Errors: {errors}")
print("\nDone.")
