import type { CriterionResult } from '../types/api'
import YellowFlagBadge from './YellowFlagBadge'

interface CriterionResultComponentProps {
  criterion: CriterionResult
}

export default function CriterionResultComponent({ criterion }: CriterionResultComponentProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="font-medium text-slate-800">{criterion.criterion_label}</p>
        <div className="flex items-center gap-2">
          {criterion.override && (
            <span className="px-2 py-1 text-xs rounded-lg bg-purple-100 text-purple-700">
              Override
            </span>
          )}
          <span
            className={`px-2 py-1 text-xs rounded-lg ${
              criterion.verdict === 'ELIGIBLE'
                ? 'bg-green-100 text-green-700'
                : criterion.verdict === 'NOT_ELIGIBLE'
                ? 'bg-red-100 text-red-700'
                : 'bg-amber-100 text-amber-700'
            }`}
          >
            {criterion.verdict}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-4 text-sm">
        <span className="text-slate-500">Confidence: {Math.round(criterion.ai_confidence * 100)}%</span>
        {criterion.yellow_flags && criterion.yellow_flags.length > 0 && (
          <YellowFlagBadge count={criterion.yellow_flags.length} />
        )}
      </div>
      <p className="text-sm text-slate-600 mt-2">{criterion.reason}</p>
      {criterion.override && (
        <p className="text-xs text-purple-600 mt-2">
          Override by {criterion.override.officer_name}: {criterion.override.rationale}
        </p>
      )}
    </div>
  )
}