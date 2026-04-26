import { useState } from 'react';
import toast from 'react-hot-toast';
import {
  ChevronLeft, ChevronRight, ChevronDown, ChevronUp,
  Filter, CheckSquare, Square, Info
} from 'lucide-react';
import { useStore } from '@/lib/store';
import { evaluateRules } from '@/lib/api';
import {
  severityClass, categoryIcon, cn
} from '@/lib/utils';
import type { FraudRule, RuleCategory, RuleSeverity } from '@/types';

interface RuleCardProps {
  rule: FraudRule;
  selected: boolean;
  onToggle: () => void;
}

function RuleCard({ rule, selected, onToggle }: RuleCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        'rounded-xl border transition-all duration-200 overflow-hidden',
        selected
          ? 'border-signal-blue/40 bg-signal-blue/5'
          : 'border-border bg-surface-1 hover:border-border-accent'
      )}
    >
      {/* Card Header */}
      <div className="flex items-start gap-3 p-4">
        {/* Checkbox */}
        <button
          onClick={onToggle}
          className={cn('rule-checkbox mt-0.5', selected && 'checked')}
          aria-label={selected ? 'Deselect rule' : 'Select rule'}
        >
          {selected && (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M1.5 5L4 7.5L8.5 2.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </button>

        <div className="flex-1 min-w-0">
          {/* Rule meta row */}
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span
              className={cn('text-xs font-semibold px-2 py-0.5 rounded-full', severityClass(rule.severity))}
            >
              {rule.severity.toUpperCase()}
            </span>
            <span className="text-xs text-text-muted">
              {categoryIcon(rule.category)} {rule.category}
            </span>
            <span className="font-mono text-xs text-text-muted">{rule.id}</span>
          </div>

          {/* Rule name + description */}
          <h3 className="font-display font-semibold text-text-primary text-sm leading-tight">{rule.name}</h3>
          <p className="text-text-secondary text-xs mt-1 leading-relaxed line-clamp-2">{rule.description}</p>

          {/* Logic expression */}
          <div
            className="mt-2 px-3 py-1.5 rounded-lg font-mono text-xs"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}
          >
            <span className="text-signal-blue">if</span>{' '}
            <span className="text-text-primary">{rule.logic_expression}</span>
          </div>

          {/* Tags */}
          {rule.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {rule.tags.map((tag) => (
                <span key={tag} className="tag">{tag}</span>
              ))}
            </div>
          )}
        </div>

        {/* Expand button */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-text-muted hover:text-text-secondary transition-colors mt-0.5 flex-shrink-0"
          title="View conditions"
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Expanded: conditions detail */}
      {expanded && rule.conditions.length > 0 && (
        <div
          className="border-t px-4 py-3 space-y-2"
          style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.15)' }}
        >
          <p className="text-xs text-text-muted font-medium uppercase tracking-wide flex items-center gap-1.5">
            <Info size={10} /> Conditions ({rule.match_any ? 'ANY match' : 'ALL must match'})
          </p>
          <div className="space-y-1.5">
            {rule.conditions.map((cond, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs">
                <span
                  className="font-mono px-1.5 py-0.5 rounded text-text-secondary flex-shrink-0"
                  style={{ background: 'rgba(255,255,255,0.05)' }}
                >
                  {idx + 1}
                </span>
                <div>
                  <span className="font-mono text-signal-blue">{cond.field}</span>
                  {' '}
                  <span className="text-signal-amber font-mono">{cond.operator}</span>
                  {' '}
                  <span className="font-mono text-signal-green">
                    {Array.isArray(cond.value) ? `[${cond.value.join(', ')}]` : String(cond.value)}
                  </span>
                  {cond.description && (
                    <p className="text-text-muted mt-0.5 leading-snug">{cond.description}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Filter controls ──────────────────────────────────────────────────────────

const CATEGORIES: RuleCategory[] = ['velocity', 'amount', 'device', 'geography', 'authentication', 'behavioral', 'account', 'merchant'];
const SEVERITIES: RuleSeverity[] = ['high', 'medium', 'low'];

export function SelectRulesStep() {
  const {
    uploadResponse, generateResponse, selectedRuleIds,
    toggleRuleSelection, selectAllRules, deselectAllRules,
    setEvaluationMetrics, setStep,
  } = useStore();

  const [evaluating, setEvaluating] = useState(false);
  const [filterCategory, setFilterCategory] = useState<RuleCategory | 'all'>('all');
  const [filterSeverity, setFilterSeverity] = useState<RuleSeverity | 'all'>('all');

  const rules = generateResponse?.rules ?? [];

  const filteredRules = rules.filter((r) => {
    if (filterCategory !== 'all' && r.category !== filterCategory) return false;
    if (filterSeverity !== 'all' && r.severity !== filterSeverity) return false;
    return true;
  });

  const selectedCount = selectedRuleIds.size;

  const handleEvaluate = async () => {
    if (!uploadResponse || selectedCount === 0) return;
    setEvaluating(true);
    try {
      const metrics = await evaluateRules(uploadResponse.session_id, {
        rules,
        selected_rule_ids: Array.from(selectedRuleIds),
      });
      setEvaluationMetrics(metrics);
      toast.success('Evaluation complete!');
      setStep(4);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Evaluation failed';
      toast.error(msg);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-text-primary tracking-tight">
            Select Rules to Evaluate
          </h1>
          <p className="text-text-secondary text-base mt-1">
            {generateResponse?.scenario_summary}
          </p>
        </div>
        <div
          className="flex-shrink-0 text-center px-4 py-3 rounded-xl"
          style={{ background: 'rgba(61,142,255,0.1)', border: '1px solid rgba(61,142,255,0.25)' }}
        >
          <p className="font-display font-bold text-2xl text-signal-blue">{selectedCount}</p>
          <p className="text-xs text-text-muted">selected</p>
        </div>
      </div>

      {/* Filters + bulk actions */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <Filter size={14} className="text-text-muted" />
          <span className="text-xs text-text-muted font-medium">Filter:</span>
        </div>

        {/* Category filter */}
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value as RuleCategory | 'all')}
          className="text-xs bg-surface-2 border border-border rounded-lg px-3 py-1.5 text-text-secondary focus:outline-none focus:border-signal-blue"
        >
          <option value="all">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{categoryIcon(c)} {c}</option>
          ))}
        </select>

        {/* Severity filter */}
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value as RuleSeverity | 'all')}
          className="text-xs bg-surface-2 border border-border rounded-lg px-3 py-1.5 text-text-secondary focus:outline-none focus:border-signal-blue"
        >
          <option value="all">All Severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <div className="ml-auto flex gap-2">
          <button
            onClick={selectAllRules}
            className="flex items-center gap-1.5 text-xs btn-ghost py-1.5 px-3"
          >
            <CheckSquare size={13} />
            Select All
          </button>
          <button
            onClick={deselectAllRules}
            className="flex items-center gap-1.5 text-xs btn-ghost py-1.5 px-3"
          >
            <Square size={13} />
            Deselect All
          </button>
        </div>
      </div>

      {/* Model info */}
      {generateResponse && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span className="font-mono bg-surface-3 px-2 py-0.5 rounded border border-border">
            {generateResponse.model_used}
          </span>
          <span>generated {rules.length} rules ·</span>
          <span>{filteredRules.length} shown</span>
        </div>
      )}

      {/* Rule cards */}
      <div className="space-y-3">
        {filteredRules.map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            selected={selectedRuleIds.has(rule.id)}
            onToggle={() => toggleRuleSelection(rule.id)}
          />
        ))}
        {filteredRules.length === 0 && (
          <div className="text-center py-12 text-text-muted">
            <p>No rules match the current filters.</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between items-center pt-4">
        <button className="btn-ghost" onClick={() => setStep(2)}>
          <ChevronLeft size={16} />
          Back
        </button>

        <button
          className="btn-primary text-base px-8 py-3"
          disabled={selectedCount === 0 || evaluating}
          onClick={handleEvaluate}
        >
          {evaluating ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Evaluating…
            </>
          ) : (
            <>
              Evaluate {selectedCount} Rule{selectedCount !== 1 ? 's' : ''}
              <ChevronRight size={16} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
