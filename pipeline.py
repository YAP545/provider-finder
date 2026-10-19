"""Run: python pipeline.py --target 50   (add --no-ai for rule-based mode, --rescore-fallback to re-evaluate non-AI rows)"""
import argparse
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from tqdm import tqdm

import collect
import config
import discover
import evaluate
import export


def rescore_fallback():
    csv_path = Path("data/providers.csv")
    if not csv_path.exists():
        print("data/providers.csv not found.")
        return

    df = pd.read_csv(csv_path).fillna("")
    if "ai_used" not in df.columns:
        print("ai_used column not in data/providers.csv.")
        return

    # Identify rows where AI was not used
    # ai_used can be boolean or string ('True'/'False')
    mask = (df["ai_used"] == False) | (df["ai_used"] == "False") | (df["ai_used"] == "")
    indices = df[mask].index.tolist()
    print(f"Found {len(indices)} rows where AI was not used to rescore.")

    rescored_count = 0
    records_cache_dir = Path("data/cache")

    for idx in tqdm(indices, desc="Rescoring fallback"):
        row = df.loc[idx]
        website = str(row.get("website", "")).strip()
        domain = urlparse(website).netloc.lower().removeprefix("www.").rstrip("/")
        cache_file = records_cache_dir / f"{domain}.json"
        
        rec = None
        if cache_file.exists():
            try:
                rec = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                rec = None
        
        # If cache file doesn't exist under domain, try to construct minimal rec from row
        if not rec:
            rec = {
                "name": row.get("name", ""),
                "website": website,
                "domain": domain,
                "country": row.get("country", "Unknown"),
                "country_source": row.get("country_source", "not found"),
                "email": row.get("email", ""),
                "phone": row.get("phone", ""),
                "social_links": str(row.get("social_links", "")).split("; ") if row.get("social_links") else [],
                "pricing_snippets": str(row.get("pricing_info", "")).split("; ") if row.get("pricing_info") else [],
                "portfolio_urls": str(row.get("portfolio_urls", "")).split("; ") if row.get("portfolio_urls") else [],
                "meta_description": str(row.get("summary", "")),
                "text_excerpt": str(row.get("experience_evidence", "")) + " " + str(row.get("summary", "")),
                "pages_checked": str(row.get("pages_checked", "")).split("; ") if row.get("pages_checked") else [],
                "category_hint": row.get("category", "Other"),
                "source_query": row.get("source_query", ""),
                "collected_at": row.get("collected_at", ""),
            }

        # Attempt evaluate with AI
        new_row = evaluate.evaluate(rec, use_ai=True)
        # Update row fields in df
        for k, v in new_row.items():
            if k in df.columns:
                df.at[idx, k] = v
        rescored_count += 1

    # Ensure scored_by column exists
    if "scored_by" not in df.columns:
        df["scored_by"] = df["ai_used"].apply(lambda x: "AI" if str(x).lower() == "true" else "fallback")
    else:
        df["scored_by"] = df["ai_used"].apply(lambda x: "AI" if str(x).lower() == "true" else "fallback")

    # Dedup and re-sort / re-shortlist
    rows = df.to_dict(orient="records")
    rows = evaluate.dedup_by_domain(rows)
    rows = evaluate.add_shortlist(rows)
    out_df = export.export(rows)

    ai_count = int((out_df["scored_by"] == "AI").sum())
    fallback_count = int((out_df["scored_by"] == "fallback").sum())
    shortlisted_count = int(out_df["shortlisted"].sum())
    print(f"\nRescored {rescored_count} rows. Updated data/providers.csv and data/providers.xlsx.")
    print(f"Total providers: {len(out_df)} | Shortlisted: {shortlisted_count} | AI used: {ai_count} | Fallback used: {fallback_count}")
    if evaluate.failure_counts:
        print("Failure counts by status code:")
        for sc, cnt in sorted(evaluate.failure_counts.items()):
            print(f"  HTTP {sc}: {cnt}")
    else:
        print("Failure counts by status code: None")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50, help="number of providers to collect")
    ap.add_argument("--no-ai", action="store_true", help="skip LLM, use keyword heuristics")
    ap.add_argument("--rescore-fallback", action="store_true", help="re-score only rows where AI was not used")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    if args.rescore_fallback:
        rescore_fallback()
        return

    records = []
    with tqdm(total=args.target, desc="Collecting") as bar:
        for cand in discover.discover():
            rec = collect.collect_one(cand)
            if rec:
                records.append(rec)
                bar.update(1)
            if len(records) >= args.target:
                break

    rows = [evaluate.evaluate(r, use_ai=not args.no_ai) for r in tqdm(records, desc="Evaluating")]
    
    # Dedup by normalized domain keeping higher-scored row
    rows = evaluate.dedup_by_domain(rows)
    rows = evaluate.add_shortlist(rows)
    df = export.export(rows)

    ai_count = int((df["scored_by"] == "AI").sum()) if "scored_by" in df.columns else int(df["ai_used"].sum())
    fallback_count = len(df) - ai_count
    shortlisted_count = int(df["shortlisted"].sum())

    print("\n--- Summary ---")
    print(f"Total providers: {len(df)}")
    print(f"Shortlisted: {shortlisted_count}")
    print(f"AI used: {ai_count}")
    print(f"Fallback used: {fallback_count}")
    if evaluate.failure_counts:
        print("Failures by status code:")
        for sc, cnt in sorted(evaluate.failure_counts.items()):
            print(f"  HTTP {sc}: {cnt}")
    else:
        print("Failures by status code: None")
    print("Dashboard: streamlit run app.py")


if __name__ == "__main__":
    main()
