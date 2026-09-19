# National AI Material Master — Examiner Demo Script (5 Minutes)

## Smart India Hackathon (SIH) | Problem Statement: Unified National Material Master Catalog for Indian CPSEs / PSUs

---

## Executive Pitch (30 Seconds)

> **"Good morning / afternoon, esteemed examiners.**
> 
> Across India's 300+ Central Public Sector Enterprises (CPSEs) like ONGC, IOCL, BHEL, NTPC, and Indian Railways, the exact same physical spare parts and materials are purchased under completely different item codes, descriptions, and units of measurement.
> 
> This creates **massive procurement duplication, idle warehouse inventory, zero inter-PSU sharing, and thousands of crores in locked capital**.
> 
> Today, we present the **National AI Material Master**: an AI-assisted standardization and deduplication system designed specifically for Indian public sector procurement.
> 
> Let's walk through our working prototype."

---

## 4-Step Live Demonstration Flow

### Step 1: Dashboard Overview (`/dashboard`) — 45 Seconds

**Screen:** [Dashboard](http://localhost:5173/)

**Presenter Action:**
1. Point to the clean, white executive dashboard.
2. Highlight the **4 core metrics**:
   - **Materials Uploaded:** 10 sample items loaded across CPSE catalogs.
   - **Duplicate Candidates:** 6 potential matches detected.
   - **Pending Review:** Cases awaiting technical officer sign-off.
   - **National Codes Proposed:** Unified master codes ready for publication.
3. Walk the examiner through the **5-Step Flow Diagram**:
   - **Upload** $\rightarrow$ **Standardize** $\rightarrow$ **Match** $\rightarrow$ **Approve** $\rightarrow$ **National Code**

**Talking Points:**
> *"Our platform follows a transparent 5-step journey. We take messy, unstandardized inventory spreadsheets and transform them into verified National Material Master records without technical complexity."*

---

### Step 2: Upload Materials (`/upload`) — 60 Seconds

**Screen:** [Upload Materials](http://localhost:5173/upload)

**Presenter Action:**
1. Click **"Upload Materials"** in the navigation bar.
2. Show the sample CPSE catalog already loaded (or click **"Preview Sample Data"**).
3. Point out the clean table of uploaded materials:
   - Notice how original messy descriptions like `"PIPE CS SEAMLESS 4 INCH SCH 40 A106-B"` and `"CARBON STEEL SEAMLESS PIPE 4\" SCH 40 ASTM A106 GRADE B"` are standardized.
   - Units of measurement are normalized (e.g., `MTR` $\rightarrow$ `M`, `NOS` $\rightarrow$ `EA`).
4. (Optional) Briefly open the collapsed **"Advanced Tools"** at the bottom to demonstrate live text normalization or attribute extraction for any custom description.

**Talking Points:**
> *"In real-world PSU procurement, descriptions contain spelling typos, non-standard abbreviations, and arbitrary formatting. Our system automatically cleans text, standardizes units, and extracts critical engineering specifications before matching begins."*

---

### Step 3: Duplicate Review (`/matching`) — 75 Seconds

**Screen:** [Duplicate Review](http://localhost:5173/matching)

**Presenter Action:**
1. Navigate to **"Duplicate Review"**.
2. Point out the clear side-by-side card comparing **Material A** (e.g. Indian Railways) and **Material B** (e.g. Coal India):
   - **Match Confidence:** High Confidence (e.g., `92% Match`).
   - **Why did these materials match?** Review the plain-English bullets (e.g., *"Identical ball bearing size: 6205"*, *"Same rubber seal: 2RS"*, *"Matching unit: Numbers"*).
   - **Proposed National Material Code:** Show the generated master code (e.g., `NAMM-BRG-6205-2RS`).
3. Click **"Approve as Match"** or use the Next arrow to step through candidate pairs.
4. (Optional) Toggle the collapsed **"Technical Scoring Details"** accordion to show the breakdown of text similarity, attribute matching, and description similarity.

**Talking Points:**
> *"Notice the examiner does not need to decipher complex algorithms. The system presents the two items side-by-side, shows a clear percentage match, explains exactly why they matched in plain English, and proposes a single unified National Code."*

---

### Step 4: Approval & Audit (`/approvals`) — 60 Seconds

**Screen:** [Approval & Audit](http://localhost:5173/approvals)

**Presenter Action:**
1. Navigate to **"Approval & Audit"**.
2. Review the **Pending Approvals Queue**:
   - Point to the two-tier review status: **Reviewer 1 (Technical Nodal)** and **Reviewer 2 (Ministry Authority)**.
   - Point out the estimated annual procurement savings (e.g., `₹336K`).
   - Click **"Approve"** to finalize the case.
3. Scroll down to the **Audit Log**:
   - Show the chronological event log recording every action: Ingestion, Duplicate Flagged, Reviewer Sign-off.
   - Point to the **"Audit Log Verified"** green badge confirming that the records are tamper-evident and integrity-checked.
   - Click **"Export Audit CSV"** to demonstrate compliance export.

**Talking Points:**
> *"For Government procurement, human-in-the-loop accountability is mandatory. We support two-step officer sign-offs and an immutable, tamper-evident audit log that complies with CVC and CAG audit requirements."*

---

## Conclusion & Impact (30 Seconds)

> *"In summary, esteemed examiners:
> The National AI Material Master solves a real, high-impact problem for Indian industry.
> By replacing duplicate part numbers with unified National Material Codes, public sector enterprises can eliminate redundant buffer stocks, unlock inter-PSU emergency sharing, and save thousands of crores annually.
> 
> Thank you, and we welcome your questions!"*

---

## Technical Q&A Defense

### Q1: "Why not simply use ChatGPT or a generic LLM?"
- **Hallucination Risk:** Generic LLMs can hallucinate engineering grades, threading standards, or pressure classes (e.g., confusing PN16 with PN40 valves), risking dangerous industrial equipment failures.
- **Cost & Speed:** Evaluating millions of PSU catalog pairs using commercial cloud LLM APIs is slow and cost-prohibitive.
- **Our Solution:** A deterministic hybrid engine that is explainable, safe, deployable on-premises, and 100% cost-effective.

### Q2: "Is this prototype persisting data to a database?"
- *"For this SIH evaluation prototype, all actions run in-memory against bundled CPSE datasets. No database setup or persistent migrations are required. The Pydantic schemas and service interfaces are 100% prepared for PostgreSQL/pgvector database connection in the next phase."*

### Q3: "How does the system scale to millions of CPSE catalog items?"
- We use a two-stage retrieval pipeline: category filtering and token blocking prune millions of items to top candidate pairs in milliseconds, followed by detailed attribute and similarity scoring only on relevant pairs.
