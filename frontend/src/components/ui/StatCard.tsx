import React, { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  change?: string;
  isPositive?: boolean;
  icon?: ReactNode;
  accentColor?: 'blue' | 'green' | 'amber' | 'purple' | 'cyan' | 'emerald' | 'indigo';
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  change,
  isPositive,
  icon,
  className,
}) => {
  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 bg-white p-5 shadow-sm hover:border-blue-300 transition-colors',
        className
      )}
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{title}</p>
        {icon && (
          <div className="w-8 h-8 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center">
            {icon}
          </div>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <h3 className="text-2xl font-bold tracking-tight text-gray-900">{value}</h3>
        {change && (
          <span
            className={cn(
              'text-xs font-medium',
              isPositive ? 'text-green-600' : 'text-red-600'
            )}
          >
            {change}
          </span>
        )}
      </div>
      {subtitle && <p className="mt-1 text-xs text-gray-500">{subtitle}</p>}
    </div>
  );
};
