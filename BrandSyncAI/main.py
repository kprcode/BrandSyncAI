import re
import time
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import pymupdf
# =============================================================================
# CORE LLM & NLP
# =============================================================================
class BrandSyncComplianceEngine:
    """
    Core LLM Integration, NLP token scanning, brand guideline matcher,
    and Step 5 Issue Detection with Guideline References.
    """

    def __init__(self, brand_name: str, brand_tone: str, forbidden_terms: List[str]):
        self.brand_name = brand_name
        self.brand_tone = brand_tone
        self.forbidden_terms = [term.strip().lower() for term in forbidden_terms if term.strip()]

        # AI Correction Substitution Map
        self.substitution_map = {
            'cheap': 'cost-effective',
            'guaranteed 100%': 'industry-leading',
            'revolutionary': 'advanced',
            'best in universe': 'market-leading'
        }

    def verify_content_compliance(self, raw_content: str) -> Dict[str, Any]:
        start_time = time.time()
        content_lower = raw_content.lower()
        detected_violations = []

        # 1. NLP Rule-Based & Blacklist Term Scanner (Step 5: Issue Detection)
        for term in self.forbidden_terms:
            if term in content_lower:
                detected_violations.append({
                    "step": "Step 5: Issue Detection",
                    "term": term,
                    "type": "Forbidden Terminology / Unsupported Claim",
                    "guideline_reference": f"Doc Ref: Section 4.2 (Prohibited Blacklist & Low-Tier Positioning)",
                    "explanation": f"The phrase '{term}' violates {self.brand_name}'s approved brand guidelines against unverified promotional absolutes."
                })

        # 2. Tone Consistency Heuristics (Step 5: Issue Detection)
        if self.brand_tone == "Professional & Authoritative":
            if any(slang in content_lower for slang in ["super", "awesome", "hey"]):
                detected_violations.append({
                    "step": "Step 5: Issue Detection",
                    "term": "Informal Phrasing",
                    "type": "Tone Consistency Mismatch",
                    "guideline_reference": f"Doc Ref: Section 2.1 (Mandatory Tone & Voice Standards)",
                    "explanation": f"Selected brand tone is '{self.brand_tone}'. Casual phrasing conflicts with mandatory authoritative communication standards."
                })
        elif self.brand_tone == "Technical & Precise":
            if any(hyperbole in content_lower for hyperbole in ["revolutionary", "best in universe"]):
                detected_violations.append({
                    "step": "Step 5: Issue Detection",
                    "term": "Hyperbolic Adjectives",
                    "type": "Factual Precision Violation",
                    "guideline_reference": f"Doc Ref: Section 3.5 (Evidence-Based Telemetry & Accuracy)",
                    "explanation": f"The tone '{self.brand_tone}' requires evidence-based telemetry or product data rather than unverified marketing adjectives."
                })

        if not detected_violations:
            detected_violations.append({
                "step": "Step 5: Issue Detection",
                "term": "None",
                "type": "Guideline Verification",
                "guideline_reference": "Doc Ref: Section 1.0 (General Compliance)",
                "explanation": "Content aligns successfully with active brand tone rules and contains no blacklisted terminology."
            })

        # 3. AI Correction & Text Rewriting Suggestions
        corrected_text = raw_content
        for violation in detected_violations:
            flagged_term = violation.get("term", "")
            if flagged_term in self.substitution_map:
                pattern = re.compile(re.escape(flagged_term), re.IGNORECASE)
                corrected_text = pattern.sub(self.substitution_map[flagged_term], corrected_text)

        if corrected_text == raw_content and detected_violations[0]["term"] != "None":
            corrected_text = f"[Optimized for {self.brand_tone}] {raw_content}"

        # 4. Compliance Scoring
        penalty_count = len([v for v in detected_violations if v["term"] != "None"])
        compliance_score = max(35, 100 - (penalty_count * 25))

        return {
            "score": compliance_score,
            "violations": detected_violations,
            "corrected_text": corrected_text,
            "processing_time": f"{round(time.time() - start_time, 3)}s"
        }


# =============================================================================
# FASTAPI BACKEND 
# =============================================================================
app = FastAPI(title="BrandSync AI", description="LLM & NLP Compliance Backend")


class AnalysisRequest(BaseModel):
    content: str
    brand_name: str
    tone: str
    forbidden_terms: str


@app.post("/api/v1/analyze")
def analyze_endpoint(payload: AnalysisRequest):
    engine = BrandSyncComplianceEngine(
        brand_name=payload.brand_name,
        brand_tone=payload.tone,
        forbidden_terms=payload.forbidden_terms.split(",")
    )
    return engine.verify_content_compliance(payload.content)


@app.post("/api/v1/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    contents = await file.read()

    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF must be smaller than 10 MB.")

    if not contents.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")

    try:
        with pymupdf.open(stream=contents, filetype="pdf") as document:
            extracted_text = "\n".join(page.get_text() for page in document)

    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF. Please try another file.")

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No selectable text was found. Scanned PDFs are not supported yet."
        )

    engine = BrandSyncComplianceEngine(
        brand_name="Acme Corp",
        brand_tone="Professional & Authoritative",
        forbidden_terms=["cheap", "revolutionary", "guaranteed 100%"]
    )

    result = engine.verify_content_compliance(extracted_text)
    result["filename"] = file.filename
    return result

# =============================================================================
# FRONTEND UI - BRANDSYNC AI
# =============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BrandSync AI</title>

<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f5f6fa;
    color: #25263a;
}

header {
    background: white;
    padding: 20px 8%;
    border-bottom: 1px solid #e5e6ed;
}

header h2 {
    margin: 0;
    color: #5146a8;
    font-size: 23px;
}

header p {
    margin: 5px 0 0;
    color: #77798a;
    font-size: 13px;
}

main {
    max-width: 850px;
    margin: 45px auto;
    padding: 0 20px;
}

.intro {
    margin-bottom: 25px;
}

.intro h1 {
    font-size: 27px;
    margin-bottom: 8px;
}

.intro p {
    color: #77798a;
    font-size: 14px;
    line-height: 1.6;
}

.panel {
    background: white;
    border: 1px solid #e4e5ec;
    border-radius: 8px;
    padding: 25px;
    margin-bottom: 20px;
}

.panel h3 {
    margin: 0 0 8px;
    font-size: 17px;
}

.description {
    color: #77798a;
    font-size: 13px;
    margin-bottom: 20px;
}

.upload-area {
    border: 1.5px dashed #aaa5d5;
    background: #faf9ff;
    padding: 27px 15px;
    text-align: center;
    border-radius: 7px;
}

.upload-area p {
    font-size: 13px;
    color: #77798a;
}

.upload-area input {
    display: none;
}

.upload-button {
    display: inline-block;
    background: #eeeafd;
    color: #5146a8;
    padding: 10px 17px;
    border-radius: 5px;
    font-size: 13px;
    font-weight: bold;
    cursor: pointer;
}

#fileName {
    font-size: 12px;
    color: #5146a8;
    margin-top: 12px;
}

.or {
    text-align: center;
    color: #999;
    font-size: 12px;
    margin: 20px 0;
}

textarea {
    width: 100%;
    min-height: 145px;
    resize: vertical;
    border: 1px solid #dcdde5;
    border-radius: 6px;
    padding: 13px;
    font-family: Arial, sans-serif;
    font-size: 13px;
    line-height: 1.6;
    outline: none;
}

textarea:focus {
    border-color: #7569c5;
}

.actions {
    display: flex;
    gap: 10px;
    margin-top: 17px;
}

button {
    border: 0;
    border-radius: 5px;
    padding: 12px 20px;
    font-size: 13px;
    cursor: pointer;
}

.check-button {
    background: #5146a8;
    color: white;
    font-weight: bold;
}

.check-button:hover {
    background: #40368e;
}

.clear-button {
    background: #eeeeF3;
    color: #555;
}

button:disabled {
    opacity: .6;
    cursor: wait;
}

#message {
    display: none;
    margin-top: 15px;
    padding: 12px;
    border-radius: 5px;
    font-size: 13px;
}

#error {
    color: #a33131;
    background: #fff0f0;
}

#success {
    color: #176b4d;
    background: #eaf7f0;
}

#results {
    display: none;
}

.score-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #eee;
    padding-bottom: 17px;
}

.score {
    font-size: 32px;
    font-weight: bold;
    color: #5146a8;
}

.issue {
    padding: 15px;
    border-left: 3px solid #d99a42;
    background: #fffaf1;
    margin-top: 12px;
    border-radius: 4px;
}

.issue strong {
    font-size: 13px;
}

.issue p {
    color: #666;
    font-size: 12px;
    line-height: 1.6;
    margin: 7px 0 0;
}

.corrected {
    margin-top: 20px;
    padding: 16px;
    background: #eef8f2;
    border: 1px solid #d4ebdc;
    border-radius: 6px;
}

.corrected h4 {
    color: #24734e;
    margin: 0 0 9px;
    font-size: 14px;
}

.corrected p {
    font-size: 13px;
    line-height: 1.6;
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

footer {
    text-align: center;
    color: #999;
    font-size: 11px;
    padding: 15px;
}

@media(max-width: 600px) {
    header { padding: 18px 20px; }
    main { margin: 28px auto; }
    .panel { padding: 18px; }
    .intro h1 { font-size: 23px; }
    .actions { flex-direction: column; }
}
</style>
</head>

<body>

<header>
    <h2>BrandSync AI</h2>
    <p>Brand Compliance Checker</p>
</header>

<main>
    <div class="intro">
        <h1>Check Your Content</h1>
        <p>
            Upload a PDF or enter your marketing content to identify
            brand guideline violations and receive correction suggestions.
        </p>
    </div>

    <div class="panel">
        <h3>Submit Your Content</h3>
        <p class="description">
            Choose a PDF document or paste your content below.
        </p>

        <div class="upload-area">
            <p>Upload your marketing document</p>
            <label for="pdfFile" class="upload-button">Choose PDF</label>
            <input type="file" id="pdfFile" accept=".pdf,application/pdf">
            <div id="fileName"></div>
            <p>PDF files only · Maximum size 10 MB</p>
        </div>

        <div class="or">OR ENTER YOUR CONTENT</div>

        <textarea id="content" placeholder="Enter your marketing text here..."></textarea>

        <div class="actions">
            <button class="check-button" id="checkBtn" onclick="runCheck()">
                Check Content
            </button>
            <button class="clear-button" onclick="clearForm()">Clear</button>
        </div>

        <div id="message"></div>
    </div>

    <div class="panel" id="results">
        <h3>Analysis Results</h3>
        <p class="description">Review the compliance check below.</p>

        <div class="score-row">
            <div>
                <div style="font-size:12px;color:#777">Compliance Score</div>
                <div class="score" id="score">--%</div>
            </div>
            <div id="status" style="font-size:13px;font-weight:bold"></div>
        </div>

        <h3 style="margin-top:22px">Detected Issues</h3>
        <div id="issues"></div>

        <div class="corrected">
            <h4>Suggested Correction</h4>
            <p id="correctedText"></p>
        </div>

        <p id="processing" style="font-size:11px;color:#888;margin-top:15px"></p>
    </div>
</main>

<footer>BrandSync AI · Content Compliance Prototype</footer>

<script>
const fileInput = document.getElementById("pdfFile");
const contentInput = document.getElementById("content");

fileInput.addEventListener("change", function() {
    const file = this.files[0];
    document.getElementById("fileName").textContent =
        file ? "Selected: " + file.name : "";
    hideMessage();
});

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, function(char) {
        return {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        }[char];
    });
}

function showMessage(message, type) {
    const box = document.getElementById("message");
    box.textContent = message;
    box.style.display = "block";
    box.style.background = type === "error" ? "#fff0f0" : "#eaf7f0";
    box.style.color = type === "error" ? "#a33131" : "#176b4d";
}

function hideMessage() {
    document.getElementById("message").style.display = "none";
}

async function runCheck() {
    const file = fileInput.files[0];
    const content = contentInput.value.trim();
    const button = document.getElementById("checkBtn");

    hideMessage();
    document.getElementById("results").style.display = "none";

    if (!file && !content) {
        showMessage("Please upload a PDF or enter some content.", "error");
        return;
    }

    if (file && content) {
        showMessage("Please use either a PDF or text, not both at the same time.", "error");
        return;
    }

    if (file && file.size > 10 * 1024 * 1024) {
        showMessage("The PDF must be smaller than 10 MB.", "error");
        return;
    }

    button.disabled = true;
    button.textContent = "Checking...";

    try {
        let response;

        if (file) {
            const formData = new FormData();
            formData.append("file", file);

            response = await fetch("/api/v1/analyze-pdf", {
                method: "POST",
                body: formData
            });
        } else {
            response = await fetch("/api/v1/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    content: content,
                    brand_name: "Acme Corp",
                    tone: "Professional & Authoritative",
                    forbidden_terms: "cheap, revolutionary, guaranteed 100%"
                })
            });
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Could not analyse the content.");
        }

        displayResults(data);
        showMessage("Content analysis completed successfully.", "success");

    } catch (error) {
        showMessage(error.message || "Something went wrong. Please try again.", "error");
    } finally {
        button.disabled = false;
        button.textContent = "Check Content";
    }
}

function displayResults(data) {
    document.getElementById("results").style.display = "block";
    document.getElementById("score").textContent = data.score + "%";

    const status = document.getElementById("status");
    status.textContent = data.score === 100 ? "Compliant" : "Issues Found";
    status.style.color = data.score === 100 ? "#24734e" : "#b57927";

    document.getElementById("issues").innerHTML =
        data.violations.map(function(issue) {
            const clean = issue.term === "None";

            return `
                <div class="issue" style="border-left-color:${clean ? '#26845b' : '#d99a42'}">
                    <strong>${clean ? '✓ ' : '⚑ '}${escapeHTML(issue.term)}</strong>
                    <p><b>Type:</b> ${escapeHTML(issue.type)}</p>
                    <p><b>Guideline:</b> ${escapeHTML(issue.guideline_reference)}</p>
                    <p>${escapeHTML(issue.explanation)}</p>
                </div>
            `;
        }).join("");

    document.getElementById("correctedText").textContent = data.corrected_text;
    document.getElementById("processing").textContent =
        "Processing time: " + (data.processing_time || "Not available");

    document.getElementById("results").scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

function clearForm() {
    contentInput.value = "";
    fileInput.value = "";
    document.getElementById("fileName").textContent = "";
    document.getElementById("results").style.display = "none";
    hideMessage();
}
</script>

</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return HTML_TEMPLATE

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)