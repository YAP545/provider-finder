"""Streamlit dashboard: streamlit run app.py"""
from pathlib import Path
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data" / "providers.csv"
st.set_page_config(page_title="Provider Finder", layout="wide")
st.title("Provider Discovery & Research")

if not DATA.exists():
    st.warning("No dataset yet. Run `python pipeline.py --target 50` first.")
    st.stop()

df = pd.read_csv(DATA).fillna("")
side = st.sidebar
side.header("Filters")
cats = side.multiselect("Category", sorted(df.category.unique()))
countries = side.multiselect("Country", sorted(df.country.unique()))
min_score = side.slider("Min suitability score", 0, 100, 0)
only_short = side.checkbox("Shortlisted only")
has_price = side.checkbox("Has public pricing")
q = side.text_input("Search name / services")

f = df[df.suitability_score >= min_score]
if cats: f = f[f.category.isin(cats)]
if countries: f = f[f.country.isin(countries)]
if only_short: f = f[f.shortlisted == True]  # noqa: E712
if has_price: f = f[f.pricing_info != ""]
if q: f = f[f.name.str.contains(q, case=False) | f.services.str.contains(q, case=False)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Providers", len(f))
c2.metric("Shortlisted", int((f.shortlisted == True).sum()))  # noqa: E712
c3.metric("Avg score", round(f.suitability_score.mean(), 1) if len(f) else 0)
c4.metric("With pricing", int((f.pricing_info != "").sum()))

st.subheader("Average score by category")
if len(f):
    st.bar_chart(f.groupby("category").suitability_score.mean())

st.subheader("Providers")
show = ["rank", "shortlisted", "suitability_score", "name", "website", "category", "country", "services", "email", "pricing_info"]
st.dataframe(
    f[show], use_container_width=True, hide_index=True,
    column_config={
        "website": st.column_config.LinkColumn("website"),
        "suitability_score": st.column_config.ProgressColumn("score", min_value=0, max_value=100, format="%.0f"),
    },
)
st.download_button("Download filtered CSV", f.to_csv(index=False).encode("utf-8-sig"), "providers_filtered.csv")

st.subheader("Provider detail")
if len(f):
    row = f[f.name == st.selectbox("Select", f.name.tolist())].iloc[0]
    a, b = st.columns(2)
    a.markdown(f"**{row['name']}** — {row['category']} ({row['provider_type']})  \n{row['website']}")
    a.write(row["summary"])
    a.write(f"**Experience evidence:** {row['experience_evidence']}")
    a.write(f"**Red flags:** {row['red_flags'] or 'none noted'}")
    b.write(f"**Country:** {row['country']} _(source: {row['country_source']})_")
    b.write(f"**Email:** {row['email'] or 'not found'}  |  **Phone:** {row['phone'] or 'not found'}")
    b.write(f"**Pricing seen:** {row['pricing_info'] or 'not published'}")
    b.write(f"**Portfolio:** {row['portfolio_urls'] or 'not found'}")
    b.write(f"**Sub-scores** skill {row['skill_relevance']} · experience {row['experience_score']} · "
            f"portfolio {row['portfolio_score']} · transparency {row['transparency_score']}")
    b.caption(f"Scored by {'AI' if row['ai_used'] else 'keyword rules'} · confidence: {row['confidence']}")
