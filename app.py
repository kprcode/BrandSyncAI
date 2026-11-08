import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Union

import pymupdf
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# =====================================================================
# 1. LLM INTEGRATION: SETUP & CONFIGURATION
# =====================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brandsync")

BRAND_NAME = "Acme Corp"
MAX_FILE_SIZE = 4 * 1024 * 1024  # 4 MB (Vercel request body limit is ~4.5 MB)
MAX_TEXT_LENGTH = 100_000
MAX_PDF_PAGES = 100
CONTEXT_CHARS = 40  # characters of context shown around each hit

SEVERITY_WEIGHT = {"High": 25, "Medium": 15, "Low": 5}

Replacement = Union[str, Callable[[re.Match], str]]


def _map_replacement(mapping: Dict[str, str], default: str) -> Callable[[re.Match], str]:
    def fn(m: re.Match) -> str:
        return mapping.get(re.sub(r"\s+", " ", m.group(0).lower()), default)

    return fn


def _revolutionize(m: re.Match) -> str:
    word = m.group(0).lower()
    if word.endswith("ing"):
        return "improving"
    if word.endswith("ed"):
        return "improved"
    if word.endswith("es"):
        return "improves"
    return "improve"


# Rule catalog: each rule is a pattern, a replacement, and the reporting metadata.
RULES: List[Dict[str, Any]] = [
    {
        "id": "cheap",
        "label": "cheap",
        "pattern": r"(?<!\w)cheap(?:er|est|ly)?(?!\w)",
        "replacement": _map_replacement(
            {"cheap": "cost-effective", "cheaper": "more cost-effective",
             "cheapest": "most cost-effective", "cheaply": "cost-effectively"},
            "cost-effective",
        ),
        "type": "Low-Tier Positioning",
        "severity": "High",
        "guideline": "Section 4.2 (Prohibited Terms & Low-Tier Positioning)",
        "explanation": "Words implying low quality or low value undermine premium brand positioning.",
    },
    {
        "id": "guaranteed_100",
        "label": "guaranteed 100%",
        "pattern": r"(?<!\w)guarantee[sd]?\s+100\s?%",
        "replacement": "designed to deliver reliable results",
        "type": "Unsupported Claim",
        "severity": "High",
        "guideline": "Section 4.2 (Unverified Promotional Absolutes)",
        "explanation": "Absolute guarantees cannot be substantiated and create legal exposure.",
    },
    {
        "id": "hundred_guaranteed",
        "label": "100% guaranteed",
        "pattern": r"(?<!\w)100\s?%\s+guaranteed(?!\w)",
        "replacement": "reliable",
        "type": "Unsupported Claim",
        "severity": "High",
        "guideline": "Section 4.2 (Unverified Promotional Absolutes)",
        "explanation": "Absolute guarantees cannot be substantiated and create legal exposure.",
    },
    {
        "id": "best_universe",
        "label": "best in universe",
        "pattern": r"(?<!\w)best\s+in\s+(?:the\s+)?universe(?!\w)",
        "replacement": "market-leading",
        "type": "Unsupported Superlative",
        "severity": "High",
        "guideline": "Section 4.2 (Unverified Promotional Absolutes)",
        "explanation": "Unprovable superlatives must be replaced with defensible positioning.",
    },
    {
        "id": "revolutionary",
        "label": "revolutionary",
        "pattern": r"(?<!\w)revolutionary(?!\w)",
        "replacement": "advanced",
        "type": "Exaggerated Claim",
        "severity": "Medium",
        "guideline": "Section 4.2 (Prohibited Terms)",
        "explanation": "Hyperbolic innovation claims need evidence; use measured language.",
    },
    {
        "id": "revolutionize",
        "label": "revolutionize (verb forms)",
        "pattern": r"(?<!\w)revolutioni[sz](?:e|es|ed|ing)(?!\w)",
        "replacement": _revolutionize,
        "type": "Exaggerated Claim",
        "severity": "Medium",
        "guideline": "Section 4.2 (Prohibited Terms)",
        "explanation": "Hyperbolic innovation claims need evidence; use measured language.",
    },
]

for _r in RULES:
    _r["regex"] = re.compile(_r["pattern"], re.IGNORECASE)

# =====================================================================
# 2. LLM INTEGRATION: ANALYSIS & CORRECTION LOGIC
# =====================================================================
VOWEL_START = re.compile(r"[aeiou]", re.IGNORECASE)
ARTICLE_TAIL = re.compile(r"(?<!\w)(a|an)(\s+)$", re.IGNORECASE)


def _match_case(original: str, new: str) -> str:
    letters = [c for c in original if c.isalpha()]
    if len(letters) > 1 and all(c.isupper() for c in letters):
        return new.upper()
    if letters and letters[0].isupper():
        return new[0].upper() + new[1:]
    return new


def _fix_article(output_so_far: str, new_word: str) -> str:
    """Return output_so_far with a trailing a/an corrected for new_word."""
    m = ARTICLE_TAIL.search(output_so_far)
    if not m or not new_word:
        return output_so_far
    article = m.group(1)
    wanted = "an" if VOWEL_START.match(new_word[0]) else "a"
    if article.lower() == wanted:
        return output_so_far
    fixed = wanted.capitalize() if article[0].isupper() else wanted
    return output_so_far[:m.start(1)] + fixed + m.group(2)


def _snippet(text: str, start: int, end: int) -> str:
    a, b = max(0, start - CONTEXT_CHARS), min(len(text), end + CONTEXT_CHARS)
    snippet = re.sub(r"\s+", " ", text[a:b]).strip()
    return ("…" if a > 0 else "") + snippet + ("…" if b < len(text) else "")


class BrandComplianceAnalyzer:
    def find_matches(self, text: str) -> List[Dict[str, Any]]:
        hits = []
        for rule in RULES:
            for m in rule["regex"].finditer(text):
                hits.append({"rule": rule, "start": m.start(), "end": m.end(), "match": m})
        # Resolve overlaps: earliest start wins, then the longest match.
        hits.sort(key=lambda h: (h["start"], -(h["end"] - h["start"])))
        resolved, last_end = [], -1
        for h in hits:
            if h["start"] >= last_end:
                resolved.append(h)
                last_end = h["end"]
        return resolved

    def correct(self, text: str, hits: List[Dict[str, Any]]) -> (str, List[Dict[str, Any]]):
        out, cursor, enriched = "", 0, []
        for h in hits:
            m, rule = h["match"], h["rule"]
            repl = rule["replacement"]
            raw_new = repl(m) if callable(repl) else repl
            new = _match_case(m.group(0), raw_new)
            out += text[cursor:h["start"]]
            out = _fix_article(out, new)
            out += new
            cursor = h["end"]
            enriched.append({
                "rule": rule,
                "found": re.sub(r"\s+", " ", m.group(0)),
                "suggested": new,
                "context": _snippet(text, h["start"], h["end"]),
            })
        out += text[cursor:]
        return out, enriched

    @staticmethod
    def _score(grouped: List[Dict[str, Any]]) -> int:
        penalty = 0
        for g in grouped:
            base = SEVERITY_WEIGHT[g["severity"]]
            penalty += base + min(g["occurrences"] - 1, 3) * 5
        return max(0, 100 - penalty)

    def analyze(self, raw_content: str) -> Dict[str, Any]:
        start_t = time.perf_counter()
        if not raw_content or not raw_content.strip():
            raise ValueError("Content cannot be empty.")
        if len(raw_content) > MAX_TEXT_LENGTH:
            raise ValueError("Content exceeds maximum length.")

        hits = self.find_matches(raw_content)
        corrected_text, enriched = self.correct(raw_content, hits)

        groups: Dict[str, Dict[str, Any]] = {}
        for e in enriched:
            r = e["rule"]
            g = groups.setdefault(r["id"], {
                "term": r["label"],
                "type": r["type"],
                "severity": r["severity"],
                "guideline_reference": r["guideline"],
                "explanation": f"{r['explanation']} ({BRAND_NAME} brand guidelines)",
                "occurrences": 0,
                "examples": [],
            })
            g["occurrences"] += 1
            if len(g["examples"]) < 3:
                g["examples"].append({"found": e["found"], "suggested": e["suggested"], "context": e["context"]})

        violations = list(groups.values())
        score = self._score(violations)
        status = "Compliant" if score >= 90 else ("Needs Review" if score >= 70 else "Issues Found")

        total_issues = sum(v["occurrences"] for v in violations)
        if not violations:
            violations = [{
                "term": "None", "type": "Guideline Verification", "severity": "None",
                "guideline_reference": "General compliance check",
                "explanation": "No violations detected.", "occurrences": 0, "examples": [],
            }]

        return {
            "score": score,
            "status": status,
            "total_issues": total_issues,
            "violations": violations,
            "corrected_text": corrected_text,
            "processing_time": f"{round(time.perf_counter() - start_t, 4)}s",
        }


# =====================================================================
# 3. FASTAPI BACKEND APP
# =====================================================================
app = FastAPI(title="BrandSync AI", version="6.0.0")
analyzer = BrandComplianceAnalyzer()


class TextPayload(BaseModel):
    content: str = Field(..., min_length=1)


@app.post("/api/v1/analyze")
def analyze_text(payload: TextPayload):
    try:
        return analyzer.analyze(payload.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Analysis error")
        raise HTTPException(status_code=500, detail="Internal processing error.")


@app.post("/api/v1/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    try:
        contents = await file.read(MAX_FILE_SIZE + 1)
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (Max 4MB).")

        with pymupdf.open(stream=contents, filetype="pdf") as doc:
            if doc.page_count > MAX_PDF_PAGES:
                raise HTTPException(status_code=400, detail=f"PDF exceeds {MAX_PDF_PAGES} pages.")
            text = "\n\n".join(page.get_text("text") for page in doc)

        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text found. This may be a scanned/image-only PDF.",
            )
        return analyzer.analyze(text)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("PDF parsing error")
        raise HTTPException(status_code=400, detail="Could not read PDF contents.")


# =====================================================================
# 4. FRONTEND INTERFACE
# =====================================================================
HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BrandSync AI</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, sans-serif; background: #f8f9fe; color: #25263a; }
header { padding: 25px 8% 5px 8%; }
header h2 { margin: 0; color: #5146a8; font-size: 20px; }
header p { margin: 2px 0 0; color: #77798a; font-size: 12px; }
main { max-width: 750px; margin: 15px auto 40px auto; padding: 0 20px; }
.intro h1 { font-size: 24px; margin-bottom: 6px; color: #1a1a2e; }
.intro p { color: #66687a; font-size: 13px; line-height: 1.5; margin-bottom: 20px; }
.panel { background: white; border: 1px solid #e4e5ec; border-radius: 8px; padding: 24px; margin-bottom: 20px; }
.panel h3 { margin: 0 0 5px; font-size: 15px; color: #1a1a2e; }
.description { color: #77798a; font-size: 12px; margin-bottom: 18px; }
.upload-area { border: 1.5px dashed #bbafe8; background: #faf9ff; padding: 24px 15px; text-align: center; border-radius: 6px; }
.upload-area input { display: none; }
.upload-button { display: inline-block; background: #ece8f9; color: #5146a8; padding: 8px 15px; border-radius: 5px; font-size: 12px; font-weight: bold; cursor: pointer; }
#fileName { font-size: 11.5px; color: #5146a8; margin-top: 8px; }
.or { text-align: center; color: #aaa; font-size: 10.5px; font-weight: bold; margin: 16px 0; }
textarea { width: 100%; min-height: 130px; resize: vertical; border: 1px solid #dcdde5; border-radius: 6px; padding: 12px; font-family: Arial, sans-serif; font-size: 13px; outline: none; }
textarea:focus { border-color: #5146a8; }
.actions { display: flex; gap: 10px; margin-top: 15px; }
button { border: 0; border-radius: 5px; padding: 10px 18px; font-size: 12.5px; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.check-button { background: #5146a8; color: white; font-weight: bold; }
.check-button:hover { background: #40368e; }
.clear-button { background: #f0f0f5; color: #555; }
#message { display: none; margin-top: 15px; padding: 12px; border-radius: 5px; font-size: 13px; }
#results { display: none; }
.score-row { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #eee; padding-bottom: 15px; }
.score { font-size: 30px; font-weight: bold; color: #5146a8; }
.issue { padding: 14px; border-left: 3px solid #d99a42; background: #fffaf1; margin-top: 12px; border-radius: 4px; }
.issue strong { font-size: 12.5px; color: #222; }
.issue p { color: #555; font-size: 11.5px; line-height: 1.5; margin: 5px 0 0; }
.example { margin-top: 6px; padding: 6px 8px; background: #fff; border: 1px solid #f0e4cc; border-radius: 4px; font-size: 11px; color: #555; }
.example .from { color: #a33131; text-decoration: line-through; }
.example .to { color: #24734e; font-weight: bold; }
.corrected { margin-top: 18px; padding: 15px; background: #eef8f2; border: 1px solid #d4ebdc; border-radius: 6px; }
.corrected h4 { color: #24734e; margin: 0 0 6px; font-size: 13px; }
.corrected p { font-size: 12.5px; line-height: 1.5; margin: 0; color: #1a4d36; white-space: pre-wrap; }
footer { text-align: center; color: #aaa; font-size: 11px; padding: 15px; }
</style>
</head>
<body>
<header>
    <h2>BrandSync AI</h2>
    <p>Brand Compliance Checker v6.0</p>
</header>
<main>
    <div class="intro">
        <h1>Check Your Content</h1>
        <p>Upload a PDF or enter your marketing content to identify brand guideline violations and receive correction suggestions.</p>
    </div>
    <div class="panel">
        <h3>Submit Your Content</h3>
        <p class="description">Choose a PDF document or paste your content below.</p>
        <div class="upload-area">
            <p style="color:#77798a; font-size:12.5px; margin:0 0 10px 0;">Upload your marketing document</p>
            <label for="pdfFile" class="upload-button">Choose PDF</label>
            <input type="file" id="pdfFile" accept=".pdf">
            <div id="fileName"></div>
            <p style="margin-top: 8px; font-size: 11px; color:#888;">PDF files only · Maximum size 4 MB</p>
        </div>
        <div class="or">OR ENTER YOUR CONTENT</div>
        <textarea id="content" maxlength="100000" placeholder="Paste your marketing content here..."></textarea>
        <div class="actions">
            <button class="check-button" id="checkBtn" onclick="runCheck()">Check Content</button>
            <button class="clear-button" onclick="clearForm()">Clear</button>
        </div>
        <div id="message"></div>
    </div>
    <div class="panel" id="results">
        <h3>Analysis Results</h3>
        <p class="description">Review the compliance check below.</p>
        <div class="score-row">
            <div>
                <div style="font-size:11px; color:#777;">Compliance Score</div>
                <div class="score" id="score">--%</div>
            </div>
            <div id="status" style="font-size:13px; font-weight:bold;"></div>
        </div>
        <h3 style="margin-top:18px;">Detected Issues</h3>
        <div id="issues"></div>
        <div class="corrected">
            <h4>Suggested Correction</h4>
            <p id="correctedText"></p>
        </div>
        <p id="processing" style="font-size:11px; color:#888; margin-top:15px;"></p>
    </div>
</main>
<footer>BrandSync AI · Brand Compliance Prototype</footer>
<script>
const fileInput = document.getElementById("pdfFile");
const contentInput = document.getElementById("content");
const fileName = document.getElementById("fileName");

fileInput.addEventListener("change", function() {
    if (this.files[0]) {
        contentInput.value = "";
        fileName.textContent = "Selected: " + this.files[0].name;
    } else {
        fileName.textContent = "";
    }
    document.getElementById("message").style.display = "none";
});
contentInput.addEventListener("input", function() {
    if (this.value && fileInput.files[0]) { fileInput.value = ""; fileName.textContent = ""; }
});

function showMsg(text, isError) {
    const box = document.getElementById("message");
    box.textContent = text;
    box.style.display = "block";
    box.style.background = isError ? "#fff0f0" : "#eaf7f0";
    box.style.color = isError ? "#a33131" : "#176b4d";
}
function esc(s) {
    const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
    return String(s ?? "").replace(/[&<>"']/g, c => map[c]);
}

async function runCheck() {
    const file = fileInput.files[0];
    const content = contentInput.value.trim();
    const btn = document.getElementById("checkBtn");
    document.getElementById("results").style.display = "none";
    document.getElementById("message").style.display = "none";
    if (!file && !content) { showMsg("Please upload a PDF or enter content.", true); return; }

    btn.disabled = true;
    btn.textContent = "Checking...";
    try {
        let res;
        if (file) {
            const fd = new FormData();
            fd.append("file", file);
            res = await fetch("/api/v1/analyze-pdf", { method: "POST", body: fd });
        } else {
            res = await fetch("/api/v1/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: content })
            });
        }
        let data;
        try { data = await res.json(); } catch (e) { throw new Error("Server error (" + res.status + ")."); }
        if (!res.ok) throw new Error(data.detail || "Analysis failed.");

        document.getElementById("results").style.display = "block";
        document.getElementById("score").textContent = data.score + "%";
        const st = document.getElementById("status");
        st.textContent = data.status;
        st.style.color = data.score >= 90 ? "#24734e" : "#b57927";

        document.getElementById("issues").innerHTML = data.violations.map(i => {
            const none = i.term === 'None';
            const count = i.occurrences > 1 ? ` (${i.occurrences}×)` : "";
            const examples = (i.examples || []).map(e => `
                <div class="example">
                    <span class="from">${esc(e.found)}</span> → <span class="to">${esc(e.suggested)}</span><br>
                    ${esc(e.context)}
                </div>`).join("");
            return `
            <div class="issue" style="border-left-color:${none ? '#26845b' : '#d99a42'}">
                <strong>${none ? '✓ ' : '⚑ '} ${esc(i.term)}${count}</strong>
                <p><b>Type:</b> ${esc(i.type)} · <b>Severity:</b> ${esc(i.severity)}</p>
                <p><b>Guideline:</b> ${esc(i.guideline_reference)}</p>
                <p>${esc(i.explanation)}</p>
                ${examples}
            </div>`;
        }).join("");

        document.getElementById("correctedText").textContent = data.corrected_text;
        document.getElementById("processing").textContent = "Processing time: " + data.processing_time;
        document.getElementById("results").scrollIntoView({ behavior: "smooth" });
        showMsg("Content analysis completed successfully.", false);
    } catch (err) {
        showMsg(err.message || "An error occurred.", true);
    } finally {
        btn.disabled = false;
        btn.textContent = "Check Content";
    }
}

function clearForm() {
    contentInput.value = "";
    fileInput.value = "";
    fileName.textContent = "";
    document.getElementById("results").style.display = "none";
    document.getElementById("message").style.display = "none";
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content=HTML_UI)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(f"{Path(__file__).stem}:app", host="127.0.0.1", port=8000, reload=True)