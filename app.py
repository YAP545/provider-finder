"""Streamlit dashboard: streamlit run app.py"""
import io
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

# Gracefully handle missing scored_by column
if "scored_by" not in df.columns:
    if "ai_used" in df.columns:
        df["scored_by"] = df["ai_used"].apply(
            lambda x: "AI" if str(x).lower() == "true" else ("fallback" if str(x).lower() == "false" else "unknown")
        )
    else:
        df["scored_by"] = "unknown"

side = st.sidebar
side.header("Filters")
cats = side.multiselect("Category", sorted(df.category.unique()))
countries = side.multiselect("Country", sorted(df.country.unique()))
min_score = side.slider("Min suitability score", 0, 100, 0)
only_short = side.checkbox("Shortlisted only")
only_ai = side.checkbox("AI-scored only")
has_price = side.checkbox("Has public pricing")
q = side.text_input("Search name / services")

f = df[df.suitability_score >= min_score]
if cats:
    f = f[f.category.isin(cats)]
if countries:
    f = f[f.country.isin(countries)]
if only_short:
    f = f[f.shortlisted == True]  # noqa: E712
if only_ai:
    f = f[f.scored_by == "AI"]
if has_price:
    f = f[f.pricing_info != ""]
if q:
    f = f[f.name.str.contains(q, case=False) | f.services.str.contains(q, case=False)]

# Table sort option
sort_col = side.selectbox("Sort table by", ["suitability_score", "rank", "name", "skill_relevance", "experience_score"], index=0)
sort_asc = side.checkbox("Ascending order", value=False)
f = f.sort_values(by=sort_col, ascending=sort_asc)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Providers", len(f))
c2.metric("Shortlisted", int((f.shortlisted == True).sum()))  # noqa: E712
c3.metric("Avg score", round(f.suitability_score.mean(), 1) if len(f) else 0)
c4.metric("With pricing", int((f.pricing_info != "").sum()))
c5.metric("AI-scored", int((f.scored_by == "AI").sum()))

st.subheader("Average score by category")
if len(f):
    st.bar_chart(f.groupby("category").suitability_score.mean())

st.subheader("Providers")
show = ["rank", "shortlisted", "suitability_score", "scored_by", "name", "website", "category", "country", "services", "email", "pricing_info"]
# Show columns that exist in f
valid_show = [c for c in show if c in f.columns]
st.dataframe(
    f[valid_show], use_container_width=True, hide_index=True,
    column_config={
        "website": st.column_config.LinkColumn("website"),
        "suitability_score": st.column_config.ProgressColumn("score", min_value=0, max_value=100, format="%.0f"),
    },
)

# Download buttons for CSV and Excel
d1, d2 = st.columns(2)
d1.download_button(
    "📥 Download filtered CSV",
    f.to_csv(index=False).encode("utf-8-sig"),
    "providers_filtered.csv",
    "text/csv",
    use_container_width=True,
)

excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    f.to_excel(writer, index=False, sheet_name="Filtered Providers")
excel_data = excel_buffer.getvalue()

d2.download_button(
    "📥 Download filtered Excel (.xlsx)",
    excel_data,
    "providers_filtered.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.divider()

# Compare section: compare 2 or 3 providers side-by-side
st.subheader("Compare Providers")
compare_options = f.name.tolist() if len(f) else df.name.tolist()
selected_compare = st.multiselect("Select 2 or 3 providers to compare side by side", compare_options, max_selections=3)

if selected_compare:
    comp_df = df[df.name.isin(selected_compare)]
    comp_cols = st.columns(len(selected_compare))
    for col, name in zip(comp_cols, selected_compare):
        prov_rows = comp_df[comp_df.name == name]
        if not prov_rows.empty:
            p = prov_rows.iloc[0]
            with col:
                st.markdown(f"### {p['name']}")
                st.caption(f"{p['website']} | {p['category']} ({p['provider_type']})")
                
                badge_type = p.get('scored_by', 'unknown')
                if badge_type == "AI":
                    st.success("🤖 Scored by: AI")
                elif badge_type == "fallback":
                    st.info("⚙️ Scored by: Fallback (Keyword rules)")
                else:
                    st.caption(f"Scored by: {badge_type}")

                st.metric("Suitability Score", f"{p['suitability_score']} / 100")
                st.markdown("**Sub-scores:**")
                st.write(f"Skill: {p['skill_relevance']} / 10")
                st.progress(min(1.0, max(0.0, float(p['skill_relevance']) / 10.0)))
                st.write(f"Experience: {p['experience_score']} / 10")
                st.progress(min(1.0, max(0.0, float(p['experience_score']) / 10.0)))
                st.write(f"Portfolio: {p['portfolio_score']} / 10")
                st.progress(min(1.0, max(0.0, float(p['portfolio_score']) / 10.0)))
                st.write(f"Transparency: {p['transparency_score']} / 10")
                st.progress(min(1.0, max(0.0, float(p['transparency_score']) / 10.0)))

                st.markdown(f"**Country:** {p['country']}")
                st.markdown(f"**Email:** {p['email'] or 'None'}")
                st.markdown(f"**Pricing:** {p['pricing_info'] or 'Not published'}")
                st.markdown(f"**Services:** {p['services'] or 'None'}")
                st.markdown(f"**Summary:** {p['summary']}")

st.divider()

st.subheader("Provider detail")
if len(f):
    row = f[f.name == st.selectbox("Select provider for detail", f.name.tolist())].iloc[0]
    a, b = st.columns(2)
    with a:
        st.markdown(f"### {row['name']} — {row['category']} ({row['provider_type']})")
        st.markdown(f"[{row['website']}]({row['website']})")
        
        # Scored_by badge
        s_by = row.get("scored_by", "unknown")
        if s_by == "AI":
            st.success("🤖 Scored by: AI (Gemini)")
        elif s_by == "fallback":
            st.warning("⚙️ Scored by: Fallback (Keyword rules)")
        else:
            st.info(f"Scored by: {s_by}")

        st.write(row["summary"])
        st.write(f"**Experience evidence:** {row['experience_evidence']}")
        st.write(f"**Red flags:** {row['red_flags'] or 'none noted'}")

    with b:
        st.write(f"**Country:** {row['country']} _(source: {row['country_source']})_")
        st.write(f"**Email:** {row['email'] or 'not found'}  |  **Phone:** {row['phone'] or 'not found'}")
        st.write(f"**Pricing seen:** {row['pricing_info'] or 'not published'}")
        st.write(f"**Portfolio:** {row['portfolio_urls'] or 'not found'}")
        
        st.markdown("#### Sub-scores")
        st.write(f"Skill relevance: **{row['skill_relevance']}** / 10")
        st.progress(min(1.0, max(0.0, float(row['skill_relevance']) / 10.0)))
        
        st.write(f"Experience: **{row['experience_score']}** / 10")
        st.progress(min(1.0, max(0.0, float(row['experience_score']) / 10.0)))
        
        st.write(f"Portfolio: **{row['portfolio_score']}** / 10")
        st.progress(min(1.0, max(0.0, float(row['portfolio_score']) / 10.0)))
        
        st.write(f"Transparency: **{row['transparency_score']}** / 10")
        st.progress(min(1.0, max(0.0, float(row['transparency_score']) / 10.0)))

        st.caption(f"Suitability score: {row['suitability_score']}/100 · Confidence: {row['confidence']}")
