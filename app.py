import csv
import io
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pymupdf
except ImportError:  # PDF uploads remain available after installing PyMuPDF.
    pymupdf = None
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

BRAND_NAME = "Acme Corp"
MAX_FILE_SIZE = 4 * 1024 * 1024
MAX_TEXT_LENGTH = 100_000
MAX_PDF_PAGES = 100
DB_PATH = Path(__file__).with_name("brandsync_history.sqlite3")

DEFAULT_GUIDELINES = [
    {"forbidden": "cheap", "approved": "cost-effective"},
    {"forbidden": "revolutionary", "approved": "advanced"},
    {"forbidden": "guaranteed 100%", "approved": "designed to deliver reliable results"},
    {"forbidden": "100% guaranteed", "approved": "reliable"},
    {"forbidden": "best in universe", "approved": "market-leading"},
]

app = FastAPI(title="BrandSync AI", version="7.0.0")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            score INTEGER NOT NULL,
            status TEXT NOT NULL,
            total_issues INTEGER NOT NULL,
            content TEXT NOT NULL,
            corrected_text TEXT NOT NULL,
            violations_json TEXT NOT NULL
        )""")
        conn.commit()


init_db()


class TextPayload(BaseModel):
    content: str = Field(..., min_length=1)
    guidelines: Optional[List[Dict[str, str]]] = None


class GuidelinePayload(BaseModel):
    guidelines: List[Dict[str, str]]


def normalize_guidelines(items: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    source = items if items is not None else DEFAULT_GUIDELINES
    result = []
    for item in source:
        forbidden = str(item.get("forbidden", "")).strip()
        approved = str(item.get("approved", "")).strip()
        if forbidden and approved:
            result.append({"forbidden": forbidden, "approved": approved})
    if not result:
        raise ValueError("Add at least one forbidden and approved term pair.")
    return result


def match_case(original: str, replacement: str) -> str:
    letters = [c for c in original if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return replacement.upper()
    if letters and letters[0].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def tone_issues(text: str) -> List[Dict[str, Any]]:
    issues = []
    for m in re.finditer(r"!{2,}", text):
        issues.append({"id": "exclamation", "term": "Excessive exclamation marks", "type": "Tone", "severity": "Low", "found": m.group(), "suggested": "!", "context": m.group()})
    for m in re.finditer(r"\b[A-Z]{4,}\b", text):
        if m.group() not in {"HTTP", "PDF", "HTML", "NASA"}:
            issues.append({"id": "all_caps", "term": "ALL CAPS", "type": "Tone", "severity": "Low", "found": m.group(), "suggested": m.group().capitalize(), "context": m.group()})
    for word in ("revolutionary", "unbelievable", "amazing", "perfect", "guaranteed", "best-ever", "ultimate"):
        for m in re.finditer(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.I):
            issues.append({"id": "hype", "term": word, "type": "Tone", "severity": "Medium", "found": m.group(), "suggested": "measurable", "context": m.group()})
    for m in re.finditer(r"[^.!?\n]{181,}[.!?]", text):
        issues.append({"id": "long_sentence", "term": "Overly long sentence", "type": "Tone", "severity": "Low", "found": m.group().strip()[:80] + "…", "suggested": "Split into shorter sentences", "context": m.group().strip()[:120] + "…"})
    return issues


class Analyzer:
    def analyze(self, text: str, guidelines: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        started = time.perf_counter()
        if not text or not text.strip():
            raise ValueError("Content cannot be empty.")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError("Content exceeds maximum length.")
        rules = normalize_guidelines(guidelines)
        hits = []
        for index, rule in enumerate(rules):
            pattern = re.compile(r"(?<!\w)" + re.escape(rule["forbidden"]) + r"(?!\w)", re.I)
            for m in pattern.finditer(text):
                hits.append((m.start(), m.end(), index, m, rule))
        hits.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        selected, last_end = [], -1
        for hit in hits:
            if hit[0] >= last_end:
                selected.append(hit)
                last_end = hit[1]

        corrected, cursor, found = [], 0, []
        for start, end, index, m, rule in selected:
            corrected.append(text[cursor:start])
            new = match_case(m.group(), rule["approved"])
            corrected.append(new)
            found.append({"id": f"guideline_{index}", "term": rule["forbidden"], "type": "Brand guideline", "severity": "High", "found": m.group(), "suggested": new, "context": text[max(0, start - 40):min(len(text), end + 40)].replace("\n", " ")})
            cursor = end
        corrected.append(text[cursor:])
        tone = tone_issues(text)
        all_issues = found + tone
        grouped = []
        by_id = {}
        for issue in all_issues:
            group = by_id.setdefault(issue["id"], {"term": issue["term"], "type": issue["type"], "severity": issue["severity"], "guideline_reference": (f'Your uploaded guideline line: "{issue["term"]}" → "{issue["suggested"]}"' if issue["type"] == "Brand guideline" else "Tone policy"), "explanation": "Replace the forbidden term with the approved wording." if issue["type"] == "Brand guideline" else "This style pattern can reduce clarity or weaken a consistent brand voice.", "occurrences": 0, "examples": []})
            group["occurrences"] += 1
            if len(group["examples"]) < 3:
                group["examples"].append({"found": issue["found"], "suggested": issue["suggested"], "context": issue["context"]})
        grouped = list(by_id.values())
        penalty = sum((25 if x["severity"] == "High" else 15 if x["severity"] == "Medium" else 5) + min(x["occurrences"] - 1, 3) * 5 for x in grouped)
        score = max(0, 100 - penalty)
        return {"score": score, "status": "Compliant" if score >= 90 else ("Needs Review" if score >= 70 else "Issues Found"), "total_issues": len(all_issues), "violations": grouped or [{"term": "None", "type": "Guideline Verification", "severity": "None", "guideline_reference": "All uploaded guideline lines and tone policies", "explanation": "No violations detected.", "occurrences": 0, "examples": []}], "corrected_text": "".join(corrected), "original_text": text, "processing_time": f"{time.perf_counter() - started:.4f}s"}


analyzer = Analyzer()


def save_result(result: Dict[str, Any]):
    import json
    with db() as conn:
        conn.execute("INSERT INTO checks(created_at,score,status,total_issues,content,corrected_text,violations_json) VALUES(?,?,?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(), result["score"], result["status"], result["total_issues"], result["original_text"], result["corrected_text"], json.dumps(result["violations"])))
        conn.commit()


def analyze_and_save(text: str, guidelines=None):
    result = analyzer.analyze(text, guidelines)
    save_result(result)
    return result


@app.post("/api/v1/analyze")
def analyze_text(payload: TextPayload):
    try:
        return analyze_and_save(payload.content, payload.guidelines)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/v1/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    if pymupdf is None:
        raise HTTPException(503, "PDF support is unavailable. Install the PyMuPDF package to enable PDF uploads.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (maximum 4 MB).")
    try:
        with pymupdf.open(stream=contents, filetype="pdf") as doc:
            if doc.page_count > MAX_PDF_PAGES:
                raise HTTPException(400, f"PDF exceeds {MAX_PDF_PAGES} pages.")
            text = "\n\n".join(page.get_text("text") for page in doc)
        if not text.strip():
            raise HTTPException(400, "No readable text found in the PDF.")
        return analyze_and_save(text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Could not read PDF contents: {exc}")


@app.post("/api/v1/guidelines/validate")
def validate_guidelines(payload: GuidelinePayload):
    try:
        return {"guidelines": normalize_guidelines(payload.guidelines)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/history")
def history(limit: int = 50):
    with db() as conn:
        rows = conn.execute("SELECT id,created_at,score,status,total_issues FROM checks ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 200),)).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/v1/dashboard")
def dashboard():
    with db() as conn:
        summary = conn.execute("SELECT COUNT(*) checks, COALESCE(SUM(total_issues),0) issues, COALESCE(ROUND(AVG(score),1),0) average_score FROM checks").fetchone()
        rows = conn.execute("SELECT violations_json FROM checks").fetchall()
    import json
    counts = {}
    for row in rows:
        for violation in json.loads(row[0]):
            if violation.get("term") != "None":
                counts[violation["term"]] = counts.get(violation["term"], 0) + violation.get("occurrences", 0)
    common = sorted(({"term": k, "count": v} for k, v in counts.items()), key=lambda x: -x["count"])[:10]
    return {**dict(summary), "most_common_violations": common}


@app.get("/api/v1/history.csv")
def history_csv():
    with db() as conn:
        rows = conn.execute("SELECT id,created_at,score,status,total_issues,content,corrected_text FROM checks ORDER BY id DESC").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "score", "status", "total_issues", "original_text", "corrected_text"])
    writer.writerows([tuple(row) for row in rows])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=brandsync-history.csv"})


HTML_UI = r'''<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BrandSync AI</title><style>
*{box-sizing:border-box}body{margin:0;font:14px Arial,sans-serif;background:#f7f8fc;color:#25263a}header{padding:22px 7%;background:#fff;border-bottom:1px solid #e6e7ef;display:flex;justify-content:space-between;align-items:center}header h2{margin:0;color:#5146a8}header p{margin:4px 0 0;color:#777;font-size:12px}.nav button{background:#eeeafa;color:#5146a8;margin-left:6px}main{max-width:1100px;margin:24px auto;padding:0 18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{background:#fff;border:1px solid #e2e4ed;border-radius:10px;padding:20px;margin-bottom:18px;box-shadow:0 2px 8px #26315d0a}h1{font-size:25px;margin:0 0 7px}h3{margin:0 0 8px;color:#1d1e31}.muted{color:#777;font-size:12px;line-height:1.5}textarea{width:100%;min-height:150px;padding:11px;border:1px solid #d7d9e3;border-radius:7px;resize:vertical;font:13px Arial}.guideline-row{display:grid;grid-template-columns:1fr 1fr 32px;gap:7px;margin:8px 0}.guideline-row input{padding:8px;border:1px solid #d7d9e3;border-radius:5px}.upload{border:1.5px dashed #b9afe4;border-radius:7px;padding:15px;text-align:center;background:#fbfaff;margin:12px 0}.actions{display:flex;gap:8px;margin-top:12px}button{border:0;border-radius:6px;padding:9px 14px;cursor:pointer;font-size:12px}.primary{background:#5146a8;color:white;font-weight:bold}.secondary{background:#eeeef5;color:#555}.danger{background:#fff0f0;color:#a33131;padding:6px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.card{background:#fafaff;padding:12px;border-radius:7px;border:1px solid #e9e8f5}.card b{font-size:22px;color:#5146a8;display:block}.score{font-size:30px;color:#5146a8;font-weight:bold}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:12px}.compare-box{white-space:pre-wrap;background:#fafafa;border:1px solid #eee;padding:12px;border-radius:6px;line-height:1.5;max-height:320px;overflow:auto}.issue{padding:11px;border-left:3px solid #d99a42;background:#fffaf1;margin:9px 0;border-radius:5px;font-size:12px}.issue p{margin:5px 0;color:#555}.example{margin-top:6px}.from{text-decoration:line-through;color:#a33131}.to{color:#24734e;font-weight:bold}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:8px;border-bottom:1px solid #eee}.hidden{display:none}@media(max-width:760px){.grid,.comparison{grid-template-columns:1fr}.cards{grid-template-columns:1fr 1fr}}
</style></head><body><header><div><h2>BrandSync AI</h2><p>Custom brand compliance checker</p></div><div class="nav"><button onclick="showTab('checker')">Checker</button><button onclick="showTab('dashboard')">Dashboard</button></div></header><main>
<section id="checker"><h1>Check content against your brand</h1><p class="muted">Upload your own terminology list, then review every suggested change before downloading the corrected copy.</p><div class="grid"><div class="panel"><h3>1. Your brand guideline</h3><p class="muted">One forbidden term and one approved replacement per line.</p><div id="rules"></div><button class="secondary" onclick="addRule()">+ Add guideline line</button><div class="upload"><label>Or upload a CSV or TXT file<br><input id="rulesFile" type="file" accept=".csv,.txt"></label><p class="muted">CSV columns: forbidden, approved. TXT format: forbidden → approved</p></div></div><div class="panel"><h3>2. Content to check</h3><textarea id="content" maxlength="100000" placeholder="Paste marketing copy here..."></textarea><div class="upload"><label>Or choose a PDF<br><input id="pdf" type="file" accept=".pdf"></label><div id="fileName" class="muted"></div></div><div class="actions"><button class="primary" id="check" onclick="runCheck()">Check content</button><button class="secondary" onclick="clearAll()">Clear</button></div><div id="message" class="muted"></div></div></div><div id="results" class="panel hidden"><div style="display:flex;justify-content:space-between;align-items:center"><div><h3>Results</h3><span id="status" class="muted"></span></div><div class="score" id="score"></div></div><div id="issues"></div><h3>Original vs revised</h3><div class="comparison"><div><p class="muted">Original</p><div class="compare-box" id="original"></div></div><div><p class="muted">Revised</p><div class="compare-box" id="revised"></div></div></div><div class="actions"><button class="primary" onclick="downloadText()">Download corrected text</button></div></div></section>
<section id="dashboard" class="hidden"><h1>Submission dashboard</h1><p class="muted">Saved checks help you monitor recurring violations and content quality over time.</p><div class="panel"><div class="cards"><div class="card"><span class="muted">Total checks</span><b id="checks">0</b></div><div class="card"><span class="muted">Issues found</span><b id="issueCount">0</b></div><div class="card"><span class="muted">Average score</span><b id="average">0</b></div></div><h3 style="margin-top:22px">Most common violations</h3><div id="common" class="muted"></div><div class="actions"><button class="secondary" onclick="location.href='/api/v1/history.csv'">Export CSV</button></div></div><div class="panel"><h3>Submission history</h3><table><thead><tr><th>Date</th><th>Score</th><th>Status</th><th>Issues</th></tr></thead><tbody id="history"></tbody></table></div></section></main><script>
let lastResult=null;const rules=document.getElementById('rules');function addRule(a='',b=''){const row=document.createElement('div');row.className='guideline-row';row.innerHTML=`<input placeholder="Forbidden term" value="${esc(a)}"><input placeholder="Approved term" value="${esc(b)}"><button class="danger" onclick="this.parentElement.remove()">×</button>`;rules.appendChild(row)}function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}addRule('cheap','cost-effective');addRule('revolutionary','advanced');
document.getElementById('rulesFile').onchange=async e=>{const f=e.target.files[0];if(!f)return;const t=await f.text();rules.innerHTML='';t.split(/\r?\n/).forEach(line=>{let p=line.split(/,|\s*→\s*/);if(p.length>=2)addRule(p[0].trim(),p.slice(1).join(',').trim())})};document.getElementById('pdf').onchange=e=>document.getElementById('fileName').textContent=e.target.files[0]?.name||'';
function getRules(){return [...rules.children].map(r=>({forbidden:r.children[0].value.trim(),approved:r.children[1].value.trim()})).filter(x=>x.forbidden&&x.approved)}function showTab(t){document.getElementById('checker').classList.toggle('hidden',t!=='checker');document.getElementById('dashboard').classList.toggle('hidden',t!=='dashboard');if(t==='dashboard')loadDashboard()}function msg(s,bad=false){const m=document.getElementById('message');m.textContent=s;m.style.color=bad?'#a33131':'#24734e'}
async function runCheck(){const file=document.getElementById('pdf').files[0],text=document.getElementById('content').value.trim(),btn=document.getElementById('check');if(!file&&!text)return msg('Enter content or choose a PDF.',true);btn.disabled=true;btn.textContent='Checking…';try{let res;if(file){let fd=new FormData();fd.append('file',file);res=await fetch('/api/v1/analyze-pdf',{method:'POST',body:fd})}else res=await fetch('/api/v1/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:text,guidelines:getRules()})});let d=await res.json();if(!res.ok)throw Error(d.detail);lastResult=d;document.getElementById('results').classList.remove('hidden');document.getElementById('score').textContent=d.score+'%';document.getElementById('status').textContent=d.status+' · '+d.total_issues+' issue(s)';document.getElementById('original').textContent=d.original_text;document.getElementById('revised').textContent=d.corrected_text;document.getElementById('issues').innerHTML=d.violations.map(i=>`<div class="issue"><b>${i.term==='None'?'✓':'⚑'} ${esc(i.term)}${i.occurrences>1?' ('+i.occurrences+'×)':''}</b><p><b>${esc(i.type)}</b> · ${esc(i.severity)} · ${esc(i.guideline_reference)}</p><p>${esc(i.explanation)}</p>${(i.examples||[]).map(e=>`<div class="example"><span class="from">${esc(e.found)}</span> → <span class="to">${esc(e.suggested)}</span> — ${esc(e.context)}</div>`).join('')}</div>`).join('');msg('Analysis completed successfully.')}catch(e){msg(e.message||'Analysis failed.',true)}finally{btn.disabled=false;btn.textContent='Check content'}}function downloadText(){if(!lastResult)return;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lastResult.corrected_text],{type:'text/plain'}));a.download='corrected-content.txt';a.click()}function clearAll(){document.getElementById('content').value='';document.getElementById('pdf').value='';document.getElementById('results').classList.add('hidden');msg('');}async function loadDashboard(){const [d,h]=await Promise.all([fetch('/api/v1/dashboard').then(r=>r.json()),fetch('/api/v1/history').then(r=>r.json())]);document.getElementById('checks').textContent=d.checks;document.getElementById('issueCount').textContent=d.issues;document.getElementById('average').textContent=d.average_score+'%';document.getElementById('common').innerHTML=d.most_common_violations.length?d.most_common_violations.map(x=>`${esc(x.term)} (${x.count})`).join(' · '):'No checks yet.';document.getElementById('history').innerHTML=h.items.map(x=>`<tr><td>${new Date(x.created_at).toLocaleString()}</td><td>${x.score}%</td><td>${esc(x.status)}</td><td>${x.total_issues}</td></tr>`).join('')} </script></body></html>'''


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(HTML_UI)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(f"{Path(__file__).stem}:app", host="127.0.0.1", port=8000, reload=True)
