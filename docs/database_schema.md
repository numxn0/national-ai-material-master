# Supabase PostgreSQL Target Database Schema

Target database: **Supabase PostgreSQL** with `pgvector` extension enabled.

```sql
-- Enable vector extension for semantic embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Organizations / PSUs table
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,       -- e.g., 'IR_NORTH', 'CIL', 'SAIL'
    name VARCHAR(255) NOT NULL,
    ministry VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Raw Ingested Materials (staged before deduplication)
CREATE TABLE materials_raw (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    original_item_code VARCHAR(100) NOT NULL,
    raw_description TEXT NOT NULL,
    raw_unit_of_measure VARCHAR(50),
    raw_category VARCHAR(150),
    price_unit NUMERIC(12, 2),
    raw_metadata JSONB DEFAULT '{}'::jsonb,
    ingestion_batch_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'STAGED',   -- 'STAGED', 'PROCESSED', 'FLAGGED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Standardized Master Materials (Canonical SKUs)
CREATE TABLE materials_master (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_item_code VARCHAR(100) UNIQUE NOT NULL, -- e.g., 'NAMM-MEC-BRG-00192'
    standardized_title VARCHAR(255) NOT NULL,
    category_id VARCHAR(100) NOT NULL,
    unit_of_measure VARCHAR(20) NOT NULL,          -- e.g., 'NOS', 'KGS', 'MTR'
    specifications JSONB DEFAULT '{}'::jsonb,      -- { "bore_diameter": "25mm", "grade": "SS304" }
    embedding vector(384),                         -- 384-dim embedding from all-MiniLM-L6-v2
    approval_status VARCHAR(50) DEFAULT 'APPROVED',-- 'DRAFT', 'L1_PENDING', 'L2_PENDING', 'APPROVED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- HNSW Vector Index for sub-millisecond similarity queries
CREATE INDEX ON materials_master USING hnsw (embedding vector_cosine_ops);

-- 4. Material Aliases & Cross-References
CREATE TABLE material_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_id UUID REFERENCES materials_master(id) ON DELETE CASCADE,
    raw_item_id UUID REFERENCES materials_raw(id),
    source_org_id UUID REFERENCES organizations(id),
    source_item_code VARCHAR(100) NOT NULL,
    confidence_score NUMERIC(5, 4),               -- e.g. 0.9425
    match_tier VARCHAR(50),                       -- 'EXACT_CODE', 'VECTOR_COSINE', 'HYBRID_XGBOOST'
    verified_by VARCHAR(150),
    verified_at TIMESTAMP WITH TIME ZONE
);

-- 5. AI Deduplication Review Queue
CREATE TABLE deduplication_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_raw_id UUID REFERENCES materials_raw(id),
    candidate_master_id UUID REFERENCES materials_master(id),
    rapidfuzz_score NUMERIC(5, 2),
    vector_similarity NUMERIC(5, 4),
    xgboost_composite_score NUMERIC(5, 4),
    shap_explanations JSONB,                      -- Feature importance factors
    decision VARCHAR(50) DEFAULT 'PENDING',       -- 'PENDING', 'APPROVED', 'REJECTED'
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Immutable Compliance Audit Trail
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    actor VARCHAR(150) NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_entity VARCHAR(150) NOT NULL,
    details TEXT,
    sha256_hash VARCHAR(64) NOT NULL
);
```

---

## 7. pgvector Integration & Indexing Planning Notes (Planning Only — No Migration Yet)

> [!NOTE]
> **Prototype Status**: The project currently runs a **lightweight local deterministic embedding stub** (`backend/app/services/embedding_service.py`). No database migrations have been applied, no tables have been created, and no database persistence is performed yet.

### Planned Vector Storage & Index Specifications:
1. **Column Definition**:
   - `materials_master.embedding vector(384)`: 384-dimensional dense vector populated by `all-MiniLM-L6-v2` or `bge-small-en-v1.5`.
   - Optional alias caching: `materials_raw.embedding_preview vector(64)` for fast pre-filtering.
2. **Indexing Techniques**:
   - **HNSW (Hierarchical Navigable Small World)**:
     ```sql
     CREATE INDEX idx_materials_master_embedding_hnsw 
     ON materials_master 
     USING hnsw (embedding vector_cosine_ops) 
     WITH (m = 16, ef_construction = 64);
     ```
     - *Advantage*: Delivers $O(\log N)$ search latency, sub-5ms recall for interactive deduplication queues.
   - **IVFFlat (Inverted File Flat)**:
     ```sql
     CREATE INDEX idx_materials_master_embedding_ivfflat 
     ON materials_master 
     USING ivfflat (embedding vector_cosine_ops) 
     WITH (lists = 100);
     ```
     - *Advantage*: Faster index build times and lower RAM overhead for massive bulk PSU catalog ingestions.
3. **Migration Prerequisites**:
   - Supabase project provisioning with `pgvector` extension enabled (`CREATE EXTENSION IF NOT EXISTS vector;`).
   - Automated Alembic or Supabase SQL migration script once governance schema and approval states are finalized.

