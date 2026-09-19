import React from 'react';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
  const getStyle = (val: string) => {
    switch (val.toLowerCase()) {
      case 'standardized':
      case 'approved':
      case 'high_confidence_duplicate':
      case 'auto_match_recommended':
      case 'strong_match':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'possible_duplicate':
      case 'strong_review_candidate':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'low_confidence_review':
      case 'manual_review_required':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'pending review':
      case 'ambiguous_requires_review':
      case 'weak_match_review_optional':
      case 'pending l1':
      case 'pending l2':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      case 'under approval':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'flagged':
      case 'rejected':
      case 'rejected_by_scoring':
      case 'high':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'low':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'medium':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border tracking-wide uppercase',
        getStyle(status),
        className
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {status.replace(/_/g, ' ')}
    </span>
  );
};
