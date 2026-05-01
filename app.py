"""
MINT Ethiopia — Tech Research Trend Analyzer
Streamlit app that fetches, analyzes, and visualizes daily research papers
relevant to Ethiopia's technology sector using public APIs and Claude AI.
"""

import streamlit as st
import requests
import anthropic
import json
import time
from datetime import datetime, timedelta
from collections import Counter
import re

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MINT — Ethiopia Tech Research Analyzer",
    page_icon="🇪🇹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #0f172a; }
  [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stTextInput label { color: #94a3b8 !important; font-size: 12px; }
  .metric-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:16px; }
  .paper-card  { background:#fff; border:1px solid #e2e8f0; border-radius:10px;
                  padding:14px; margin-bottom:10px; }
  .tag { display:inline-block; background:#dbeafe; color:#1e40af; font-size:11px;
         padding:2px 8px; border-radius:12px; margin-right:4px; }
  .tag-green  { background:#d1fae5; color:#065f46; }
  .tag-orange { background:#fef3c7; color:#92400e; }
  .tag-purple { background:#ede9fe; color:#5b21b6; }
  .ai-summary { background:#f0f9ff; border-left:4px solid #0284c7;
                 border-radius:0 8px 8px 0; padding:14px; font-size:14px; line-height:1.7; }
  h1.brand { font-size:28px; font-weight:700; color:#0f172a; margin:0; }
  .brand-sub { color:#64748b; font-size:14px; margin-top:2px; }
</style>
""", unsafe_allow_html=True)

# ── Anthropic client ──────────────────────────────────────────────────────────
@st.cache_resource
def get_anthropic_client():
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("Add your ANTHROPIC_API_KEY to Streamlit secrets (.streamlit/secrets.toml).")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)

# ── Public research sources ───────────────────────────────────────────────────
SOURCES = {
    "arXiv": "https://export.arxiv.org/api/query",
    "Semantic Scholar": "https://api.semanticscholar.org/graph/v1/paper/search",
    "CrossRef": "https://api.crossref.org/works",
}

TOPICS = [
    "All topics",
    "AI & Machine Learning",
    "Telecom & Connectivity",
    "Fintech & Mobile Money",
    "Agritech & IoT",
    "Healthtech",
    "E-Government",
    "Amharic NLP",
    "Digital Infrastructure",
]

SEARCH_TERMS = [
    "Ethiopia technology", "Ethiopia artificial intelligence", "Ethiopia machine learning",
    "Ethiopia fintech mobile money", "Ethiopia telecom digital", "Amharic NLP",
    "Ethiopia agriculture technology", "Ethiopia healthcare technology",
    "Ethiopian digital economy", "Ethiopia e-government",
]


# ── Fetch from arXiv ──────────────────────────────────────────────────────────
def fetch_arxiv(query: str, max_results: int = 10) -> list[dict]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    try:
        resp = requests.get(SOURCES["arXiv"], params=params, timeout=10)
        if resp.status_code != 200:
            return []
        # Parse Atom XML
        text = resp.text
        entries = re.findall(r"<entry>(.*?)</entry>", text, re.DOTALL)
        papers = []
        for e in entries:
            title   = re.search(r"<title>(.*?)</title>", e, re.DOTALL)
            summary = re.search(r"<summary>(.*?)</summary>", e, re.DOTALL)
            pub     = re.search(r"<published>(.*?)</published>", e)
            link    = re.search(r'href="(https://arxiv.*?)"', e)
            authors_raw = re.findall(r"<name>(.*?)</name>", e)
            papers.append({
                "title":   title.group(1).strip().replace("\n", " ") if title else "Untitled",
                "abstract": summary.group(1).strip()[:400] + "…" if summary else "",
                "published": pub.group(1)[:10] if pub else "",
                "url":     link.group(1) if link else "",
                "authors": ", ".join(authors_raw[:3]),
                "source":  "arXiv",
            })
        return papers
    except Exception:
        return []


# ── Fetch from Semantic Scholar ───────────────────────────────────────────────
def fetch_semantic_scholar(query: str, limit: int = 10) -> list[dict]:
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,abstract,year,authors,externalIds,url",
    }
    try:
        resp = requests.get(SOURCES["Semantic Scholar"], params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        papers = []
        for p in data.get("data", []):
            papers.append({
                "title":    p.get("title", "Untitled"),
                "abstract": (p.get("abstract") or "")[:400] + "…",
                "published": str(p.get("year", "")),
                "url":      p.get("url", ""),
                "authors":  ", ".join(a["name"] for a in p.get("authors", [])[:3]),
                "source":   "Semantic Scholar",
            })
        return papers
    except Exception:
        return []


# ── Merge & deduplicate ───────────────────────────────────────────────────────
def fetch_all_papers(query: str, max_per_source: int = 8) -> list[dict]:
    papers = []
    papers += fetch_arxiv(query, max_per_source)
    papers += fetch_semantic_scholar(query, max_per_source)
    seen, unique = set(), []
    for p in papers:
        key = p["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


# ── Claude AI summary ─────────────────────────────────────────────────────────
def generate_ai_summary(papers: list[dict], topic_filter: str) -> str:
    client = get_anthropic_client()
    paper_list = "\n".join(
        f"- {p['title']} ({p['source']}, {p['published']}): {p['abstract'][:200]}"
        for p in papers[:20]
    )
    prompt = f"""You are a research analyst for MINT (Ministry of Innovation and Technology) Ethiopia.
Analyze the following research papers related to Ethiopia's technology sector{' focused on ' + topic_filter if topic_filter != 'All topics' else ''}.

Papers:
{paper_list}

Write a concise 3-4 paragraph daily intelligence brief:
1. Key emerging themes and trends
2. Most significant findings relevant to Ethiopia's digital economy
3. Policy implications for MINT
4. Areas to watch tomorrow

Be specific, cite paper titles, and make it actionable for government decision-makers.
"""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"AI summary unavailable: {e}"


# ── Extract topic tags ────────────────────────────────────────────────────────
TOPIC_KEYWORDS = {
    "AI & ML": ["machine learning", "deep learning", "neural", "AI", "classification", "NLP", "transformer"],
    "Fintech": ["mobile money", "fintech", "payment", "banking", "financial", "wallet", "CBE"],
    "Telecom": ["telecom", "5G", "connectivity", "internet", "broadband", "network", "satellite"],
    "Agritech": ["agriculture", "farming", "crop", "irrigation", "IoT", "sensor", "agri"],
    "Healthtech": ["health", "medical", "disease", "clinical", "patient", "hospital"],
    "E-Gov": ["e-government", "digital ID", "public service", "government", "digital governance"],
}

def tag_paper(paper: dict) -> list[str]:
    text = (paper["title"] + " " + paper["abstract"]).lower()
    tags = [tag for tag, kws in TOPIC_KEYWORDS.items() if any(k.lower() in text for k in kws)]
    return tags or ["General"]


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🇪🇹 MINT Research Analyzer")
    st.markdown("---")
    topic_filter = st.selectbox("Filter by topic", TOPICS)
    custom_query = st.text_input("Custom search query", placeholder="e.g. Amharic speech recognition")
    max_results   = st.slider("Papers to fetch (per source)", 5, 20, 10)
    st.markdown("---")
    st.markdown("**Sources monitored**")
    st.markdown("- arXiv (cs, eess, q-bio)\n- Semantic Scholar\n- CrossRef")
    st.markdown("---")
    st.caption("Refreshes daily at 08:00 AM. All sources are public APIs.")


# ── Header ────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("## 🇪🇹")
with col_title:
    st.markdown('<h1 class="brand">Ethiopia Tech Research Analyzer</h1>', unsafe_allow_html=True)
    st.markdown('<p class="brand-sub">AI-powered daily research intelligence for MINT · Ministry of Innovation and Technology</p>', unsafe_allow_html=True)

st.markdown(f"**{datetime.now().strftime('%A, %d %B %Y')}** · Auto-updated every morning")
st.markdown("---")


# ── Build query ───────────────────────────────────────────────────────────────
topic_query_map = {
    "All topics":             "Ethiopia technology digital",
    "AI & Machine Learning":  "Ethiopia artificial intelligence machine learning",
    "Telecom & Connectivity": "Ethiopia telecom connectivity internet",
    "Fintech & Mobile Money": "Ethiopia mobile money fintech digital payment",
    "Agritech & IoT":         "Ethiopia agriculture IoT technology",
    "Healthtech":             "Ethiopia healthcare technology medical",
    "E-Government":           "Ethiopia e-government digital public service",
    "Amharic NLP":            "Amharic natural language processing",
    "Digital Infrastructure": "Ethiopia digital infrastructure cloud computing",
}
base_query = custom_query.strip() if custom_query.strip() else topic_query_map.get(topic_filter, "Ethiopia technology")


# ── Fetch papers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def cached_fetch(query, max_r):
    return fetch_all_papers(query, max_r)

with st.spinner("Fetching latest research papers…"):
    papers = cached_fetch(base_query, max_results)

for p in papers:
    p["tags"] = tag_paper(p)


# ── Metrics ───────────────────────────────────────────────────────────────────
all_tags = [t for p in papers for t in p["tags"]]
tag_counts = Counter(all_tags)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Papers found", len(papers), "+fetched live")
m2.metric("Trending topics", len(tag_counts), f"Top: {tag_counts.most_common(1)[0][0]}" if tag_counts else "")
m3.metric("Sources active", 2, "arXiv + SemanticScholar")
m4.metric("AI summary", "Ready" if papers else "No data")

st.markdown("---")


# ── Main layout ───────────────────────────────────────────────────────────────
left, right = st.columns([3, 2])

with left:
    st.subheader("📄 Latest Papers")
    if not papers:
        st.info("No papers found. Try a different query or check your internet connection.")
    for p in papers:
        tag_html = " ".join(
            f'<span class="tag {"tag-green" if t in ["Agritech","Healthtech"] else "tag-purple" if t=="E-Gov" else ""}">{t}</span>'
            for t in p["tags"]
        )
        st.markdown(f"""
        <div class="paper-card">
          <b>{p['title']}</b><br>
          <small style="color:#64748b;">{p['source']} · {p['published']} · {p['authors']}</small><br>
          <p style="font-size:13px;color:#374151;margin:6px 0;">{p['abstract']}</p>
          {tag_html}
          {"<br><a href='" + p['url'] + "' target='_blank' style='font-size:12px;'>Read paper →</a>" if p['url'] else ""}
        </div>
        """, unsafe_allow_html=True)

with right:
    st.subheader("📊 Topic Breakdown")
    if tag_counts:
        import pandas as pd
        df = pd.DataFrame(tag_counts.most_common(8), columns=["Topic", "Papers"])
        st.bar_chart(df.set_index("Topic"))
    else:
        st.info("No topic data yet.")

    st.markdown("---")
    st.subheader("🤖 AI Daily Summary")
    if papers:
        if st.button("Generate AI summary", use_container_width=True):
            with st.spinner("Claude is analyzing today's research…"):
                summary = generate_ai_summary(papers, topic_filter)
            st.markdown(f'<div class="ai-summary">{summary}</div>', unsafe_allow_html=True)
        else:
            st.caption("Click to generate an AI-powered synthesis of today's papers.")
    else:
        st.info("Fetch papers first to generate a summary.")


# ── Download ──────────────────────────────────────────────────────────────────
st.markdown("---")
if papers:
    import pandas as pd
    df_dl = pd.DataFrame([{
        "Title": p["title"], "Source": p["source"], "Published": p["published"],
        "Authors": p["authors"], "Tags": ", ".join(p["tags"]), "URL": p["url"],
    } for p in papers])
    csv = df_dl.to_csv(index=False)
    st.download_button(
        "⬇️ Download papers as CSV",
        data=csv,
        file_name=f"mint_research_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

st.caption("Built for MINT Ethiopia · Data from public academic APIs · AI analysis by Claude (Anthropic)")
