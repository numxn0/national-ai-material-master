# National AI Material Master — System Architecture

## 1. Executive Summary
The **National AI Material Master** is an AI-powered data deduplication, standardization, and governance platform tailored for Indian Public Sector Undertakings (PSUs) and Ministries (e.g., Indian Railways, Coal India, ONGC, SAIL, NTPC). 

It solves the massive catalog redundancy problem where identical industrial spares and materials are cataloged under disparate naming conventions, varied units of measure, and non-standard part numbers across departmental silos.

```
+-----------------------------------------------------------------------------------+
|                        National AI Material Master Architecture                   |
+-----------------------------------------------------------------------------------+
                                        |
                 [Data Ingestion: CSV, Excel, ERP APIs, PDFs]
                                        |
                                        v
                       +---------------------------------+
                       | 1. Ingestion & Sanitization     |
                       | - Unicode normalization         |
                       | - Punctuation & case standard.  |
                       | - Noise token stripping         |
                       +---------------------------------+
                                        |
                                        v
                       +---------------------------------+
                       | 2. Attribute Extraction         |
                       | - spaCy NER & Regex Engine      |
                       | - Dimension, Grade, Spec parser |
                       | - Unit of Measure standardizer  |
                       +---------------------------------+
                                        |
                                        v
                       +---------------------------------+
                       | 3. Multi-Tier AI Matching Engine|
                       | - Stage A: RapidFuzz Levenshtein|
                       | - Stage B: Embeddings (pgvector)|
                       | - Stage C: XGBoost + SHAP       |
                       |   Explainability Classifier     |
                       +---------------------------------+
                                        |
                 +----------------------+----------------------+
                 | (Confidence >= 90%)                         | (70% <= Conf < 90%)
                 v                                             v
       +--------------------+                        +--------------------+
       | Auto-Link Candidate|                        | Human-in-the-Loop  |
       | (Pre-staged Master)|                        | Review Queue       |
       +--------------------+                        +--------------------+
                 |                                             |
                 +----------------------+----------------------+
                                        |
                                        v
                       +---------------------------------+
                       | 4. Dual-Tier Governance         |
                       | - Tier 1: Nodal Officer Verify  |
                       | - Tier 2: Ministry Ratification |
                       +---------------------------------+
                                        |
                                        v
                       +---------------------------------+
                       | 5. Master Catalog & Audit Trail |
                       | - Supabase PostgreSQL + pgvector|
                       | - Immutable SHA-256 Audit Log   |
                       +---------------------------------+
```

---

## 2. Technical Stack Breakdown

| Layer | Component | Description / Role |
| :--- | :--- | :--- |
| **Frontend** | React 18 + TypeScript + Vite | Enterprise SPA with instant hot-reloading & high type safety |
| **Styling & UI** | Tailwind CSS + Lucide Icons | Responsive modern design system adhering to GovTech standards |
| **Visualizations** | Recharts | Interactive duplication metrics, savings charts, and confidence distributions |
| **Backend API** | FastAPI + Uvicorn (Python) | High-concurrency async REST API with auto-generated OpenAPI docs |
| **Database** | Supabase PostgreSQL + pgvector | Relational database with integrated HNSW vector indexing |
| **AI Roadmap** | RapidFuzz, spaCy, XGBoost, SHAP | Tiered matching: string distance -> semantic vector -> gradient boosting |
| **OCR Pipeline** | PaddleOCR (Planned) | Digitization of legacy technical spec sheets and scanned blue-prints |

---

## 3. Planned AI Matching Pipeline
1. **Tier 1 (Fast Blocking - RapidFuzz)**:
   - High-speed fuzzy string comparison using token sort ratio and weighted Levenshtein distance.
   - Reduces search space from $O(N^2)$ to $O(N \cdot K)$ candidate pairs.
2. **Tier 2 (Semantic Vector Retrieval - pgvector)**:
   - Deep text embeddings generated via `sentence-transformers/all-MiniLM-L6-v2`.
   - Semantic similarity search over cosine distance in PostgreSQL with HNSW indexes.
3. **Tier 3 (Composite Classifier & Explainability - XGBoost + SHAP)**:
   - Supervised model evaluating token overlap, dimension compatibility, and material grade match.
   - SHAP values provide procurement officers with human-readable rationale (e.g., "+42% confidence due to M12x50 dimension match").

### 3.1 Semantic Embedding Architecture & pgvector Roadmap
- **Current Implementation (Phase 1 Stub)**:
  - Employs a **deterministic local feature hashing stub** (`backend/app/services/embedding_service.py`).
  - Projects synthesized material text (standard description, category, metallurgy, manufacturer, extracted technical attributes) into a 64-dimensional unit-normalized vector ($\|\mathbf{v}\|_2 = 1.0$).
  - Evaluates semantic similarity via cosine dot product without heavy model weights, GPU dependencies, or external API calls.
  - Generates preview-only scores for candidate duplicate pairs while preserving RapidFuzz as the primary scoring mechanism.
- **Future Upgrade Path (Production Rollout)**:
  - **Model Migration**: Drop-in upgrade to domain-specialized Transformer models (e.g., `sentence-transformers/all-MiniLM-L6-v2`, `BAAI/bge-small-en-v1.5`, or `intfloat/e5-small-v2`).
  - **pgvector Integration**: Persist 384- or 768-dimensional embeddings in PostgreSQL using the native `vector(N)` type.
  - **Approximate Nearest Neighbor (ANN) Indexing**: Leverage PostgreSQL HNSW (`vector_cosine_ops`) or IVFFlat indexes for sub-5ms semantic nearest-neighbor candidate generation across millions of CPSE records.
  - **Multi-Modal Hybrid Fusion**: Combine semantic embedding distance with RapidFuzz token ratios, attribute constraint matrices, and XGBoost gradient-boosted decision trees for final master catalog auto-linkage.

### 3.2 Hybrid Match Scoring Engine & XGBoost Training Roadmap
- **Current Implementation (Rule-Based Hybrid Engine)**:
  - Operates downstream of RapidFuzz blocking and semantic vector computation (`backend/app/services/hybrid_scoring.py`).
  - Synthesizes 8 weighted signals into a composite duplicate confidence score:
    - **25%** RapidFuzz Description Similarity
    - **20%** Attribute Specification Parity
    - **20%** Dense Semantic Vector Cosine Similarity
    - **10%** Normalized Token Jaccard Overlap
    - **10%** Taxonomy Category Compatibility
    - **5%** Unit of Measure Alignment
    - **5%** OEM Manufacturer & Part Number Parity
    - **5%** Technical Attribute Completeness Bonus
  - Enforces **hard conflict penalty caps** preventing false-positive duplicate suggestions:
    - Taxonomy domain incompatible: capped at $\le 0.30$
    - Bearing series number conflict: capped at $\le 0.40$
    - Multiple critical attribute conflicts: capped at $\le 0.45$
    - OEM part number conflict: capped at $\le 0.50$
    - Single critical parameter conflict: capped at $\le 0.60$
- **Why XGBoost is not Trained Yet (Architectural Decision)**:
  - In public sector catalog standardization, training a machine learning classifier without validated ground-truth labels causes severe data leakage, arbitrary bias, and uncalibrated probabilities.
  - The deterministic rule-based hybrid scoring engine delivers 100% auditable, explainable duplicate scores immediately, while systematically extracting and formatting 14+ ML features.
- **Future Supervised Training Data Requirement**:
  - **Feature Extraction**: Pairwise feature matrix generated automatically by `ml_feature_pipeline.py`.
  - **Ground-Truth Labeling**: Human-in-the-loop decisions recorded by Departmental Nodal Officers (Tier 1) and Ministry Authorities (Tier 2):
    - `label = 1`: Approved as master duplicate / alias linkage.
    - `label = 0`: Rejected as distinct inventory SKU.
  - **Model Retraining Trigger**: Scheduled automatically upon collecting 500+ audited human decisions (minimum 250 positive / 250 negative).
  - **SHAP Explainability**: SHAP value generation will be activated on the trained tree ensemble to supply procurement officers with mathematical feature attribution for every duplicate suggestion.

### 3.3 SHAP-Style Explainability Layer & Reviewer Workflow
- **Current Implementation (Deterministic Factor Attribution)**:
  - Operates directly downstream of the hybrid match scoring engine (`backend/app/services/explainability.py`).
  - Translates composite hybrid scores and 16-dimensional feature vectors into human-readable, deterministic factor attributions across 9 dimensions:
    - `description_similarity` (Lexical parity)
    - `attribute_similarity` (Specification alignment)
    - `semantic_similarity` (Vector space domain match)
    - `token_overlap` (Shared token Jaccard overlap)
    - `category_compatibility` (Taxonomy classification parity)
    - `uom_compatibility` (Unit of Measure compatibility)
    - `manufacturer_part_model` (OEM brand & part number parity)
    - `completeness_bonus` (Critical specification bonus)
    - `conflict_penalty` (Penalty deduction or ceiling cap)
  - Classifies factor directions:
    - **POSITIVE**: Pushes confidence toward duplicate classification (rendered as green contribution bars with evidence tokens).
    - **NEGATIVE**: Imposes penalties, highlights conflicts, or flags specification gaps (rendered as amber/rose risk bars).
    - **NEUTRAL**: Baseline or negligible impact on recommendation.
  - Generates executive **Reviewer Summaries** tailored to score bands and conflict states (e.g., auto-match recommendations, specification gap alerts, bearing mismatch rejections).
  - Flags **Missing Data Asymmetries** (attributes present on one CPSE record but unstated on the other) and **Technical Conflict Statements**.
  - Produces immutable **Audit Records** tagged with method version `hybrid-rule-v1 + semantic-stub-v1 + explainability-v1`.
- **Reviewer Decision Protocol (In-Memory Demo Mode)**:
  - Exposes `POST /api/matching/review-decision/demo` allowing CPSE Nodal Officers to record `APPROVE`, `REJECT`, or `NEEDS_MORE_INFO` actions with optional remarks.
  - Complies strictly with zero-persistence constraints: acknowledges decisions in memory with explicit disclosure (`"Demo-only decision accepted in memory; not persisted."`).
- **Future Upgrade Path to TreeSHAP**:
  - Once the supervised XGBoost/LightGBM model is trained on 500+ verified Nodal Officer labels, the system will seamlessly transition from deterministic formula weights to TreeSHAP (`shap.TreeExplainer`).
  - Exact Shapley values ($\phi_i$) will compute the marginal contribution of each feature vector coordinate to the tree ensemble log-odds, fully backward-compatible with the existing `ExplanationFactor` schema and UI visualizer.

---

## 4. Governance & Dual-Approval Protocol

### 4.1 Overview of Dual-Tier Governance
To safeguard procurement safety across mission-critical CPSE operations (e.g. power generation at NTPC, rolling stock maintenance at Indian Railways, refinery piping at IOCL), catalog deduplication is never executed blindly. The platform implements a strict dual-tier human-in-the-loop governance protocol:
- **Level-1 (Technical Nodal Officer Verification)**: Specialized departmental nodal officers verify that technical tolerances, operating clearances, metallurgy grades, and physical dimensions are interchangeable for plant operation.
- **Level-2 (Ministry Oversight Authority Ratification)**: Department of Public Enterprises (DPE) and nodal ministry administrators ratify cross-enterprise procurement harmonization, register the canonical SKU, and bind legacy CPSE item codes as catalog aliases.

### 4.2 National Material Code Generation (NAMM Specification)
The platform features a deterministic national material master nomenclature generator (`backend/app/services/approval_workflow.py`):
- **Bearings**: `NAMM-BRG-{SERIES}-{SEALS}` (e.g. `NAMM-BRG-6205-2RS`, `NAMM-BRG-6205-ZZ`)
- **Pipes & Tubes**: `NAMM-PIP-{MATERIAL}-{NOMINAL_BORE}-{SCHEDULE}` (e.g. `NAMM-PIP-SS-050-S40`, `NAMM-PIP-CS-100-S80`)
- **Valves**: `NAMM-VLV-{TYPE}-{SIZE}-{RATING}` (e.g. `NAMM-VLV-BALL-050-PN16`, `NAMM-VLV-BALL-050-CL150`)
- **Electrical Cables**: `NAMM-CBL-{CONDUCTOR}-{CORES}C-{SIZE}` (e.g. `NAMM-CBL-AL-3C-185SQ`)
- **Motors**: `NAMM-MTR-{POWER}KW-{RPM}RPM` (e.g. `NAMM-MTR-15KW-1440RPM`)
- **Deterministic Fallback**: `NAMM-DRAFT-{CATEGORY_SLUG}-{MD5_HASH[:6]}`

### 4.3 Governance Routing & Approval Tier Rules
Every candidate duplicate pair is automatically routed to an approval workflow stage based on its calibrated hybrid confidence score:
| Hybrid Classification | Confidence Score | Routing Requirement | Governance Action |
| :--- | :--- | :--- | :--- |
| **AUTO_MATCH_RECOMMENDED** | $\ge 0.88$ | `L1_ONLY` | Expedited review; single sign-off by Technical Nodal Officer |
| **STRONG_REVIEW_CANDIDATE** | $0.75 - 0.88$ | `L1_AND_L2` | Dual-tier verification: Nodal verification + Ministry ratification |
| **MANUAL_REVIEW_REQUIRED** | $0.60 - 0.75$ | `L1_AND_L2` | Dual-tier verification with engineering drawing inspection |
| **WEAK_MATCH_REVIEW_OPTIONAL**| $0.45 - 0.60$ | `L2_SPECIALIST` | Domain specialist review; alias creation optional upon inspection |
| **REJECTED_BY_SCORING** | $< 0.45$ | `REJECTED_ONLY` | Automatically flagged as distinct inventory SKUs |

### 4.4 Procurement Impact Modeling
Standardizing duplicate items enables aggregated procurement, eliminating fragmented low-volume purchasing across CPSEs:
- **Annual Spend Overlap Benchmark**: Derived deterministically by industrial domain (e.g., Bearings: ₹24 Lakhs; Valves: ₹48 Lakhs; Cables: ₹65 Lakhs; Motors: ₹55 Lakhs).
- **Harmonization Savings Percentage**: Scales with AI confidence (14% for high-confidence matches $\ge 0.85$, 12% for medium confidence $\ge 0.65$, 9% baseline).
- **Risk Profiling**: Classified as `LOW`, `MEDIUM`, or `HIGH` risk based on attribute completeness, tolerance variance, and critical parameter parity.

### 4.5 Cryptographic SHA-256 Tamper-Evident Audit Trail
To satisfy Central Vigilance Commission (CVC) and Comptroller and Auditor General (CAG) audit readiness, the platform implements a blockchain-inspired, cryptographically linked audit ledger (`backend/app/services/audit_trail.py`):
1. **Genesis Block Linkage**: The first event in the ledger chains to a designated 64-character zero string:
   $$\text{previous\_hash}_0 = \mathtt{0000000000000000000000000000000000000000000000000000000000000000}$$
2. **Sequential Hash Chaining**: Every event $i$ seals its state, timestamp, actor, action, and payload into a SHA-256 signature chained to event $i-1$:
   $$\text{hash\_sig}_i = \text{SHA-256}\Big(\text{hash\_sig}_{i-1} \parallel \text{audit\_id}_i \parallel \text{timestamp}_i \parallel \text{actor}_i \parallel \text{action}_i \parallel \text{entity\_id}_i \parallel \text{payload\_hash}_i\Big)$$
3. **Automated Chain Verification**: The `GET /api/audit/demo-verify` endpoint iterates sequentially from Genesis to the current tip. Any payload alteration, timestamp tampering, or block deletion instantly triggers a `CHAIN_BROKEN` alert identifying the exact corrupted block index.

