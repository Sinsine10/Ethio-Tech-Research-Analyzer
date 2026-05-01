# MINT Ethiopia — Tech Research Trend Analyzer

AI-powered daily research intelligence for Ethiopia's technology sector.

## What it does

- Fetches research papers daily from **arXiv** and **Semantic Scholar** (free public APIs)
- Filters for Ethiopia-relevant tech topics (AI, Fintech, Telecom, Agritech, Healthtech, etc.)
- Auto-tags papers by topic
- Generates an AI daily brief using **Claude** (Anthropic)
- Lets users download results as CSV

---

## Quickstart (local)

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "your-key-here"
```

Run:
```bash
streamlit run app.py
```

---

## Deploy to Streamlit Cloud (recommended — FREE)

1. Push this folder to a GitHub repo
2. Go to https://share.streamlit.io → New app
3. Connect your repo, set `app.py` as the entry point
4. In **Secrets**, add:
   ```
   ANTHROPIC_API_KEY = "your-key-here"
   ```
5. Click Deploy — you get a public URL instantly

---

## Deploy to Vercel (alternative)

Streamlit doesn't run natively on Vercel. For Vercel, the app would need to be rebuilt as a Next.js app with API routes. Streamlit Cloud is strongly recommended for this use case.

---

## Sources monitored

| Source | API | Rate limit |
|--------|-----|------------|
| arXiv | Free, no key needed | 3 req/sec |
| Semantic Scholar | Free, no key needed | 100 req/5min |

---

## Project structure

```
mint_research_analyzer/
├── app.py              ← Main Streamlit app
├── requirements.txt    ← Python dependencies
└── README.md           ← This file
```
