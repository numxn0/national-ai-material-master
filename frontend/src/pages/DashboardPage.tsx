import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  UploadCloud,
  GitCompare,
  CheckSquare,
  Sparkles,
  ArrowRight,
  FileSpreadsheet,
  CheckCircle,
  Clock
} from 'lucide-react';
import { StatCard } from '@/components/ui/StatCard';
import { fetchDemoSummary } from '@/services/api';
import { DemoSummaryResponse } from '@/types';

export const DashboardPage: React.FC = () => {
  const [summary, setSummary] = useState<DemoSummaryResponse | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const res = await fetchDemoSummary();
        setSummary(res);
      } catch {
        // Fallback gracefully if backend unavailable
      }
    };
    loadData();
  }, []);

  const flowSteps = [
    {
      step: '1',
      title: 'Upload',
      desc: 'Ingest raw material records from various CPSE catalogs (CSV).',
      link: '/upload',
      icon: UploadCloud,
    },
    {
      step: '2',
      title: 'Standardize',
      desc: 'Clean descriptions, standardize units (UOM), and extract specifications.',
      link: '/upload',
      icon: Sparkles,
    },
    {
      step: '3',
      title: 'Match',
      desc: 'Detect duplicate items across organizations with confidence scores.',
      link: '/matching',
      icon: GitCompare,
    },
    {
      step: '4',
      title: 'Approve',
      desc: 'Human-in-the-loop review by technical nodal officers.',
      link: '/approvals',
      icon: CheckSquare,
    },
    {
      step: '5',
      title: 'National Code',
      desc: 'Generate unified master material code and record in audit log.',
      link: '/approvals',
      icon: CheckCircle,
    },
  ];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Simple Clean Header Banner */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 mb-2">
              Govt. of India • Central Public Sector Enterprises (CPSEs)
            </div>
            <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
              National AI Material Master
            </h2>
            <p className="text-sm text-gray-600 mt-1 max-w-2xl leading-relaxed">
              Centralized catalog standardization and duplicate detection across Indian PSUs (ONGC, IOCL, BHEL, NTPC, Railways). Eliminates redundant inventory, unifies conflicting item descriptions, and creates a single National Material Code.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-sm"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Upload Materials</span>
            </Link>
            <Link
              to="/matching"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-gray-300 bg-white text-gray-700 text-xs font-semibold hover:bg-gray-50 transition-colors"
            >
              <span>Review Duplicates</span>
              <ArrowRight className="w-4 h-4 text-gray-400" />
            </Link>
          </div>
        </div>
      </div>

      {/* 4 Simple Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Materials Uploaded"
          value={summary ? summary.sample_material_count : 10}
          subtitle="Items from CPSE catalogs"
          icon={<FileSpreadsheet className="w-4 h-4" />}
        />
        <StatCard
          title="Duplicate Candidates"
          value={summary ? summary.candidate_count : 6}
          subtitle="Potential matches detected"
          icon={<GitCompare className="w-4 h-4" />}
        />
        <StatCard
          title="Pending Review"
          value={summary ? (summary.pending_l1_count + summary.pending_l2_count) : 3}
          subtitle="Cases awaiting approval"
          icon={<Clock className="w-4 h-4" />}
        />
        <StatCard
          title="National Codes Proposed"
          value={summary ? summary.high_confidence_match_count : 4}
          subtitle="Unified master codes ready"
          icon={<CheckCircle className="w-4 h-4" />}
        />
      </div>

      {/* Simple 5-Step Flow Diagram */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-1">
          How It Works (System Workflow)
        </h3>
        <p className="text-xs text-gray-500 mb-6">
          A transparent 5-step process from messy procurement data to an approved National Material Code.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
          {flowSteps.map((step) => {
            const Icon = step.icon;
            return (
              <Link
                key={step.step}
                to={step.link}
                className="p-4 rounded-lg border border-gray-200 bg-gray-50 hover:bg-white hover:border-blue-300 hover:shadow-sm transition-all group"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center">
                    {step.step}
                  </span>
                  <Icon className="w-4 h-4 text-gray-400 group-hover:text-blue-600 transition-colors" />
                </div>
                <h4 className="text-sm font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
                  {step.title}
                </h4>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                  {step.desc}
                </p>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link
          to="/upload"
          className="p-5 bg-white border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-sm transition-all group"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-blue-600">Step 1</span>
            <ArrowRight className="w-4 h-4 text-gray-400 group-hover:translate-x-1 transition-transform" />
          </div>
          <h4 className="text-base font-bold text-gray-900">Upload Material Data</h4>
          <p className="text-xs text-gray-500 mt-1">
            Upload CPSE spreadsheets or preview bundled sample data from Railways, Coal India, ONGC, and BHEL.
          </p>
        </Link>

        <Link
          to="/matching"
          className="p-5 bg-white border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-sm transition-all group"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-blue-600">Step 2</span>
            <ArrowRight className="w-4 h-4 text-gray-400 group-hover:translate-x-1 transition-transform" />
          </div>
          <h4 className="text-base font-bold text-gray-900">Duplicate Review</h4>
          <p className="text-xs text-gray-500 mt-1">
            Compare candidate pairs side-by-side with match confidence and clear, human-readable reasons.
          </p>
        </Link>

        <Link
          to="/approvals"
          className="p-5 bg-white border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-sm transition-all group"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-blue-600">Step 3</span>
            <ArrowRight className="w-4 h-4 text-gray-400 group-hover:translate-x-1 transition-transform" />
          </div>
          <h4 className="text-base font-bold text-gray-900">Approval & Audit Log</h4>
          <p className="text-xs text-gray-500 mt-1">
            Review proposed National Material Codes, execute officer approvals, and inspect the chronological audit log.
          </p>
        </Link>
      </div>
    </div>
  );
};
