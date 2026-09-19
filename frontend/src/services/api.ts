const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`Health HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return {
      status: 'offline_or_mock',
      service: 'National AI Material Master API (Local UI Fallback)',
      version: '0.1.0',
      database_target: 'Supabase PostgreSQL (Ready)',
      ai_pipeline_status: {
        rapidfuzz: 'standby',
        embeddings: 'standby',
        xgboost: 'standby'
      }
    };
  }
}

export async function fetchMaterials() {
  try {
    const res = await fetch(`${API_BASE}/api/materials`);
    if (!res.ok) throw new Error(`Materials HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { items: [] };
  }
}

export async function fetchMatchingQueue() {
  try {
    const res = await fetch(`${API_BASE}/api/matching/queue`);
    if (!res.ok) throw new Error(`Matching HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { data: [] };
  }
}

export async function fetchApprovals() {
  try {
    const res = await fetch(`${API_BASE}/api/approvals/pending`);
    if (!res.ok) throw new Error(`Approvals HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { data: [] };
  }
}

export async function fetchAuditLogs() {
  try {
    const res = await fetch(`${API_BASE}/api/audit/logs`);
    if (!res.ok) throw new Error(`Audit HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { logs: [] };
  }
}

export async function previewSampleMaterials() {
  const res = await fetch(`${API_BASE}/api/materials/preview-sample`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Sample preview failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function previewCsvUpload(file: File, sourceCpse?: string, sourceSystem?: string) {
  const formData = new FormData();
  formData.append('file', file);
  if (sourceCpse) formData.append('source_cpse', sourceCpse);
  if (sourceSystem) formData.append('source_system', sourceSystem);

  const res = await fetch(`${API_BASE}/api/materials/preview-csv`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `CSV preview upload failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function normalizeText(payload: {
  raw_description: string;
  uom?: string;
  category?: string;
}) {
  const res = await fetch(`${API_BASE}/api/materials/normalize-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Text normalization failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function extractAttributes(payload: {
  raw_description: string;
  category?: string;
  uom?: string;
}) {
  const res = await fetch(`${API_BASE}/api/materials/extract-attributes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Attribute extraction failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchSampleDuplicateCandidates(minScore: number = 0.65) {
  const res = await fetch(`${API_BASE}/api/matching/candidates/sample?min_score=${minScore}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Candidate duplicate detection failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchDuplicateCandidates(payload: {
  materials: any[];
  min_score?: number;
}) {
  const res = await fetch(`${API_BASE}/api/matching/candidates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Candidate matching failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function generateEmbedding(payload: {
  text: string;
  dimensions?: number;
}) {
  const res = await fetch(`${API_BASE}/api/matching/embedding/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Embedding generation failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function compareEmbeddings(payload: {
  material_a: any;
  material_b: any;
  dimensions?: number;
}) {
  const res = await fetch(`${API_BASE}/api/matching/embedding/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Semantic similarity comparison failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchSampleSemanticComparisons() {
  const res = await fetch(`${API_BASE}/api/matching/embedding/sample`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Sample semantic comparisons failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchSampleHybridScoring(minScore: number = 0.50) {
  const res = await fetch(`${API_BASE}/api/matching/hybrid-score/sample?min_candidate_score=${minScore}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Sample hybrid scoring failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function scoreCandidatesHybrid(candidates: any[]) {
  const res = await fetch(`${API_BASE}/api/matching/hybrid-score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidates }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Hybrid scoring calculation failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchMLTrainingPlan() {
  const res = await fetch(`${API_BASE}/api/matching/ml-training-plan`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch ML training plan: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchSampleMLFeatureExport(minScore: number = 0.50) {
  const res = await fetch(`${API_BASE}/api/matching/ml-feature-export/sample?min_candidate_score=${minScore}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to export ML features: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchSampleExplanations(minScore: number = 0.50) {
  const res = await fetch(`${API_BASE}/api/matching/explain/sample?min_candidate_score=${minScore}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch sample explanations: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function explainCandidates(candidates: any[]) {
  const res = await fetch(`${API_BASE}/api/matching/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(candidates),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Explainability calculation failed with HTTP ${res.status}`);
  }
  return await res.json();
}

export async function submitReviewDecisionDemo(payload: {
  candidate_id: string;
  decision: 'APPROVE' | 'REJECT' | 'NEEDS_MORE_INFO';
  reviewer_note?: string;
  reviewer_name?: string;
}) {
  const res = await fetch(`${API_BASE}/api/matching/review-decision/demo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Review decision submission failed with HTTP ${res.status}`);
  }
  return await res.json();
}

// --- Prompt 11 Demo Approval & Cryptographic Audit Endpoints ---

export async function fetchDemoApprovalQueue(minScore: number = 0.45) {
  const res = await fetch(`${API_BASE}/api/approvals/demo-queue?min_score=${minScore}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch demo approval queue: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function submitDemoApprovalAction(payload: {
  approval_case_id: string;
  decision: 'APPROVE' | 'REJECT' | 'NEEDS_MORE_INFO';
  reviewer_name?: string;
  reviewer_role?: 'NODAL_OFFICER' | 'MINISTRY_AUTHORITY';
  reviewer_note?: string;
  stage?: 'L1_REVIEW' | 'L2_REVIEW';
}) {
  const res = await fetch(`${API_BASE}/api/approvals/demo-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Approval action submission failed: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchDemoAuditTrail() {
  const res = await fetch(`${API_BASE}/api/audit/demo-trail`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch demo audit trail: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function verifyDemoAuditChain() {
  const res = await fetch(`${API_BASE}/api/audit/demo-verify`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to verify audit chain: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchDemoSummary() {
  const res = await fetch(`${API_BASE}/api/demo/summary`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch demo summary: HTTP ${res.status}`);
  }
  return await res.json();
}
