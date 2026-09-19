"""
Demo Overview and System Health API Router.
Exposes GET /api/demo/summary providing an executive snapshot of all active
and planned pipeline modules, dataset metrics, and non-persistence disclosures.
"""

from fastapi import APIRouter
from datetime import datetime, timezone

from app.schemas.demo import DemoSummaryResponse, ModuleStatus
from app.services.approval_workflow import build_demo_approval_queue
from app.services.audit_trail import build_demo_audit_trail, verify_audit_chain_integrity

router = APIRouter(prefix="/demo", tags=["Demo & System Summary"])


@router.get("/summary", response_model=DemoSummaryResponse)
async def get_demo_summary():
    """
    Returns an executive, live summary of prototype readiness, sample dataset metrics,
    module operational statuses, and explicit disclosures of demonstration-only execution.
    """
    # Build live queue and audit trail in memory
    queue = build_demo_approval_queue(min_candidate_score=0.45)
    trail = build_demo_audit_trail()
    verification = verify_audit_chain_integrity(trail.events)

    sample_count = 10
    cand_count = queue.total_cases
    high_conf_count = sum(1 for c in queue.cases if c.hybrid_score >= 0.85)
    total_savings = sum(c.procurement_impact.estimated_savings_inr for c in queue.cases)

    modules = [
        ModuleStatus(
            name="CSV Ingestion & Schema Mapping",
            key="ingestion_preview",
            status="READY",
            description="Header normalization, CPSE column detection, canonical schema validation",
            implementation="Pandas/Python csv parser + Pydantic v2 Canonical Source Schema"
        ),
        ModuleStatus(
            name="Data Cleaning & Text Normalization",
            key="normalization",
            status="READY",
            description="Noise stripping, punctuation normalization, UOM unification, tokenization",
            implementation="Regex-based taxonomy cleaning + standard description synthesizer"
        ),
        ModuleStatus(
            name="Rule-Based Attribute Extraction",
            key="attribute_extraction",
            status="READY",
            description="Domain attribute parser for Bearings, Valves, Pipes, Fasteners, Cables, Motors",
            implementation="Deterministic regex + domain engineering specification extractors"
        ),
        ModuleStatus(
            name="Candidate Duplicate Detection",
            key="candidate_matching",
            status="READY",
            description="Pairwise fuzzy comparison with domain blocking filters",
            implementation="RapidFuzz Token Sort & Token Set Ratio (C++ Levenshtein)"
        ),
        ModuleStatus(
            name="Semantic Vector Embedding Stub",
            key="embedding_service",
            status="READY",
            description="64-dimensional feature hashing cosine proximity (pgvector-ready)",
            implementation="Deterministic SHA-256 token projection with L2 normalization"
        ),
        ModuleStatus(
            name="Hybrid Match Scoring Engine",
            key="hybrid_scoring",
            status="READY",
            description="8-signal weighted fusion + hard conflict penalty ceilings",
            implementation="Rule-based fusion (25% text, 20% attr, 20% vector, 10% token, etc.)"
        ),
        ModuleStatus(
            name="SHAP-Style Explainability Layer",
            key="explainability",
            status="READY",
            description="9-factor attributions, positive drivers, risk analysis, discrepancy warnings",
            implementation="Deterministic factor decomposition + reviewer guidance generator"
        ),
        ModuleStatus(
            name="Dual-Tier Governance & National Code Proposals",
            key="approval_workflow",
            status="DEMO_READY",
            description="L1 Technical Nodal verification + L2 Ministry Authority ratification",
            implementation="In-memory multi-tier state simulation + NAMM code synthesizer"
        ),
        ModuleStatus(
            name="Cryptographic Tamper-Evident Audit Trail",
            key="audit_trail",
            status="VERIFIED",
            description="Blockchain-style SHA-256 hash chaining with automated integrity checks",
            implementation="Cryptographic parent hash chaining starting from Genesis block"
        ),
        ModuleStatus(
            name="Supabase PostgreSQL Persistence & pgvector",
            key="persistence",
            status="PLANNED",
            description="Live persistent database storage with HNSW vector index",
            implementation="Supabase PostgreSQL + pgvector extension (Planned Post-Hackathon)"
        ),
        ModuleStatus(
            name="Supervised XGBoost Classifier & TreeSHAP",
            key="ml_classifier",
            status="PLANNED",
            description="Trained gradient boosting trees on 500+ audited Nodal Officer labels",
            implementation="XGBoost/LightGBM + shap.TreeExplainer (Planned Post-Hackathon)"
        ),
    ]

    return DemoSummaryResponse(
        service_status="operational",
        service_name="National AI Material Master",
        version="1.0.0-sih-prototype",
        timestamp=datetime.now(timezone.utc).isoformat(),
        sample_material_count=sample_count,
        candidate_count=cand_count,
        high_confidence_match_count=high_conf_count,
        approval_case_count=queue.total_cases,
        pending_l1_count=queue.pending_l1_count,
        pending_l2_count=queue.pending_l2_count,
        audit_event_count=trail.total_events,
        audit_chain_status=verification.chain_status,
        total_estimated_savings_inr=round(total_savings, 2),
        modules=modules,
        persistence_status="demo_in_memory_only",
        is_database_connected=False,
        planned_production_integrations=[
            "Supabase PostgreSQL Relational Storage",
            "pgvector HNSW Vector Indexing",
            "Sentence Transformers (all-MiniLM-L6-v2 / BAAI/bge-small)",
            "XGBoost Supervised Gradient Boosting Classifier",
            "TreeSHAP Exact Feature Attribution",
            "Enterprise OAuth2 / CPSE SAML Single Sign-On",
            "Role-Based Access Control (RBAC) for Nodal Reviewers"
        ],
        notes="All metrics generated dynamically in-memory from sample CPSE datasets without disk or database persistence."
    )
