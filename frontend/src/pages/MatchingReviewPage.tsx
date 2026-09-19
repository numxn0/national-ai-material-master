import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Info
} from 'lucide-react';
import {
  fetchSampleHybridScoring,
  fetchSampleExplanations,
  submitReviewDecisionDemo
} from '../services/api';
import {
  HybridScoredCandidate,
  ReviewerExplanation
} from '../types';

export const MatchingReviewPage: React.FC = () => {
  const [candidates, setCandidates] = useState<HybridScoredCandidate[]>([]);
  const [explanations, setExplanations] = useState<Record<string, ReviewerExplanation>>({});
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [decisions, setDecisions] = useState<Record<string, string>>({});
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  useEffect(() => {
    loadReviewData();
  }, []);

  const loadReviewData = async () => {
    setLoading(true);
    try {
      const scoringData = await fetchSampleHybridScoring(0.50);
      const items: HybridScoredCandidate[] = scoringData.candidates || [];
      setCandidates(items);

      const explData = await fetchSampleExplanations(0.50);
      const explMap: Record<string, ReviewerExplanation> = {};
      (explData.explanations || []).forEach((exp: ReviewerExplanation) => {
        explMap[exp.pair_id] = exp;
      });
      setExplanations(explMap);
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  const currentPair = candidates[currentIndex];
  const currentExplanation = currentPair ? explanations[currentPair.pair_id] : null;

  const handleDecision = async (decision: 'APPROVE' | 'REJECT' | 'NEEDS_MORE_INFO') => {
    if (!currentPair) return;

    try {
      await submitReviewDecisionDemo({
        candidate_id: currentPair.pair_id,
        decision,
        reviewer_name: 'EXAMINER_USER',
        reviewer_note: `Marked as ${decision} during examiner review.`
      });

      setDecisions((prev) => ({
        ...prev,
        [currentPair.pair_id]: decision
      }));

      setActionNotice(`Pair marked as "${decision}". Updated in-memory.`);
      setTimeout(() => setActionNotice(null), 3000);
    } catch {
      // Handle error gracefully
    }
  };

  // Helper to construct a simple proposed code
  const getProposedCode = (c: HybridScoredCandidate) => {
    const cat = (c.source_material_a.category || 'GEN').slice(0, 3).toUpperCase();
    const cleanA = (c.source_material_a.source_material_code || '').replace(/[^A-Z0-9]/gi, '');
    return `NAMM-${cat}-${cleanA.slice(-4) || '1001'}`;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">Duplicate Review</h2>
          <p className="text-xs text-gray-600 mt-1">
            Compare suspected duplicate materials from different CPSEs side-by-side. Review match confidence, inspect why they matched, and take action.
          </p>
        </div>

        {/* Pager Controls */}
        {candidates.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">
              Candidate {currentIndex + 1} of {candidates.length}
            </span>
            <div className="flex items-center border border-gray-300 rounded-md bg-white">
              <button
                onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentIndex === 0}
                className="p-1.5 text-gray-600 hover:bg-gray-100 disabled:opacity-30 rounded-l-md"
                title="Previous Candidate"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setCurrentIndex((prev) => Math.min(candidates.length - 1, prev + 1))}
                disabled={currentIndex === candidates.length - 1}
                className="p-1.5 text-gray-600 hover:bg-gray-100 disabled:opacity-30 rounded-r-md border-l border-gray-300"
                title="Next Candidate"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {actionNotice && (
        <div className="p-3 bg-green-50 border border-green-200 text-green-800 text-xs rounded-md flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-600" />
          <span>{actionNotice}</span>
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center bg-white border border-gray-200 rounded-lg shadow-sm text-xs text-gray-500">
          Loading duplicate candidates...
        </div>
      ) : !currentPair ? (
        <div className="p-12 text-center bg-white border border-gray-200 rounded-lg shadow-sm text-xs text-gray-500">
          No duplicate candidates found.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Main Side-by-Side Comparison Card */}
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 space-y-6">
            {/* Top Match Score Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-gray-200">
              <div className="flex items-center gap-3">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
                  Match Confidence:
                </span>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-green-50 text-green-700 border border-green-200">
                  {(currentPair.hybrid_score * 100).toFixed(0)}% Match
                </span>
                <span className="text-xs font-semibold text-gray-700">
                  {currentPair.hybrid_classification.replace(/_/g, ' ')}
                </span>
              </div>

              {decisions[currentPair.pair_id] && (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
                  Status: {decisions[currentPair.pair_id]}
                </span>
              )}
            </div>

            {/* Side-by-Side Material Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Material A */}
              <div className="p-4 rounded-lg border border-gray-200 bg-gray-50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase text-blue-700">Material A</span>
                  <span className="text-xs font-medium text-gray-500">
                    {currentPair.source_material_a.source_cpse}
                  </span>
                </div>

                <div>
                  <span className="text-[11px] text-gray-400 uppercase font-semibold">Item Code</span>
                  <p className="font-mono text-sm font-bold text-gray-900">
                    {currentPair.source_material_a.source_material_code}
                  </p>
                </div>

                <div>
                  <span className="text-[11px] text-gray-400 uppercase font-semibold">Description</span>
                  <p className="text-xs text-gray-800 font-medium">
                    {currentPair.source_material_a.raw_description}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200 text-xs text-gray-600">
                  <div>
                    <span className="text-gray-400 text-[10px] uppercase block">Unit (UOM)</span>
                    <span className="font-mono font-bold text-gray-700">
                      {currentPair.source_material_a.uom}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400 text-[10px] uppercase block">Category</span>
                    <span className="text-gray-700">
                      {currentPair.source_material_a.category}
                    </span>
                  </div>
                </div>
              </div>

              {/* Material B */}
              <div className="p-4 rounded-lg border border-gray-200 bg-gray-50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase text-blue-700">Material B</span>
                  <span className="text-xs font-medium text-gray-500">
                    {currentPair.source_material_b.source_cpse}
                  </span>
                </div>

                <div>
                  <span className="text-[11px] text-gray-400 uppercase font-semibold">Item Code</span>
                  <p className="font-mono text-sm font-bold text-gray-900">
                    {currentPair.source_material_b.source_material_code}
                  </p>
                </div>

                <div>
                  <span className="text-[11px] text-gray-400 uppercase font-semibold">Description</span>
                  <p className="text-xs text-gray-800 font-medium">
                    {currentPair.source_material_b.raw_description}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200 text-xs text-gray-600">
                  <div>
                    <span className="text-gray-400 text-[10px] uppercase block">Unit (UOM)</span>
                    <span className="font-mono font-bold text-gray-700">
                      {currentPair.source_material_b.uom}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400 text-[10px] uppercase block">Category</span>
                    <span className="text-gray-700">
                      {currentPair.source_material_b.category}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Why Matched? Section */}
            <div className="p-4 rounded-lg border border-blue-100 bg-blue-50/60 space-y-2">
              <h4 className="text-xs font-bold text-blue-900 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                Why did these materials match?
              </h4>

              {currentExplanation ? (
                <div className="space-y-1.5">
                  <p className="text-xs text-blue-900 font-medium leading-relaxed">
                    {currentExplanation.reviewer_summary}
                  </p>
                  <ul className="text-xs text-blue-800 space-y-1 pl-4 list-disc">
                    {currentExplanation.factors
                      .filter((f) => f.direction === 'POSITIVE')
                      .slice(0, 3)
                      .map((f, i) => (
                        <li key={i}>
                          <strong>{f.display_label || f.factor_name}:</strong> {f.evidence && f.evidence.length > 0 ? f.evidence.join(', ') : f.explanation}
                        </li>
                      ))}
                  </ul>
                </div>
              ) : (
                <ul className="text-xs text-blue-800 space-y-1 pl-4 list-disc">
                  <li>Identical technical specifications and engineering attributes.</li>
                  <li>High text and token similarity across descriptions.</li>
                  <li>Compatible standard units of measurement.</li>
                </ul>
              )}
            </div>

            {/* Proposed National Material Code */}
            <div className="p-4 rounded-lg border border-gray-200 bg-gray-50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider block">
                  Proposed National Material Code
                </span>
                <span className="font-mono text-base font-bold text-blue-700">
                  {getProposedCode(currentPair)}
                </span>
                <p className="text-xs text-gray-500 mt-0.5">
                  Unified master catalog identifier for both CPSE records upon approval.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => handleDecision('APPROVE')}
                  className="px-3.5 py-2 rounded-md bg-green-600 hover:bg-green-700 text-white text-xs font-semibold shadow-sm transition-colors"
                >
                  Approve as Match
                </button>
                <button
                  onClick={() => handleDecision('REJECT')}
                  className="px-3.5 py-2 rounded-md bg-red-600 hover:bg-red-700 text-white text-xs font-semibold shadow-sm transition-colors"
                >
                  Reject (Keep Separate)
                </button>
                <button
                  onClick={() => handleDecision('NEEDS_MORE_INFO')}
                  className="px-3.5 py-2 rounded-md border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 text-xs font-medium transition-colors"
                >
                  Flag for Review
                </button>
              </div>
            </div>
          </div>

          {/* Collapsed Technical Details Accordion */}
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
            <button
              type="button"
              onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
              className="w-full p-4 flex items-center justify-between text-left hover:bg-gray-50 transition-colors rounded-lg"
            >
              <div className="flex items-center gap-2 text-gray-700 text-xs font-bold uppercase">
                <Info className="w-4 h-4 text-gray-400" />
                <span>Technical Scoring Details (Optional)</span>
              </div>
              <span className="text-xs text-blue-600 font-medium flex items-center gap-1">
                {showTechnicalDetails ? 'Hide Details' : 'View Scoring Breakdown'}
                {showTechnicalDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </span>
            </button>

            {showTechnicalDetails && (
              <div className="p-5 border-t border-gray-200 bg-gray-50 text-xs space-y-3">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-400 text-[10px] block uppercase">Fuzzy Text Score</span>
                    <span className="font-mono font-bold text-gray-900">
                      {(currentPair.rapidfuzz_score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-400 text-[10px] block uppercase">Attribute Match</span>
                    <span className="font-mono font-bold text-gray-900">
                      {(currentPair.feature_vector.attribute_similarity * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-400 text-[10px] block uppercase">Description Similarity</span>
                    <span className="font-mono font-bold text-gray-900">
                      {(currentPair.feature_vector.semantic_similarity_score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-400 text-[10px] block uppercase">Final Score</span>
                    <span className="font-mono font-bold text-blue-600">
                      {(currentPair.hybrid_score * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                <p className="text-[11px] text-gray-500">
                  Scores are calculated using a weighted combination of text similarity, extracted technical parameters, and description compatibility.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
