"""Run: python pipeline.py --target 50   (add --no-ai for rule-based mode, --rescore-fallback to re-evaluate non-AI rows)"""
import argparse
import json
import logging
from datetime import datetime
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
                "pricing_snippets": [s.strip() for s in str(row.get("pricing_info", "")).split("; ") if s.strip() and s.strip() != "Unknown"],
                "portfolio_urls": str(row.get("portfolio_urls", "")).split("; ") if row.get("portfolio_urls") else [],
                "meta_description": str(row.get("summary", "")),
                "text_excerpt": str(row.get("experience_evidence", "")) + " " + str(row.get("summary", "")),
                "pages_checked": str(row.get("pages_checked", "")).split("; ") if row.get("pages_checked") else [],
                "category_hint": row.get("category", "Other"),
                "source_query": row.get("source_query", ""),
                "collected_at": row.get("collected_at", datetime.now().strftime("%Y-%m-%d")),
            }

        new_row = evaluate.evaluate(rec, use_ai=True)
        for k, v in new_row.items():
            df.at[idx, k] = v
        rescored_count += 1

    df["scored_by"] = df["ai_used"].apply(lambda x: "AI" if str(x).lower() == "true" else "fallback")

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
    ap.add_argument("--refresh", action="store_true", help="ignore cache and re-fetch all providers")
    ap.add_argument("--refresh-domain", type=str, default="", help="ignore cache for a single domain")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    if args.rescore_fallback:
        rescore_fallback()
        return

    records = []
    with tqdm(total=args.target, desc="Collecting") as bar:
        for cand in discover.discover():
            refresh_this = args.refresh or (bool(args.refresh_domain) and cand["domain"] == args.refresh_domain.lower())
            rec = collect.collect_one(cand, refresh=refresh_this)
            if rec:
                records.append(rec)
                bar.update(1)
            if len(records) >= args.target:
                break

    rows = []
    for r in tqdm(records, desc="Evaluating"):
        refresh_this = args.refresh or (bool(args.refresh_domain) and r.get("domain") == args.refresh_domain.lower())
        ev_row = evaluate.evaluate(r, use_ai=not args.no_ai, refresh=refresh_this)
        rows.append(ev_row)
    
    rows = evaluate.dedup_by_domain(rows)
    rows = evaluate.add_shortlist(rows)
    out_dir = "data/test" if args.target < 50 else "data"
    df = export.export(rows, out_dir=out_dir)

    ai_count = int((df["scored_by"] == "AI").sum()) if "scored_by" in df.columns else int(df["ai_used"].sum())
    fallback_count = len(df) - ai_count
    shortlisted_count = int(df["shortlisted"].sum())

    print("\n--- Summary ---")
    print(f"Total providers: {len(df)}")
    print("\nProviders per category:")
    for cat, count in df["category"].value_counts().items():
        print(f"  {cat}: {count}")
    
    print(f"\nShortlisted: {shortlisted_count}")
    print(f"AI used: {ai_count}")
    print(f"Fallback used: {fallback_count}")

    print("\nVerification status counts:")
    for col in ["experience_status", "portfolio_status", "pricing_status"]:
        if col in df.columns:
            vc = df[col].value_counts().to_dict()
            v_str = ", ".join(f"{k}: {v}" for k, v in vc.items())
            print(f"  {col}: {v_str}")

    if evaluate.failure_counts:
        print("\nFailures by status code:")
        for sc, cnt in sorted(evaluate.failure_counts.items()):
            print(f"  HTTP {sc}: {cnt}")
    else:
        print("\nFailures by status code: None")
    print("\nDashboard: streamlit run app.py")


if __name__ == "__main__":
    main()
