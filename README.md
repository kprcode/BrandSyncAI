# BrandSync AI

**An intelligent brand compliance checking platform that helps businesses maintain consistent brand communication.**

BrandSync AI analyzes marketing content against predefined brand guidelines, identifies unwanted terminology and tone inconsistencies, explains detected violations, and suggests corrected content.

Users can paste text or upload PDF documents, review compliance scores, compare original and revised content, and track previous submissions through an interactive dashboard.



## Features

### 1. Content Analysis
- Paste marketing content directly into the application.
- Upload PDF documents for automatic text extraction and analysis.
- Supports content up to 100,000 characters.
- PDF upload limit of 4 MB and 100 pages.

### 2. Custom Brand Guidelines
- Add forbidden terms and their approved replacements.
- Upload brand guidelines using CSV or TXT files.
- Automatically identifies matching forbidden terminology.
- Suggests approved alternatives while preserving capitalization.

### 3. Tone and Language Analysis
Detects writing patterns that may affect brand consistency, including:
- Excessive exclamation marks.
- Unnecessary ALL CAPS words.
- Promotional or exaggerated language.
- Overly long sentences.

### 4. Automated Content Correction
- Identifies problematic words and expressions.
- Provides suggested replacements.
- Maintains the original text structure.
- Displays original and revised content side by side.
- Allows users to download corrected content as a TXT file.

### 5. Compliance Score
- Generates a compliance score between 0 and 100.
- Categorizes results into three statuses:
  - Compliant
  - Needs Review
  - Issues Found
- Calculates scores based on violation severity and occurrence frequency.

### 6. Interactive Dashboard
- Displays total content checks.
- Shows the total number of detected issues.
- Calculates the average compliance score.
- Identifies the most frequently detected violations.
- Displays previous submission history.

### 7. Submission History and Export
- Stores analysis results in a local SQLite database.
- Maintains submission dates, compliance scores, and detected issues.
- Allows users to review previous submissions.
- Exports submission history as a CSV file.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| FastAPI | Backend framework and API development |
| PyMuPDF | PDF text extraction |
| Pydantic | Request validation and data handling |
| SQLite | Submission history storage |
| HTML | Frontend structure |
| CSS | User interface styling |
| JavaScript | Frontend functionality and API integration |
| Uvicorn | Application server |


## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/<your-repository>.git
```

### 2. Navigate to the Project Directory

```bash
cd <your-repository>
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python app.py
```

### 5. Open in Browser

Visit:

```text
http://127.0.0.1:8000
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Loads the application interface |
| POST | `/api/v1/analyze` | Analyzes text content |
| POST | `/api/v1/analyze-pdf` | Extracts and analyzes PDF content |
| POST | `/api/v1/guidelines/validate` | Validates brand guideline entries |
| GET | `/api/v1/history` | Retrieves previous submissions |
| GET | `/api/v1/dashboard` | Retrieves dashboard statistics |
| GET | `/api/v1/history.csv` | Exports submission history |

## Current Limitations

- The current analysis engine uses predefined rules and pattern matching rather than an integrated LLM.
- Tone analysis is based on predefined language patterns.
- Scanned image-only PDFs are not supported.
- Submission history is stored in a local SQLite database.
- Authentication and multi-user access are not currently implemented.
- Advanced semantic understanding and factual verification are planned for future versions.


## Team

**Team CodeFalcon**

| Name | Role |
|---|---|
| R Kirubashree | Frontend Developer |
| Keerthana N | Backend Developer |
| Karthik P.R | AI/ML Developer |

---

**BrandSync AI – Making every piece of content consistent with your brand.**
