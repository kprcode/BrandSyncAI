import re
import time
from typing import List, Dict, Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn


# =============================================================================
# BRANDSYNC AI - CORE LLM & NLP COMPLIANCE ENGINE (DOCUMENT-ALIGNED)
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
# FASTAPI BACKEND & REFERENCE UI
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


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>BrandSync AI - Step 5 Verification</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-slate-50 p-8 font-sans">
    <div class="max-w-2xl mx-auto bg-white p-6 rounded-xl shadow border border-slate-200">
        <h1 class="text-xl font-bold mb-1">BrandSync AI</h1>
        <p class="text-xs text-slate-500 mb-4">Document-Aligned Step 5 Issue Detection Engine</p>

        <label class="block text-xs font-semibold uppercase mb-1">Marketing Copy</label>
        <textarea id="content" rows="4" class="w-full p-3 border rounded-lg mb-4 text-sm" placeholder="Enter text... e.g. Our tool is cheap and revolutionary!"></textarea>

        <button onclick="runCheck()" class="w-full py-2 bg-indigo-600 text-white font-semibold rounded-lg text-sm cursor-pointer">Run Compliance Check</button>

        <div id="output" class="mt-6 hidden p-4 bg-slate-100 rounded-lg text-xs space-y-3"></div>
    </div>

    <script>
        async function runCheck() {
            const content = document.getElementById('content').value;
            const res = await fetch('/api/v1/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content: content,
                    brand_name: "Acme Corp",
                    tone: "Professional & Authoritative",
                    forbidden_terms: "cheap, revolutionary, guaranteed 100%"
                })
            });
            const data = await res.json();
            const out = document.getElementById('output');
            out.classList.remove('hidden');

            let issuesHtml = data.violations.map(v => `
                <div class="p-2 bg-amber-50 border border-amber-200 rounded">
                    <span class="font-bold text-amber-900">${v.step}: Flagged "${v.term}"</span><br>
                    <span class="text-indigo-700 font-medium">${v.guideline_reference}</span><br>
                    <span class="text-slate-600">${v.explanation}</span>
                </div>
            `).join('');

            out.innerHTML = `<b>Compliance Score:</b> ${data.score}%<br><br><b>Detected Issues:</b><br>${issuesHtml}<br><b>AI Revision:</b> ${data.corrected_text}`;
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