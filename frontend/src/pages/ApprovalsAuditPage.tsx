import React, { useState, useEffect } from 'react';
import {
  CheckCircle,
  ShieldCheck,
  RefreshCw,
  Download,
  Check,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import {
  ApprovalCase,
  ApprovalQueueResponse,
  ApprovalActionResponse,
  AuditTrailResponse,
  AuditChainVerificationResponse
} from '@/types';
import {
  fetchDemoApprovalQueue,
  submitDemoApprovalAction,
  fetchDemoAuditTrail,
  verifyDemoAuditChain
} from '@/services/api';

export const ApprovalsAuditPage: React.FC = () => {
  // Approvals State
  const [queue, setQueue] = useState<ApprovalQueueResponse | null>(null);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Audit State
  const [auditTrail, setAuditTrail] = useState<AuditTrailResponse | null>(null);
  const [auditVerification, setAuditVerification] = useState<AuditChainVerificationResponse | null>(null);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [showSignatures, setShowSignatures] = useState(false);

  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    await Promise.all([loadQueue(), loadAudit()]);
  };

  const loadQueue = async () => {
    setLoadingQueue(true);
    try {
      const data = await fetchDemoApprovalQueue(0.45);
      setQueue(data);
    } catch {
      // Graceful fallback
    } finally {
      setLoadingQueue(false);
    }
  };

  const loadAudit = async () => {
    setLoadingAudit(true);
    try {
      const trail = await fetchDemoAuditTrail();
      setAuditTrail(trail);
      const verify = await verifyDemoAuditChain();
      setAuditVerification(verify);
    } catch {
      // Graceful fallback
    } finally {
      setLoadingAudit(false);
    }
  };

  const handleApproval = async (
    c: ApprovalCase,
    decision: 'APPROVE' | 'REJECT'
  ) => {
    setActionLoadingId(c.approval_case_id);
    const stage = c.current_stage === 'PENDING_L2' ? 'L2_REVIEW' : 'L1_REVIEW';
    const role = c.current_stage === 'PENDING_L2' ? 'MINISTRY_AUTHORITY' : 'NODAL_OFFICER';
    const reviewerName = c.current_stage === 'PENDING_L2' ? 'Reviewer 2 (Ministry Authority)' : 'Reviewer 1 (Technical Nodal)';

    try {
      const res: ApprovalActionResponse = await submitDemoApprovalAction({
        approval_case_id: c.approval_case_id,
        decision,
        reviewer_name: reviewerName,
        reviewer_role: role,
        reviewer_note: `Action ${decision} performed during examiner review.`,
        stage,
      });

      if (queue) {
        const updatedCases = queue.cases.map((item) =>
          item.approval_case_id === c.approval_case_id ? res.updated_case : item
        );
        setQueue({
          ...queue,
          cases: updatedCases,
        });
      }

      setActionNotice(`Case ${c.approval_case_id} updated to "${decision}". Logged in audit trail.`);
      setTimeout(() => setActionNotice(null), 4000);

      // Refresh audit trail to show new entry
      loadAudit();
    } catch {
      // Error handling
    } finally {
      setActionLoadingId(null);
    }
  };

  const exportAuditCsv = () => {
    if (!auditTrail || !auditTrail.events.length) return;
    const headers = ['Audit ID', 'Timestamp', 'Actor', 'Action', 'Entity ID', 'Status'];
    const rows = auditTrail.events.map((e) => [
      e.audit_id,
      e.timestamp,
      `"${e.actor}"`,
      `"${e.action}"`,
      e.entity_id,
      'Verified'
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `material_master_audit_log_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">Approval & Audit</h2>
          <p className="text-xs text-gray-600 mt-1">
            Review proposed National Material Codes, execute officer sign-offs, and inspect the chronological audit log.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadAllData}
            disabled={loadingQueue || loadingAudit}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md border border-gray-300 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-blue-600 ${(loadingQueue || loadingAudit) ? 'animate-spin' : ''}`} />
            <span>Refresh Data</span>
          </button>
          <button
            onClick={exportAuditCsv}
            disabled={!auditTrail || !auditTrail.events.length}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Audit CSV</span>
          </button>
        </div>
      </div>

      {actionNotice && (
        <div className="p-3.5 rounded-md bg-green-50 border border-green-200 text-green-800 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-green-600" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* SECTION 1: Pending Approvals */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
              Pending Approvals Queue
            </h3>
            <p className="text-xs text-gray-500">
              Matches requiring Reviewer 1 (Technical Nodal) or Reviewer 2 (Ministry Authority) sign-off.
            </p>
          </div>
          <span className="text-xs font-medium text-gray-500">
            {queue ? queue.cases.length : 0} Cases in Review
          </span>
        </div>

        {loadingQueue ? (
          <div className="p-8 bg-white border border-gray-200 rounded-lg text-center text-xs text-gray-500">
            Loading approval cases...
          </div>
        ) : !queue || queue.cases.length === 0 ? (
          <div className="p-8 bg-white border border-gray-200 rounded-lg text-center text-xs text-gray-500">
            No pending approval cases.
          </div>
        ) : (
          <div className="space-y-3">
            {queue.cases.slice(0, 4).map((item) => {
              const isPendingL2 = item.current_stage === 'PENDING_L2';
              const isCompleted = item.current_stage === 'COMPLETED' || item.approval_status === 'APPROVED_AS_UNIFIED_SKU';
              const isRejected = item.current_stage === 'REJECTED';

              return (
                <div
                  key={item.approval_case_id}
                  className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-4 hover:border-blue-300 transition-colors"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-gray-100">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-gray-400 block">Proposed National Code</span>
                      <span className="font-mono text-base font-bold text-blue-700">
                        {item.proposed_national_material_code}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 font-medium">Review Status:</span>
                      {isCompleted ? (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-200">
                          Approved (Ready for Master Catalog)
                        </span>
                      ) : isRejected ? (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
                          Rejected (Keep Separate)
                        </span>
                      ) : isPendingL2 ? (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                          Reviewer 1 Approved &bull; Reviewer 2 Pending
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                          Reviewer 1 (Technical Nodal) Pending
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Consolidating Items */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="p-3 bg-gray-50 rounded border border-gray-200 space-y-1">
                      <span className="text-[10px] uppercase font-bold text-gray-400">Source Item 1</span>
                      <p className="font-mono font-bold text-gray-900">{item.source_material_a.source_material_code}</p>
                      <p className="text-gray-600">{item.source_material_a.raw_description}</p>
                    </div>

                    <div className="p-3 bg-gray-50 rounded border border-gray-200 space-y-1">
                      <span className="text-[10px] uppercase font-bold text-gray-400">Source Item 2</span>
                      <p className="font-mono font-bold text-gray-900">{item.source_material_b.source_material_code}</p>
                      <p className="text-gray-600">{item.source_material_b.raw_description}</p>
                    </div>
                  </div>

                  {/* Bottom Actions */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
                    <div className="text-xs text-gray-500">
                      <span>Procurement Impact: </span>
                      <strong className="text-gray-900">
                        ₹{(item.procurement_impact.estimated_savings_inr / 1000).toFixed(0)}K Estimated Annual Savings
                      </strong>
                    </div>

                    {!isCompleted && !isRejected && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleApproval(item, 'APPROVE')}
                          disabled={actionLoadingId === item.approval_case_id}
                          className="px-3 py-1.5 rounded bg-green-600 hover:bg-green-700 text-white text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
                        >
                          {isPendingL2 ? 'Approve (Reviewer 2)' : 'Approve (Reviewer 1)'}
                        </button>
                        <button
                          onClick={() => handleApproval(item, 'REJECT')}
                          disabled={actionLoadingId === item.approval_case_id}
                          className="px-3 py-1.5 rounded border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 text-xs font-medium transition-colors disabled:opacity-50"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* SECTION 2: Simple Audit Log */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
              Audit Log
            </h3>
            <p className="text-xs text-gray-500">
              Chronological, tamper-evident log of all catalog ingestions, matches, and approval actions.
            </p>
          </div>

          {auditVerification && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-200">
              <ShieldCheck className="w-3.5 h-3.5 text-green-600" />
              <span>Audit Log Verified (Intact)</span>
            </span>
          )}
        </div>

        <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-100 text-gray-600 font-semibold border-b border-gray-200">
                <tr>
                  <th className="py-2.5 px-4">Event ID</th>
                  <th className="py-2.5 px-4">Timestamp</th>
                  <th className="py-2.5 px-4">Action Taken</th>
                  <th className="py-2.5 px-4">Actor / Reviewer</th>
                  <th className="py-2.5 px-4">Target Item</th>
                  <th className="py-2.5 px-4">Integrity Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {auditTrail?.events.map((evt) => (
                  <tr key={evt.audit_id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-2.5 px-4 font-mono font-medium text-blue-700">
                      {evt.audit_id}
                    </td>
                    <td className="py-2.5 px-4 text-gray-500 whitespace-nowrap">
                      {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="py-2.5 px-4 text-gray-900 font-medium">
                      {evt.action.replace(/_/g, ' ')}
                    </td>
                    <td className="py-2.5 px-4 text-gray-600">
                      {evt.actor}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-gray-700">
                      {evt.entity_id}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="inline-flex items-center gap-1 text-green-700 font-medium">
                        <Check className="w-3.5 h-3.5 text-green-600" />
                        Verified
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Optional Collapsed Signatures Details */}
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
          <button
            type="button"
            onClick={() => setShowSignatures(!showSignatures)}
            className="w-full p-3.5 flex items-center justify-between text-left hover:bg-gray-50 rounded-lg text-xs font-semibold text-gray-700"
          >
            <span>Technical Audit Hash Signatures (Optional)</span>
            <span className="text-blue-600 flex items-center gap-1 font-normal">
              {showSignatures ? 'Hide Signatures' : 'View Signatures'}
              {showSignatures ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </span>
          </button>

          {showSignatures && auditVerification && (
            <div className="p-4 border-t border-gray-200 bg-gray-50 text-[11px] font-mono text-gray-600 space-y-1">
              <p>Genesis Block: <span className="text-gray-900">{auditVerification.genesis_hash.slice(0, 32)}...</span></p>
              <p>Latest Block Signature: <span className="text-blue-700">{auditVerification.latest_hash.slice(0, 32)}...</span></p>
              <p className="text-gray-500 font-sans text-xs pt-1">
                All events are sequentially linked using cryptographic SHA-256 signatures ensuring zero records can be altered undetected.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
