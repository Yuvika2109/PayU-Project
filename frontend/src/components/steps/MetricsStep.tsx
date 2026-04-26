import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from 'recharts';
import { RotateCcw, Download, TrendingUp, Shield, Zap, Target } from 'lucide-react';
import { useStore } from '@/lib/store';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { formatNumber, formatPercent, severityColor, categoryIcon, cn } from '@/lib/utils';
import type { RuleResult } from '@/types';

// ─── Metric Card ──────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  icon?: React.ReactNode;
  color?: string;
}

function MetricCard({ label, value, sub, icon, color }: MetricCardProps) {
  return (
    <div className="metric-card flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted font-medium uppercase tracking-wide">{label}</span>
        {icon && <span style={{ color: color ?? 'var(--text-muted)' }}>{icon}</span>}
      </div>
      <p
        className="font-display font-bold text-2xl"
        style={{ color: color ?? 'var(--text-primary)' }}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-text-muted">{sub}</p>}
    </div>
  );
}

// ─── Rule result row ──────────────────────────────────────────────────────────

function RuleResultRow({ result }: { result: RuleResult }) {
  const [open, setOpen] = useState(false);
  const sColor = severityColor(result.severity);

  return (
    <div
      className="rounded-xl border overflow-hidden transition-all duration-200"
      style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'var(--bg-surface-1)' }}
    >
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-2/50 transition-colors"
        onClick={() => setOpen(!open)}
      >
        {/* Severity dot */}
        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: sColor }} />

        {/* Rule name */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-text-primary truncate">{result.rule_name}</span>
            <span className="text-xs text-text-muted font-mono flex-shrink-0">{result.rule_id}</span>
            <span className="text-xs text-text-muted flex-shrink-0">
              {categoryIcon(result.category)} {result.category}
            </span>
          </div>
          <p className="text-xs text-text-muted font-mono mt-0.5 truncate">{result.logic_expression}</p>
        </div>

        {/* Quick metrics */}
        <div className="hidden sm:flex items-center gap-5 flex-shrink-0">
          <div className="text-right">
            <p className="text-xs text-text-muted">Flagged</p>
            <p className="text-sm font-bold text-text-primary">{formatNumber(result.flagged_count)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">Precision</p>
            <p
              className="text-sm font-bold"
              style={{ color: result.precision >= 0.7 ? 'var(--signal-green)' : result.precision >= 0.4 ? 'var(--signal-amber)' : 'var(--signal-red)' }}
            >
              {formatPercent(result.precision)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">Recall</p>
            <p className="text-sm font-bold text-text-primary">{formatPercent(result.recall)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">F1</p>
            <p className="text-sm font-bold text-text-primary">{formatPercent(result.f1)}</p>
          </div>
        </div>

        <span className="text-text-muted">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div
          className="px-4 py-3 border-t space-y-3"
          style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.15)' }}
        >
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            {[
              { label: 'Flag Rate', value: formatPercent(result.flag_rate) },
              { label: 'True Positives', value: formatNumber(result.true_positive_count) },
              { label: 'False Positives', value: formatNumber(result.false_positive_count) },
              { label: 'F1 Score', value: formatPercent(result.f1) },
            ].map((m) => (
              <div
                key={m.label}
                className="rounded-lg py-2 px-3"
                style={{ background: 'rgba(255,255,255,0.04)' }}
              >
                <p className="text-xs text-text-muted">{m.label}</p>
                <p className="text-sm font-bold text-text-primary mt-0.5">{m.value}</p>
              </div>
            ))}
          </div>

          {result.sample_flagged_ids.length > 0 && (
            <div>
              <p className="text-xs text-text-muted mb-1 font-medium">Sample Flagged IDs</p>
              <div className="flex flex-wrap gap-1.5">
                {result.sample_flagged_ids.map((id) => (
                  <span key={id} className="tag">{id}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Custom tooltip for bar chart ─────────────────────────────────────────────

function CustomBarTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs space-y-1" style={{ background: 'var(--bg-surface-2)' }}>
      <p className="font-semibold text-text-primary">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-text-secondary">
          {p.name}: <span className="text-text-primary font-mono">{(p.value * 100).toFixed(1)}%</span>
        </p>
      ))}
    </div>
  );
}

// ─── Main Metrics Step ────────────────────────────────────────────────────────

export function MetricsStep() {
  const { evaluationMetrics, generateResponse, reset } = useStore();
  const [tab, setTab] = useState<'overview' | 'rules' | 'sample'>('overview');

  if (!evaluationMetrics) return null;

  const m = evaluationMetrics;
  const ds = m.dataset_summary;

  // Bar chart data
  const barData = m.rule_results.map((r) => ({
    name: r.rule_id,
    fullName: r.rule_name,
    precision: r.precision,
    recall: r.recall,
    f1: r.f1,
    severity: r.severity,
  }));

  // Radar chart data
  const radarData = [
    { subject: 'Precision', value: m.overall_precision * 100 },
    { subject: 'Recall', value: m.overall_recall * 100 },
    { subject: 'F1', value: m.overall_f1 * 100 },
    { subject: 'Coverage', value: m.overall_flag_rate * 100 },
    { subject: 'Fraud Hit', value: ds.fraud_rows > 0 ? (m.fraud_captured / ds.fraud_rows) * 100 : 0 },
  ];

  // Export JSON
  const handleExport = () => {
    const blob = new Blob([JSON.stringify(evaluationMetrics, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fraud-rule-evaluation-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-text-primary tracking-tight">
            Evaluation Results
          </h1>
          <p className="text-text-secondary text-base mt-1">
            {generateResponse?.scenario_summary}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost py-2 px-4" onClick={handleExport}>
            <Download size={15} />
            Export JSON
          </button>
          <button className="btn-ghost py-2 px-4" onClick={reset}>
            <RotateCcw size={15} />
            New Session
          </button>
        </div>
      </div>

      {/* Aggregate metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label="Total Records"
          value={formatNumber(m.total_records)}
          sub="in dataset"
          icon={<Shield size={16} />}
          color="var(--signal-blue)"
        />
        <MetricCard
          label="Flagged"
          value={formatNumber(m.total_flagged)}
          sub={`${formatPercent(m.overall_flag_rate)} flag rate`}
          icon={<Zap size={16} />}
          color="var(--signal-amber)"
        />
        <MetricCard
          label="Fraud Captured"
          value={formatNumber(m.fraud_captured)}
          sub={ds.fraud_rows > 0 ? `of ${formatNumber(ds.fraud_rows)} fraud cases` : 'no labels'}
          icon={<Target size={16} />}
          color="var(--signal-red)"
        />
        <MetricCard
          label="Overall F1"
          value={formatPercent(m.overall_f1)}
          sub="harmonic mean"
          icon={<TrendingUp size={16} />}
          color="var(--signal-green)"
        />
      </div>

      {/* Score rings */}
      <div className="card-elevated p-6">
        <div className="flex items-center justify-around flex-wrap gap-6">
          <ScoreRing value={m.overall_precision} label="Precision" size={100} />
          <ScoreRing value={m.overall_recall} label="Recall" size={100} />
          <ScoreRing value={m.overall_f1} label="F1 Score" size={100} />
          <ScoreRing
            value={ds.fraud_rows > 0 ? m.fraud_captured / ds.fraud_rows : 0}
            label="Fraud Hit Rate"
            size={100}
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {(['overview', 'rules', 'sample'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              'px-5 py-2.5 text-sm font-medium transition-colors capitalize border-b-2 -mb-px',
              tab === t
                ? 'border-signal-blue text-signal-blue'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            )}
          >
            {t === 'overview' ? 'Charts' : t === 'rules' ? 'Per-Rule Results' : 'Flagged Sample'}
          </button>
        ))}
      </div>

      {/* Tab: Overview charts */}
      {tab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">
          {/* Bar chart */}
          <div className="card-elevated p-5">
            <h3 className="font-display font-semibold text-text-primary mb-4">Precision / Recall / F1 by Rule</h3>
            {barData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barData} margin={{ top: 4, right: 4, left: -20, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                  <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                  <Tooltip content={<CustomBarTooltip />} />
                  <Bar dataKey="precision" name="Precision" fill="var(--signal-blue)" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="recall" name="Recall" fill="var(--signal-amber)" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="f1" name="F1" fill="var(--signal-green)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-text-muted text-sm text-center py-12">No data</p>
            )}
          </div>

          {/* Radar chart */}
          <div className="card-elevated p-5">
            <h3 className="font-display font-semibold text-text-primary mb-4">Overall Performance Radar</h3>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.07)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <Radar name="Score" dataKey="value" stroke="var(--signal-blue)" fill="var(--signal-blue)" fillOpacity={0.2} strokeWidth={2} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Flagged count bar */}
          <div className="card-elevated p-5 lg:col-span-2">
            <h3 className="font-display font-semibold text-text-primary mb-4">Flagged Transactions by Rule</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={m.rule_results} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="rule_id" tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-surface-2)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
                />
                <Bar dataKey="flagged_count" name="Flagged" radius={[4, 4, 0, 0]}>
                  {m.rule_results.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={severityColor(entry.severity)} opacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="flex gap-4 mt-3 justify-end text-xs text-text-muted">
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm mr-1" style={{ background: 'var(--signal-red)' }} />High</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm mr-1" style={{ background: 'var(--signal-amber)' }} />Medium</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm mr-1" style={{ background: 'var(--signal-green)' }} />Low</span>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Per-rule results */}
      {tab === 'rules' && (
        <div className="space-y-3 animate-fade-in">
          {m.rule_results.map((result) => (
            <RuleResultRow key={result.rule_id} result={result} />
          ))}
        </div>
      )}

      {/* Tab: Flagged sample */}
      {tab === 'sample' && (
        <div className="animate-fade-in">
          {m.flagged_sample.length > 0 ? (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                      {Object.keys(m.flagged_sample[0]).slice(0, 10).map((col) => (
                        <th
                          key={col}
                          className="text-left px-3 py-2.5 font-semibold text-text-muted font-mono uppercase tracking-wide whitespace-nowrap"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {m.flagged_sample.map((row, i) => (
                      <tr
                        key={i}
                        className="border-b hover:bg-surface-2/50 transition-colors"
                        style={{ borderColor: 'rgba(255,255,255,0.04)' }}
                      >
                        {Object.values(row).slice(0, 10).map((val, j) => (
                          <td key={j} className="px-3 py-2 text-text-secondary font-mono whitespace-nowrap">
                            {val === null ? <span className="text-text-muted italic">null</span> : String(val)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="px-4 py-2 border-t text-xs text-text-muted" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
                Showing {m.flagged_sample.length} of {formatNumber(m.total_flagged)} flagged records · First 10 columns displayed
              </div>
            </div>
          ) : (
            <div className="text-center py-16 text-text-muted">
              <p className="text-lg mb-2">No flagged records</p>
              <p className="text-sm">The selected rules did not match any rows in your dataset.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
