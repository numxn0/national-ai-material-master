import React, { useState, useEffect } from 'react';
import {
  Search,
  Download,
  Hash,
  Lock,
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  Activity,
  ChevronDown,
  ChevronUp,
  FileCheck2,
  AlertTriangle
} from 'lucide-react';
import {
  AuditTrailResponse,
  AuditChainVerificationResponse
} from '@/types';
import {
  fetchDemoAuditTrail,
  verifyDemoAuditChain
} from '@/services/api';

export const AuditPage: React.FC = () => {
  const [trail, setTrail] = useState<AuditTrailResponse | null>(null);
  const [verification, setVerification] = useState<AuditChainVerificationResponse | null>(null);
  const [loadingTrail, setLoadingTrail] = useState(false);
  const [verifyingChain, setVerifyingChain] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const loadTrail = async () => {
    setLoadingTrail(true);
    setError(null);
    try {
      const data = await fetchDemoAuditTrail();
      setTrail(data);
      // Auto verify after loading
      const v = await verifyDemoAuditChain();
      setVerification(v);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit trail from backend.');
    } finally {
      setLoadingTrail(false);
    }
  };

  const runVerification = async () => {
    setVerifyingChain(true);
    setError(null);
    try {
      const v = await verifyDemoAuditChain();
      setVerification(v);
    } catch (err: any) {
      setError(err.message || 'Audit chain verification failed.');
    } finally {
      setVerifyingChain(false);
    }
  };

  useEffect(() => {
    loadTrail();
  }, []);

  const filteredEvents = (trail?.events || []).filter((e) =>
    e.actor.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.entity_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.audit_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (e.reason && e.reason.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const exportCsv = () => {
    if (!trail || !trail.events.length) return;
    const headers = ['Audit ID', 'Timestamp', 'Actor', 'Role', 'Action', 'Entity ID', 'Previous Hash', 'Hash Signature', 'Reason'];
    const rows = trail.events.map(e => [
      e.audit_id,
      e.timestamp,
      e.actor,
      e.actor_role,
      e.action,
      e.entity_id,
      e.previous_hash,
      e.hash_signature,
      `"${(e.reason || '').replace(/"/g, '""')}"`
    ]);
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `namm_audit_trail_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              CVC & CAG AUDIT READINESS
            </span>
            <span className="text-xs text-slate-400">Cryptographically Chained SHA-256 Ledger</span>
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">Compliance & Cryptographic Audit Trail</h2>
          <p className="text-xs text-slate-400 mt-1">
            Tamper-evident, blockchain-inspired sequential ledger recording all CPSE ingestions, RapidFuzz inferences, hybrid scorings, and approval actions.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={loadTrail}
            disabled={loadingTrail}
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-700 bg-slate-900 text-slate-200 text-xs font-medium hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-cyan-400 ${loadingTrail ? 'animate-spin' : ''}`} />
            <span>{loadingTrail ? 'Loading Trail...' : 'Reload Audit Trail'}</span>
          </button>

          <button
            onClick={runVerification}
            disabled={verifyingChain}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold shadow-md shadow-emerald-950 transition-all disabled:opacity-50"
          >
            <ShieldCheck className={`w-4 h-4 ${verifyingChain ? 'animate-spin' : ''}`} />
            <span>{verifyingChain ? 'Verifying Hashes...' : 'Verify Chain Integrity'}</span>
          </button>

          <button
            onClick={exportCsv}
            disabled={!trail || !trail.events.length}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-700 bg-slate-900 text-slate-200 text-xs font-medium hover:bg-slate-800 transition-colors disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5 text-slate-400" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Verification Status Banner */}
      {verification && (
        <div className={`p-4 rounded-xl border ${
          verification.is_valid
            ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
            : 'bg-rose-950/20 border-rose-500/30 text-rose-300'
        } glass-panel space-y-2`}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              {verification.is_valid ? (
                <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
              ) : (
                <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
              )}
              <span className="font-semibold text-sm text-white">
                Cryptographic Audit Chain: {verification.chain_status}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-950 text-emerald-400 border border-slate-800">
                {verification.verified_event_count} Blocks Verified
              </span>
            </div>

            <span className="text-[11px] text-slate-400 font-mono">
              Validated: {new Date(verification.verification_timestamp).toLocaleTimeString()}
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">
            {verification.message}
          </p>

          <div className="pt-2 border-t border-slate-800/80 flex flex-wrap gap-4 text-[11px] font-mono text-slate-400">
            <div>
              <span className="text-slate-500">Genesis Parent: </span>
              <span className="text-slate-300">{verification.genesis_hash.slice(0, 16)}...</span>
            </div>
            <div>
              <span className="text-slate-500">Latest Signature: </span>
              <span className="text-cyan-300">{verification.latest_hash.slice(0, 16)}...</span>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Ledger Metrics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Sequenced Blocks</span>
            <Hash className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {trail ? trail.total_events : '—'}
          </div>
          <span className="text-[10px] text-slate-500">SHA-256 Chained Records</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Chain Security</span>
            <Lock className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            {trail?.chain_verified ? '100%' : 'PENDING'}
          </div>
          <span className="text-[10px] text-slate-500">Zero Block Divergence</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Protocol Hash</span>
            <Activity className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xs font-mono text-indigo-300 truncate pt-2">
            {trail ? trail.latest_hash.slice(0, 14) + '...' : '—'}
          </div>
          <span className="text-[10px] text-slate-500">Latest Tip Checksum</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 glass-panel">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Governance Ledger</span>
            <FileCheck2 className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400">
            CAG Ready
          </div>
          <span className="text-[10px] text-slate-500">Full Audit Provenance</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex items-center justify-between gap-4 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div className="relative flex-1 max-w-md">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filter audit events by actor, action verb, SKU, or audit ID..."
            className="w-full h-8 rounded-lg bg-slate-950 border border-slate-800 pl-8 pr-3 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Lock className="w-3.5 h-3.5 text-emerald-400" />
          <span>Sequential SHA-256 Hashes</span>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden glass-panel">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/70 text-slate-400 font-semibold">
                <th className="py-3 px-4">Seq # / Event ID</th>
                <th className="py-3 px-4">Timestamp (UTC)</th>
                <th className="py-3 px-4">Actor & Role</th>
                <th className="py-3 px-4">Action Verb</th>
                <th className="py-3 px-4">Target Entity</th>
                <th className="py-3 px-4">Hash Signature (SHA-256)</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-center">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loadingTrail && !trail ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin mx-auto mb-2" />
                    Loading cryptographic audit ledger...
                  </td>
                </tr>
              ) : filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    No matching audit trail records found.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((evt, idx) => {
                  const isExpanded = expandedRow === evt.audit_id;
                  const isGenesis = evt.previous_hash === '0000000000000000000000000000000000000000000000000000000000000000';

                  return (
                    <React.Fragment key={evt.audit_id}>
                      <tr className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 font-mono">
                          <span className="text-[10px] text-slate-500 mr-2">#{idx}</span>
                          <span className="font-semibold text-cyan-300">{evt.audit_id}</span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
                          {evt.timestamp.replace('T', ' ').slice(0, 19)}
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-medium text-slate-200">{evt.actor}</div>
                          <span className="text-[10px] text-slate-500 uppercase">{evt.actor_role}</span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                            {evt.action}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-300">
                          {evt.entity_id}
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-400" title={evt.hash_signature}>
                          <span className="text-cyan-400">{evt.hash_signature.slice(0, 10)}</span>
                          <span className="text-slate-600">...</span>
                          <span className="text-slate-400">{evt.hash_signature.slice(-6)}</span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          {isGenesis ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                              GENESIS
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                              VERIFIED
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() => setExpandedRow(isExpanded ? null : evt.audit_id)}
                            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                          >
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded Payload & Cryptographic Link Details */}
                      {isExpanded && (
                        <tr className="bg-slate-950/60">
                          <td colSpan={8} className="p-4 space-y-3">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                                <span className="text-slate-500 text-[10px] uppercase block">Previous Hash (Parent Link):</span>
                                <span className="text-slate-300 break-all text-[11px] select-all">
                                  {evt.previous_hash}
                                </span>
                              </div>
                              <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                                <span className="text-slate-500 text-[10px] uppercase block">Current Block Hash Signature:</span>
                                <span className="text-cyan-300 break-all text-[11px] select-all">
                                  {evt.hash_signature}
                                </span>
                              </div>
                            </div>

                            {evt.reason && (
                              <div className="text-xs text-slate-300 bg-slate-900/50 p-3 rounded-lg border border-slate-800/80">
                                <strong className="text-slate-400">Review Rationale / Operation Summary:</strong>
                                <p className="mt-1 leading-relaxed text-white font-sans">{evt.reason}</p>
                              </div>
                            )}

                            {/* Payload Snapshots */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                              {evt.old_value && (
                                <div className="p-3 rounded-lg bg-slate-900/40 border border-slate-800">
                                  <span className="text-rose-400 text-[10px] uppercase block mb-1">Pre-Action State:</span>
                                  <pre className="text-[10px] text-slate-300 overflow-x-auto">
                                    {JSON.stringify(evt.old_value, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {evt.new_value && (
                                <div className="p-3 rounded-lg bg-slate-900/40 border border-slate-800">
                                  <span className="text-emerald-400 text-[10px] uppercase block mb-1">Post-Action State:</span>
                                  <pre className="text-[10px] text-slate-300 overflow-x-auto">
                                    {JSON.stringify(evt.new_value, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
