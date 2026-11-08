# BrandSync AI

**Check your marketing content against brand guidelines in seconds.** Paste text or upload a PDF, and BrandSync AI flags violations, explains each issue, and suggests a corrected version.

> Working prototype with a rule-based engine. LLM-powered tone and factual checks are planned.

## Features

- **PDF and text input:** upload a PDF or paste content directly
- **Smart term detection:** catches forbidden words and their variants (`cheap`, `cheaper`, `cheapest`)
- **Unsupported claim detection:** flags absolutes like `guaranteed 100%` and `best in the universe`
- **Automatic corrections:** suggests a fixed version that keeps capitalisation and grammar (`a revolutionary` becomes `an advanced`)
- **Clear explanations:** every issue shows the exact text, severity, reason and suggested replacement
- **Compliance score:** a 0 to 100 score based on severity and repetition
- **Privacy friendly:** PDFs are processed in memory and never stored

## Tech Stack

Python, FastAPI, PyMuPDF, HTML/JavaScript, Vercel

## Quick Start

```bash
git clone https://github.com/<your-username>/brandsync-ai.git
cd brandsync-ai
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8000

## Limits

PDF up to 4 MB and 100 pages. Scanned (image-only) PDFs are not supported yet.

## Roadmap

- Brand guideline upload
- Original vs revised comparison
- Tone and factual checks using an LLM
- Dashboard and authentication

## Team

**Team CodeFalcon**

| Name | Role |
|---|---|
| R Kirubashree | Frontend Developer |
| Keerthana N | Backend Developer |
| Karthik P.R | AI/ML Developer |
