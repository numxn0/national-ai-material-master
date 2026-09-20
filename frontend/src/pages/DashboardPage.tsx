import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Database,
  FileSpreadsheet,
  GitCompare,
  IndianRupee,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react';
import { StatCard } from '@/components/ui/StatCard';
import { fetchAnalyticsSummary } from '@/services/api';
import type { AnalyticsSummaryResponse } from '@/types';

type RangeDays = 7 | 30 | 90;

const rangeOptions: RangeDays[] = [7, 30, 90];
const numberFormat = new Intl.NumberFormat('en-IN');
const currencyFormat = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

function formatAction(action: string) {
  return action
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ');
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function shortHash(hash: string) {
  if (!hash || hash.length <= 12) return hash || 'Not initialized';
  return `${hash.slice(0, 8)}...${hash.slice(-4)}`;
}

export const DashboardPage: React.FC = () => {
  const [summary, setSummary] = useState<AnalyticsSummaryResponse | null>(null);
  const [rangeDays, setRangeDays] = useState<RangeDays>(30);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = useCallback(async (days: RangeDays) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetchAnalyticsSummary(days);
      setSummary(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load production analytics');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics(rangeDays);
  }, [loadAnalytics, rangeDays]);

  const pendingApprovalCount = summary
    ? summary.pending_l1_count + summary.pending_l2_count + summary.needs_more_info_count
    : 0;

  const hasRecords = Boolean(
    summary &&
      (summary.total_source_materials > 0 ||
        summary.total_ingestion_batches > 0 ||
        summary.total_match_candidates > 0 ||
        summary.national_material_active_count > 0)
  );

  const cpseChartData = useMemo(
    () =>
      (summary?.cpse_breakdown ?? []).slice(0, 8).map((item) => ({
        name: item.cpse_name,
        materials: item.material_count,
        candidates: item.candidate_involvement_count,
      })),
    [summary]
  );

  const categoryChartData = useMemo(
    () =>
      (summary?.category_breakdown ?? []).slice(0, 8).map((item) => ({
        name: item.category,
        materials: item.material_count,
        candidates: item.candidate_involvement_count,
        activeCodes: item.active_national_material_count,
      })),
    [summary]
  );

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 mb-2">
              Production Analytics • Persisted Database
            </div>
            <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
              National AI Material Master
            </h2>
            <p className="text-sm text-gray-600 mt-1 max-w-2xl leading-relaxed">
              Live operational view of durable ingestion, matching, approvals, national-code registry,
              and audit-ledger health.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-2 shrink-0">
            <div className="inline-flex rounded-md border border-gray-200 bg-gray-50 p-1">
              {rangeOptions.map((days) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => setRangeDays(days)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded transition-colors ${
                    rangeDays === days
                      ? 'bg-white text-blue-700 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {days}d
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => loadAnalytics(rangeDays)}
              disabled={isLoading}
              className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-gray-300 bg-white text-gray-700 text-xs font-semibold hover:bg-gray-50 disabled:opacity-60 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <Link
              to="/upload"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-sm"
            >
              <UploadCloud className="w-4 h-4" />
              Upload Materials
            </Link>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <h3 className="text-sm font-bold text-red-900">Analytics unavailable</h3>
              <p className="text-sm text-red-700 break-words">{error}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => loadAnalytics(rangeDays)}
            className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-white border border-red-200 text-red-700 text-xs font-semibold hover:bg-red-100 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      )}

      {isLoading && !summary && (
        <div className="bg-white border border-gray-200 rounded-lg p-8 shadow-sm text-center">
          <RefreshCw className="w-6 h-6 text-blue-600 animate-spin mx-auto mb-3" />
          <p className="text-sm font-semibold text-gray-900">Loading production analytics</p>
          <p className="text-xs text-gray-500 mt-1">Reading persisted database metrics.</p>
        </div>
      )}

      {summary && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Materials"
              value={numberFormat.format(summary.total_source_materials)}
              subtitle={`${numberFormat.format(summary.total_ingestion_batches)} ingestion batches`}
              icon={<FileSpreadsheet className="w-4 h-4" />}
            />
            <StatCard
              title="Duplicate Candidates"
              value={numberFormat.format(summary.duplicate_candidate_count)}
              subtitle={`${numberFormat.format(summary.total_match_candidates)} candidate rows`}
              icon={<GitCompare className="w-4 h-4" />}
            />
            <StatCard
              title="Pending Approvals"
              value={numberFormat.format(pendingApprovalCount)}
              subtitle={`${summary.pending_l1_count} L1 • ${summary.pending_l2_count} L2 • ${summary.needs_more_info_count} info`}
              icon={<Clock className="w-4 h-4" />}
            />
            <StatCard
              title="Active National Codes"
              value={numberFormat.format(summary.national_material_active_count)}
              subtitle={`${summary.national_material_draft_count} drafts • ${summary.national_material_rejected_count} rejected`}
              icon={<CheckCircle className="w-4 h-4" />}
            />
          </div>

          {!hasRecords && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold text-blue-950">No production records yet</h3>
                <p className="text-sm text-blue-700 mt-1">
                  Upload a CSV to create durable source materials, then run matching and approvals.
                </p>
              </div>
              <Link
                to="/upload"
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors"
              >
                <UploadCloud className="w-4 h-4" />
                Start Upload
              </Link>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm min-w-0">
              <Database className="w-4 h-4 text-blue-600 mb-3" />
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Ingestion</p>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {numberFormat.format(summary.batches_completed)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                completed of {numberFormat.format(summary.total_ingestion_batches)} batches; {summary.batches_with_errors} with errors
              </p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm min-w-0">
              <ShieldCheck className="w-4 h-4 text-emerald-600 mb-3" />
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Mappings</p>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {numberFormat.format(summary.approved_mapping_count)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                approved mappings; {summary.rejected_mapping_count} rejected
              </p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm min-w-0">
              <IndianRupee className="w-4 h-4 text-amber-600 mb-3" />
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Approved Savings</p>
              <p className="text-xl font-bold text-gray-900 mt-1 break-words">
                {currencyFormat.format(summary.estimated_approved_savings_inr)}
              </p>
              <p className="text-xs text-gray-500 mt-1">estimated from approved cases</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm min-w-0">
              <ShieldCheck className="w-4 h-4 text-slate-700 mb-3" />
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Audit Chain</p>
              <p className="text-xl font-bold text-gray-900 mt-1">
                #{numberFormat.format(summary.audit_chain.last_sequence_number)}
              </p>
              <p className="text-xs text-gray-500 mt-1 break-all">
                {summary.audit_event_count} events • {shortHash(summary.audit_chain.last_hash)}
              </p>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Actual Procurement History</p>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {currencyFormat.format(summary.actual_procurement_spend_inr)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {summary.procurement_metric_source === 'ACTUAL_PROCUREMENT_HISTORY'
                  ? `${numberFormat.format(summary.actual_procurement_quantity)} units across ${summary.procurement_vendor_count} vendors`
                  : 'Import procurement history to replace this zero state with actual spend.'}
              </p>
            </div>
            <div className="text-xs text-gray-600">
              Approved-code spend: <strong>{currencyFormat.format(summary.approved_national_code_spend_inr)}</strong>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm min-w-0">
              <div className="mb-4">
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">CPSE Breakdown</h3>
                <p className="text-xs text-gray-500 mt-1">Material and duplicate-candidate involvement by source CPSE.</p>
              </div>
              <div className="h-64 min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cpseChartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={54} />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="materials" fill="#2563eb" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="candidates" fill="#0f766e" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm min-w-0">
              <div className="mb-4">
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Category Breakdown</h3>
                <p className="text-xs text-gray-500 mt-1">Persisted materials, candidates, and active national codes by category.</p>
              </div>
              <div className="h-64 min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categoryChartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={54} />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="materials" fill="#2563eb" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="candidates" fill="#0f766e" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="activeCodes" fill="#ca8a04" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm min-w-0">
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4">Recent Activity</h3>
              {summary.recent_activity.length === 0 ? (
                <p className="text-sm text-gray-500">No audit events have been recorded yet.</p>
              ) : (
                <div className="space-y-3">
                  {summary.recent_activity.map((event) => (
                    <div key={`${event.timestamp}-${event.action}-${event.entity_id}`} className="border-l-2 border-blue-200 pl-3 min-w-0">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                        <p className="text-sm font-semibold text-gray-900">{formatAction(event.action)}</p>
                        <span className="text-xs text-gray-500">{formatDateTime(event.timestamp)}</span>
                      </div>
                      <p className="text-xs text-gray-500 break-words">
                        {event.actor} • {event.entity_type} • {event.entity_id}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm min-w-0">
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4">Ingestion Timeline</h3>
              {summary.ingestion_timeline.length === 0 ? (
                <p className="text-sm text-gray-500">No ingestion batches in the selected range.</p>
              ) : (
                <div className="space-y-2">
                  {summary.ingestion_timeline.map((point) => (
                    <div
                      key={point.date}
                      className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-center rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-xs"
                    >
                      <span className="font-semibold text-gray-900">{point.date}</span>
                      <span className="text-gray-600">{point.batches_created} batches</span>
                      <span className="text-gray-600">{point.source_materials_processed} processed</span>
                      <span className="text-gray-600">{point.rejected_rows} rejected</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
