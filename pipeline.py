"""Run: python pipeline.py --target 50   (add --no-ai for rule-based mode)"""
import argparse
import logging

from tqdm import tqdm

import collect
import discover
import evaluate
import export


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50, help="number of providers to collect")
    ap.add_argument("--no-ai", action="store_true", help="skip LLM, use keyword heuristics")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

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
    rows = evaluate.add_shortlist(rows)
    df = export.export(rows)
    print(f"\nSaved {len(df)} providers to data/providers.csv and data/providers.xlsx "
          f"({int(df.shortlisted.sum())} shortlisted, AI used for {int(df.ai_used.sum())}).")
    print("Dashboard: streamlit run app.py")


if __name__ == "__main__":
    main()
