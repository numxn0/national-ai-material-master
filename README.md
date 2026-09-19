# National AI Material Master (SIH Prototype)

> **AI-Powered Material Master Standardization, Deduplication, and Multi-Tier Governance Platform for Indian Central Public Sector Enterprises (CPSEs) & Ministries.**
>
> Built for the **Smart India Hackathon (SIH)**.

---

## 1. Executive Summary & Problem Statement

Across 300+ Indian Central Public Sector Enterprises (CPSEs) like **ONGC, IOCL, BHEL, NTPC, Coal India, and Indian Railways**, industrial spare parts, pipes, valves, cables, and bearings are procured under disparate item codes, conflicting descriptions, non-standard units of measurement (UOM), and regional naming conventions.

For example, an identical physical carbon steel seamless pipe is cataloged as:
- **IOCL:** `PIPE CS SEAMLESS 4 INCH SCH 40 A106-B` (UOM: `MTR`)
- **ONGC:** `CARBON STEEL SEAMLESS PIPE 4" SCH 40 ASTM A106 GRADE B` (UOM: `M`)
- **BHEL:** `4" NB CS PIPE SMLS SCH40 A106GR.B BE` (UOM: `MTRS`)

### Critical Industry Impacts:
1. **Capital Lockup**: Billions of rupees trapped in redundant emergency inventory buffers across adjacent PSU depots.
2. **Fragmented Purchasing Power**: Inability to aggregate demand across CPSEs for bulk rate contracts.
3. **Supply Chain Fragility**: Long lead times during plant shutdowns when identical spare parts sit idle in a neighboring enterprise's warehouse.

The **National AI Material Master** resolves this with an explainable, GovTech-grade catalog harmonization engine combining **rule-based normalization, regex attribute extraction, RapidFuzz candidate blocking, semantic vector similarity, transparent hybrid scoring, SHAP-style explainability, dual-level (L1/L2) governance, and a SHA-256 cryptographic audit trail**.

---

## 2. End-to-End 9-Stage Pipeline Architecture

```text
[1. Multi-PSU Raw Ingestion (CSV / ERP)]
                  │
                  ▼
[2. Data Cleaning & Normalization Engine] ─── (UOM standardization, synonym mapping, text hygiene)
                  │
                  ▼
[3. Rule-Based Attribute Extraction] ──────── (Diameter, Schedule, Material Grade, Pressure, Ends)
                  │
                  ▼
[4. Candidate Generation (RapidFuzz)] ─────── (Taxonomy blocking, token-sort & set ratio pruning)
                  │
                  ▼
[5. Semantic Vector Similarity (pgvector)] ── (High-dimensional embedding cosine similarity stub)
                  │
                  ▼
[6. Transparent Hybrid Match Scoring] ─────── (Weighted fusion: Lexical + Semantic + Specs + Penalties)
                  │
                  ▼
[7. SHAP-Style Explainability Layer] ──────── (Waterfall contribution factors + plain-English rationale)
                  │
                  ▼
[8. Dual-Tier Governance Workflow] ────────── (L1 Technical Reviewer ──► L2 Ministry Authority)
                  │                             └─ Generates Proposed National Code (IND-CAT-YYYYMM-XXXX)
                  ▼
[9. SHA-256 Tamper-Evident Audit Trail] ───── (Sequential cryptographic blockchain hash verification)
```

---

## 3. Technology Stack

| Domain | Technology | Implementation Detail |
| :--- | :--- | :--- |
| **Frontend** | React 18 + TypeScript + Vite | Enterprise Single Page App (SPA) with strict type safety |
| **Styling** | Vanilla CSS / Tailwind CSS + Lucide React | Modern dark-mode GovTech glassmorphism design system |
| **Visualizations** | Recharts + SVG Metrics | Live duplication trends, spend impact, and explainability bars |
| **Backend API** | FastAPI (Python 3.11+) + Uvicorn | Asynchronous REST endpoints with auto OpenAPI & Swagger docs |
| **Data Contracts** | Pydantic v2 | Typed schemas for Source Materials, Mappings, Scores & Audit Logs |
| **String & Blocking** | RapidFuzz | Token sort ratio, token set ratio, partial ratio & category blocking |
| **Attribute Extraction** | Python Regex Engines | Domain-specific specs: Pipes, Valves, Bearings, Cables, Pumps |
| **Semantic Matching** | Deterministic Cosine Stub | Decoupled interface; ready for pgvector + `all-MiniLM-L6-v2` |
| **Governance & Audit** | Python `hashlib` SHA-256 | Immutable chained hashes from a 64-char zero Genesis block |
| **Containerization** | Docker & Docker Compose | Multi-container setup with healthchecks and auto-reload |

---

## 4. Frontend Route Map

The application provides a simplified, examiner-friendly workflow across 4 core views:

| Route | Page | Purpose & Capabilities |
| :--- | :--- | :--- |
| `/` or `/dashboard` | **Dashboard** | 4 simple summary cards, problem overview, and an intuitive 5-step flow diagram. |
| `/upload` | **Upload Materials** | CSV catalog ingestion, sample data preview, and clean table of standardized items. |
| `/matching` | **Duplicate Review** | Clean side-by-side duplicate pair comparison, match confidence %, plain-English reasons, and proposed national code. |
| `/approvals` & `/audit` | **Approval & Audit** | Combined page with pending review cases, Reviewer 1 & 2 sign-offs, and verified chronological audit log. |

---

## 5. Comprehensive REST API Directory

All backend endpoints are documented interactively at `http://localhost:8000/docs`.

| Method | Endpoint | Description | Persistence Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | System health check and API operational status | Stateless |
| `GET` | `/api/demo/summary` | Live telemetry summary, metrics, and module readiness | In-Memory Sample |
| `GET` | `/api/materials/preview-sample` | Pre-parsed CPSE multi-source sample catalog | In-Memory Sample |
| `POST` | `/api/materials/preview-csv` | Ingestion preview for uploaded CPSE CSV files | In-Memory (`persisted: false`) |
| `POST` | `/api/materials/normalize-text` | Rule-based cleaning and UOM/term normalization | In-Memory (`persisted: false`) |
| `POST` | `/api/materials/extract-attributes` | Regex-anchored technical attribute extraction | In-Memory (`persisted: false`) |
| `GET` | `/api/matching/candidates/sample` | Candidate duplicate pairs generated via RapidFuzz | In-Memory Sample |
| `POST` | `/api/matching/candidates` | On-demand candidate detection for custom records | In-Memory (`persisted: false`) |
| `GET` | `/api/matching/embedding/sample` | Semantic vector cosine similarity preview | Deterministic Stub |
| `GET` | `/api/matching/hybrid-score/sample` | 8-signal weighted composite match scores | In-Memory Sample |
| `POST` | `/api/matching/hybrid-score` | Dynamic hybrid score computation for custom pairs | In-Memory (`persisted: false`) |
| `GET` | `/api/matching/explain/sample` | SHAP-style waterfall factor contributions | In-Memory Sample |
| `POST` | `/api/matching/explain` | Detailed feature explainability for custom pairs | In-Memory (`persisted: false`) |
| `POST` | `/api/matching/review-decision/demo`| Simulated reviewer decision action | In-Memory (`persisted: false`) |
| `GET` | `/api/approvals/demo-queue` | Dual-tier (L1/L2) pending governance queue | In-Memory Queue |
| `POST` | `/api/approvals/demo-action` | Transition approval state (L1 verify, L2 ratify) | In-Memory (`persisted: false`) |
| `GET` | `/api/audit/demo-trail` | Sequential SHA-256 chained audit trail | In-Memory Chained Log |
| `GET / POST` | `/api/audit/demo-verify` | Recompute cryptographic chain integrity | Real-Time Hash Check |

---

## 6. How to Run Locally

### Prerequisites
- **Python**: 3.10 or higher (3.11 recommended)
- **Node.js**: v18 or higher (v20+ recommended)
- **Docker & Docker Compose** (optional, for containerized run)

---

### Option A: Manual Local Execution (Recommended for Dev)

#### 1. Start the Backend:
```bash
# Navigate to backend
cd national-ai-material-master/backend

# Create and activate virtual environment
# Windows PowerShell:
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS:
# python3 -m venv .venv
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Launch FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Backend will be live at:
- **API Base:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Live Demo Summary:** [http://localhost:8000/api/demo/summary](http://localhost:8000/api/demo/summary)

#### 2. Start the Frontend:
```bash
# In a new terminal, navigate to frontend
cd national-ai-material-master/frontend

# Install dependencies
npm install

# Launch Vite development server
npm run dev
```
Frontend will be live at:
- **Web UI:** [http://localhost:5173](http://localhost:5173)

---

### Option B: Docker Compose Execution

To launch both frontend and backend in unified containers:
```bash
cd national-ai-material-master
docker compose up --build
```
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Sample data is automatically mounted read-only at `/app/sample-data`.

---

## 7. Verification & Automated Testing

Run the comprehensive end-to-end verification script against all 11 core endpoints:

```bash
cd national-ai-material-master/backend
python verify_final_demo.py
```

Expected Output:
```text
======================================================================
  NATIONAL AI MATERIAL MASTER - FINAL VERIFICATION SUITE
======================================================================
[PASS] GET /health (Status: 200)
[PASS] GET /api/demo/summary (Status: 200, 11 modules validated)
[PASS] GET /api/materials/preview-sample (Status: 200, 12 records)
[PASS] POST /api/materials/extract-attributes (Status: 200, 5/5 specs extracted)
[PASS] GET /api/matching/candidates/sample (Status: 200, 6 pairs detected)
[PASS] GET /api/matching/embedding/sample (Status: 200, cosine=0.9634)
[PASS] GET /api/matching/hybrid-score/sample (Status: 200, hybrid=0.924)
[PASS] GET /api/matching/explain/sample (Status: 200, 9 factors explained)
[PASS] GET /api/approvals/demo-queue (Status: 200, 3 pending cases)
[PASS] GET /api/audit/demo-trail (Status: 200, 5 events chained)
[PASS] POST /api/audit/demo-verify (Status: 200, verified=True, 0 breaks)
======================================================================
ALL 11 TESTS PASSED SUCCESSFULLY! PROTOTYPE IS DEMO-READY.
======================================================================
```

To verify the frontend TypeScript compilation:
```bash
cd national-ai-material-master/frontend
npm run build
```
*(Must exit with code 0 and zero compilation errors).*

---

## 8. SIH Demonstration Flow & Judge Presentation

A dedicated 5–7 minute judge presentation script with an elevator pitch, screen-by-screen talking points, architectural differentiators, and technical Q&A defense is provided in:

👉 **[`docs/demo-script.md`](file:///c:/Users/numan/OneDrive/Documents/New%20folder/national-ai-material-master/docs/demo-script.md)**

### Key Demo Beats:
1. **The Core Problem:** 300+ CPSEs buying the exact same items under incompatible codes.
2. **Deterministic Normalization:** Why regex-anchored attribute extraction is safer than generic LLMs.
3. **RapidFuzz Candidate Blocking:** Eliminating $O(N^2)$ cross-PSU comparisons in milliseconds.
4. **pgvector-Ready Architecture:** Clean semantic similarity decoupled from heavy GPU overhead.
5. **Explainable AI:** SHAP-style waterfall contribution charts designed for PSU procurement officers.
6. **Government Accountability:** Dual-tier L1/L2 governance with tamper-evident SHA-256 audit chaining.

---

## 9. Demo Mode Disclaimers & Non-Persistence Transparency

To ensure 100% technical transparency during SIH evaluation:
- **No Persistence:** All demo approvals, match reviews, and audit events are managed in-memory. Every API response returns `"persisted": false`.
- **Database Decoupling:** No live Supabase or PostgreSQL connection is required for this milestone prototype.
- **Semantic Stub:** The embedding engine uses a deterministic, reproducible local vector stub (`pgvector-ready`), avoiding multi-gigabyte Hugging Face model downloads during local judging.
- **XGBoost & SHAP Placeholders:** The hybrid scoring engine uses calibrated transparent rule weights; the 16-dimensional feature extraction pipeline is ready for supervised training once officer review labels accumulate.

---

## 10. Production Roadmap

| Phase | Milestone | Deliverables |
| :--- | :--- | :--- |
| **Phase 1** *(Current)* | **Core Prototype** | In-memory 9-stage pipeline, RapidFuzz blocking, hybrid scoring, explainability, L1/L2 approvals, SHA-256 audit trail. |
| **Phase 2** | **Persistence & Vector DB** | Supabase PostgreSQL 16 migrations, pgvector HNSW indexing, persistent audit tables. |
| **Phase 3** | **Production ML** | Local `bge-large-en-v1.5` embeddings, supervised XGBoost classifier trained on officer labels, native TreeSHAP. |
| **Phase 4** | **GovTech Enterprise Integration** | GeM (Government e-Marketplace) API integration, SAP ERP OData connectors, SAML 2.0 / OpenID PSU Single Sign-On (SSO). |
