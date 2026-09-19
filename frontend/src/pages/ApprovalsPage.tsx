import React, { useState, useEffect } from 'react';
import {
  CheckSquare,
  CheckCircle,
  XCircle,
  AlertCircle,
  Shield,
  Layers,
  FileCode,
  Building2,
  Sparkles,
  RefreshCw,
  Clock,
  UserCheck,
  HelpCircle
} from 'lucide-react';
import { StatusBadge } from '@/components/ui/StatusBadge';
import {
  ApprovalCase,
  ApprovalQueueResponse,
  ApprovalActionResponse
} from '@/types';
import {
  fetchDemoApprovalQueue,
  submitDemoApprovalAction
} from '@/services/api';

export const ApprovalsPage: React.FC = () => {
  const [queue, setQueue] = useState<ApprovalQueueResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [notesState, setNotesState] = useState<Record<string, string>>({});
  const [roleState, setRoleState] = useState<Record<string, 'NODAL_OFFICER' | 'MINISTRY_AUTHORITY'>>({});

  const loadQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDemoApprovalQueue(0.45);
      setQueue(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load approval queue from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleAction = async (
    approvalCase: ApprovalCase,
    decision: 'APPROVE' | 'REJECT' | 'NEEDS_MORE_INFO'
  ) => {
    const caseId = approvalCase.approval_case_id;
    setActionLoadingId(caseId);
    setError(null);

    const userRole = roleState[caseId] || (approvalCase.current_stage === 'PENDING_L2' ? 'MINISTRY_AUTHORITY' : 'NODAL_OFFICER');
    const reviewerName = userRole === 'MINISTRY_AUTHORITY' ? 'Director General Verma (DPE)' : 'Nodal Officer Sharma (BHEL)';
    const stage = userRole === 'MINISTRY_AUTHORITY' ? 'L2_REVIEW' : 'L1_REVIEW';
    const note = notesState[caseId] || `Action ${decision} submitted via governance dashboard.`;

    try {
      const res: ApprovalActionResponse = await submitDemoApprovalAction({
        approval_case_id: caseId,
        decision,
        reviewer_name: reviewerName,
        reviewer_role: userRole,
        reviewer_note: note,
        stage,
      });

      // Update local state
      if (queue) {
        const updatedCases = queue.cases.map((c) =>
          c.approval_case_id === caseId ? res.updated_case : c
        );
        const p1 = updatedCases.filter((c) => c.current_stage === 'PENDING_L1').length;
        const p2 = updatedCases.filter((c) => c.current_stage === 'PENDING_L2').length;
        const comp = updatedCases.filter((c) => c.current_stage === 'COMPLETED' || c.current_stage === 'REJECTED').length;

        setQueue({
          ...queue,
          cases: updatedCases,
          pending_l1_count: p1,
          pending_l2_count: p2,
          completed_count: comp,
        });
      }

      setActionMessage(
        `Case ${caseId} updated: [${decision}]. Cryptographic SHA-256 event generated (${res.generated_audit_event.audit_id}). Not persisted (Demo mode).`
      );
      setTimeout(() => setActionMessage(null), 7000);
    } catch (err: any) {
      setError(err.message || 'Approval action submission failed.');
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              DUAL-TIER GOVERNANCE WORKFLOW
            </span>
            <span className="text-xs text-slate-400">Technical Nodal Officer & Ministry Ratification</span>
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">Material Master Approvals & Alias Ratification</h2>
          <p className="text-xs text-slate-400 mt-1">
            Review candidate duplicate pairs, evaluate procurement impact, verify national code proposals, and execute L1/L2 governance decisions.
          </p>
        </div>

        {/* Refresh / Load Button */}
        <div className="flex items-center gap-2">
          <button
            onClick={loadQueue}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-semibold shadow-lg shadow-cyan-900/30 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Processing Pipeline...' : 'Reload Demo Approval Queue'}</span>
          </button>
        </div>
      </div>

      {/* Demo Disclosure Banner */}
      <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs flex items-center justify-between gap-3 glass-panel">
        <div className="flex items-center gap-2 text-slate-300">
          <Shield className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>
            <strong>Demonstration Governance Mode:</strong> Approvals are evaluated in-memory against sample CPSE catalogs. Each action creates a cryptographically signed SHA-256 audit entry.
          </span>
        </div>
        <span className="px-2.5 py-1 rounded bg-slate-950 text-[10px] font-mono text-cyan-300 border border-slate-800 whitespace-nowrap">
          DB Persisted: False
        </span>
      </div>

      {actionMessage && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 animate-fadeIn">
          <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Workflow State Statistics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Total Cases</span>
            <Layers className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {queue ? queue.total_cases : '—'}
          </div>
          <span className="text-[10px] text-slate-500">Sample Candidate Pairs</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Pending L1 Review</span>
            <UserCheck className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400">
            {queue ? queue.pending_l1_count : '—'}
          </div>
          <span className="text-[10px] text-slate-500">Technical Nodal Verification</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Pending L2 Review</span>
            <Clock className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-indigo-400">
            {queue ? queue.pending_l2_count : '—'}
          </div>
          <span className="text-[10px] text-slate-500">Ministry Authority Ratification</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Completed / Ratified</span>
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            {queue ? queue.completed_count : '—'}
          </div>
          <span className="text-[10px] text-slate-500">Published to Master SKU</span>
        </div>
      </div>

      {/* Approval Cases List */}
      <div className="space-y-5">
        {loading && !queue ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center glass-panel">
            <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin mx-auto mb-3" />
            <p className="text-sm font-semibold text-slate-300">Generating Demo Approval Queue...</p>
            <p className="text-xs text-slate-500 mt-1">Executing RapidFuzz candidate pruning, hybrid scoring, and national code proposals.</p>
          </div>
        ) : !queue || queue.cases.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center glass-panel">
            <CheckSquare className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <h4 className="text-sm font-semibold text-slate-300">No Pending Approval Cases</h4>
            <p className="text-xs text-slate-500 mt-1">All candidate duplicates have been reviewed or no candidates met the threshold.</p>
          </div>
        ) : (
          queue.cases.map((c) => {
            const isActing = actionLoadingId === c.approval_case_id;
            const currentRole = roleState[c.approval_case_id] || (c.current_stage === 'PENDING_L2' ? 'MINISTRY_AUTHORITY' : 'NODAL_OFFICER');

            return (
              <div
                key={c.approval_case_id}
                className={`rounded-xl border ${
                  c.current_stage === 'COMPLETED'
                    ? 'border-emerald-500/30 bg-emerald-950/10'
                    : c.current_stage === 'REJECTED'
                    ? 'border-rose-500/30 bg-rose-950/10'
                    : 'border-slate-800 bg-slate-900/60'
                } p-5 glass-panel transition-all space-y-4`}
              >
                {/* Case Top Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-slate-950 text-cyan-400 border border-slate-800">
                      {c.approval_case_id}
                    </span>
                    <StatusBadge status={c.current_stage} />
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      Tier: {c.required_approval_level}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300">
                      Status: {c.approval_status}
                    </span>
                  </div>

                  {/* Dual Scores */}
                  <div className="flex items-center gap-3 text-xs">
                    <div className="text-right">
                      <span className="text-[10px] text-slate-500 block">Hybrid Duplicate Score</span>
                      <span className={`font-mono font-bold ${
                        c.hybrid_score >= 0.85
                          ? 'text-emerald-400'
                          : c.hybrid_score >= 0.65
                          ? 'text-amber-400'
                          : 'text-rose-400'
                      }`}>
                        {(c.hybrid_score * 100).toFixed(1)}% ({c.hybrid_classification})
                      </span>
                    </div>
                  </div>
                </div>

                {/* CPSE Material Pair Comparison Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-950/50 p-3.5 rounded-xl border border-slate-800/80">
                  {/* Item A */}
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 font-semibold text-cyan-300">
                        <Building2 className="w-3.5 h-3.5" />
                        {c.source_material_a.source_cpse}
                      </span>
                      <span className="font-mono text-[11px] text-slate-400">
                        {c.source_material_a.source_material_code}
                      </span>
                    </div>
                    <p className="font-medium text-white text-xs leading-relaxed">
                      {c.source_material_a.standard_description}
                    </p>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400">
                      <span>Category: {c.source_material_a.category}</span>
                      <span>•</span>
                      <span>UOM: {c.source_material_a.uom}</span>
                    </div>
                  </div>

                  {/* Item B */}
                  <div className="space-y-1 text-xs md:border-l md:border-slate-800 md:pl-4">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 font-semibold text-indigo-300">
                        <Building2 className="w-3.5 h-3.5" />
                        {c.source_material_b.source_cpse}
                      </span>
                      <span className="font-mono text-[11px] text-slate-400">
                        {c.source_material_b.source_material_code}
                      </span>
                    </div>
                    <p className="font-medium text-white text-xs leading-relaxed">
                      {c.source_material_b.standard_description}
                    </p>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400">
                      <span>Category: {c.source_material_b.category}</span>
                      <span>•</span>
                      <span>UOM: {c.source_material_b.uom}</span>
                    </div>
                  </div>
                </div>

                {/* Proposed National Material Code & Catalog Alias */}
                <div className="p-3.5 rounded-xl bg-gradient-to-r from-cyan-950/30 to-indigo-950/30 border border-cyan-500/20 text-xs space-y-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <FileCode className="w-4 h-4 text-cyan-400" />
                      <span className="text-slate-400 font-medium">Proposed National Material Master SKU:</span>
                      <span className="px-2.5 py-0.5 rounded bg-cyan-950 text-cyan-300 font-mono font-bold text-xs border border-cyan-700/50">
                        {c.proposed_national_material_code}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 self-start sm:self-auto">
                      Mapping: <strong>{c.mapping_preview.mapping_type}</strong>
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-300">
                    Proposed Canonical Nomenclature: <strong className="text-white">{c.proposed_standard_description}</strong>
                  </div>
                </div>

                {/* Procurement Impact & Estimated Savings */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-950/40 p-3 rounded-xl border border-slate-800/60 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 block">Annual Spend Overlap</span>
                    <span className="font-mono text-slate-200 font-semibold">
                      ₹{c.procurement_impact.estimated_annual_spend_overlap.toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">Harmonization Savings</span>
                    <span className="font-mono text-emerald-400 font-semibold">
                      {c.procurement_impact.standardization_savings_percent}%
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">Est. Annual Monetary Gain</span>
                    <span className="font-mono text-emerald-400 font-bold">
                      ₹{c.procurement_impact.estimated_savings_inr.toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">Procurement Risk</span>
                    <StatusBadge status={c.procurement_impact.procurement_risk_level} />
                  </div>
                </div>

                {/* AI Rationale Summary */}
                <div className="text-xs text-slate-300 bg-slate-950/30 p-2.5 rounded-lg border border-slate-800/50 flex items-start gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                  <span className="text-[11px] leading-relaxed">
                    <strong>AI Review Rationale:</strong> {c.explanation_summary}
                  </span>
                </div>

                {/* Multi-Tier History Log */}
                <div className="border-t border-slate-800/60 pt-3 flex flex-wrap gap-4 text-[11px] text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                    <span>L1 Nodal Officer:</span>
                    {c.l1_decision ? (
                      <span className="text-slate-200 font-semibold">
                        {c.l1_reviewer} ({c.l1_decision})
                      </span>
                    ) : (
                      <span className="text-slate-500 italic">Pending Review</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                    <span>L2 Ministry Authority:</span>
                    {c.l2_decision ? (
                      <span className="text-slate-200 font-semibold">
                        {c.l2_reviewer} ({c.l2_decision})
                      </span>
                    ) : (
                      <span className="text-slate-500 italic">
                        {c.current_stage === 'PENDING_L2' ? 'Awaiting Ratification' : 'Not Initiated'}
                      </span>
                    )}
                  </div>
                </div>

                {/* Interactive Governance Controls */}
                {c.current_stage !== 'COMPLETED' && c.current_stage !== 'REJECTED' && (
                  <div className="border-t border-slate-800/80 pt-3 space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-slate-400 text-[11px]">Acting As:</span>
                        <select
                          value={currentRole}
                          onChange={(e) => setRoleState({
                            ...roleState,
                            [c.approval_case_id]: e.target.value as any
                          })}
                          className="bg-slate-950 border border-slate-800 text-cyan-300 text-xs rounded px-2 py-1 font-medium focus:outline-none focus:border-cyan-500"
                        >
                          <option value="NODAL_OFFICER">Technical Nodal Officer (L1)</option>
                          <option value="MINISTRY_AUTHORITY">Ministry Authority / DPE (L2)</option>
                        </select>
                      </div>

                      <span className="text-[11px] text-slate-500">
                        {currentRole === 'NODAL_OFFICER'
                          ? 'Verifies functional tolerance & spec alignment'
                          : 'Ratifies master SKU across enterprise registries'}
                      </span>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-2">
                      <input
                        type="text"
                        placeholder="Add technical review remarks or drawing justification..."
                        value={notesState[c.approval_case_id] || ''}
                        onChange={(e) => setNotesState({
                          ...notesState,
                          [c.approval_case_id]: e.target.value
                        })}
                        className="flex-1 h-8 rounded-lg bg-slate-950 border border-slate-800 px-3 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
                      />

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => handleAction(c, 'NEEDS_MORE_INFO')}
                          disabled={isActing}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-amber-300 text-xs font-medium transition-colors disabled:opacity-50"
                        >
                          <HelpCircle className="w-3.5 h-3.5" />
                          <span>Request Info</span>
                        </button>

                        <button
                          onClick={() => handleAction(c, 'REJECT')}
                          disabled={isActing}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-rose-400 text-xs font-medium transition-colors disabled:opacity-50"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Reject (Distinct)</span>
                        </button>

                        <button
                          onClick={() => handleAction(c, 'APPROVE')}
                          disabled={isActing}
                          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold shadow-md shadow-emerald-950 transition-all disabled:opacity-50"
                        >
                          {isActing ? (
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <CheckCircle className="w-3.5 h-3.5" />
                          )}
                          <span>
                            {c.current_stage === 'PENDING_L2' || currentRole === 'MINISTRY_AUTHORITY'
                              ? 'Ratify to Master Catalog'
                              : 'Approve & Forward to L2'}
                          </span>
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
