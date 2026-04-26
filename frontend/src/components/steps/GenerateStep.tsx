import { useState } from 'react';
import toast from 'react-hot-toast';
import { Sparkles, ChevronRight, ChevronLeft, Lightbulb, Settings2 } from 'lucide-react';
import { generateRules } from '@/lib/api';
import { useStore } from '@/lib/store';
import { schemaLabel } from '@/lib/utils';
import { RuleCardSkeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';

const PRESET_SCENARIOS = [
  {
    label: 'Card Testing Fraud',
    desc: 'Low-value micro-transactions probing card validity',
    prompt: 'Card testing attack: fraudsters make multiple small transactions (often under $5) in rapid succession to test if stolen card numbers are valid before making larger purchases.',
  },
  {
    label: 'Account Takeover',
    desc: 'Sudden behavioral shift after login',
    prompt: 'Account takeover: a legitimate account is compromised and the attacker changes shipping address, device, or IP location and immediately makes high-value purchases inconsistent with historical behavior.',
  },
  {
    label: 'Money Laundering',
    desc: '3DS cross-border structuring patterns',
    prompt: 'Money laundering via 3DS: structuring transactions across multiple cross-border merchants to avoid detection, with amounts just below reporting thresholds and high velocity across geographic regions.',
  },
  {
    label: 'BIN Attack',
    desc: 'Concentrated card number range exploitation',
    prompt: 'BIN attack: fraudsters generate card numbers with a specific BIN prefix and test them in bulk, resulting in high transaction volume from a narrow range of BIN numbers with many declines.',
  },
  {
    label: 'Friendly Fraud',
    desc: 'Chargeback abuse on legitimate transactions',
    prompt: 'Friendly fraud: cardholders make genuine purchases but then falsely dispute them as unauthorized. Pattern shows high-value single purchases, often digital goods or travel, with new device or shipping address.',
  },
  {
    label: 'Velocity Fraud',
    desc: 'Rapid multi-merchant transaction bursts',
    prompt: 'Velocity fraud: using stolen credentials to make rapid purchases across multiple merchants in a short time window, exploiting the gap before the card is reported stolen.',
  },
];

export function GenerateStep() {
  const { uploadResponse, scenario, numRules, setScenario, setNumRules, setGenerateResponse, setStep } = useStore();
  const [generating, setGenerating] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loadingDots, setLoadingDots] = useState('');

  const handleGenerate = async () => {
    if (!scenario.trim()) {
      toast.error('Please describe a fraud pattern first');
      return;
    }
    setGenerating(true);

    // Animate loading dots
    let dots = 0;
    const interval = setInterval(() => {
      dots = (dots + 1) % 4;
      setLoadingDots('.'.repeat(dots));
    }, 500);

    try {
      const result = await generateRules({
        scenario: scenario.trim(),
        mode: 'normal',
        num_rules: numRules,
        session_id: uploadResponse?.session_id,
        available_columns: uploadResponse?.columns,
        schema_type: uploadResponse?.schema_type,
      });
      setGenerateResponse(result);
      toast.success(`Generated ${result.rules.length} rules using ${result.model_used}`);
      setStep(3);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Rule generation failed';
      toast.error(msg);
    } finally {
      setGenerating(false);
      clearInterval(interval);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-slide-up">
      <div className="text-center space-y-2 mb-8">
        <h1 className="font-display text-3xl font-bold text-text-primary tracking-tight">
          Describe the Fraud Pattern
        </h1>
        <p className="text-text-secondary text-base">
          Explain the fraud scenario in plain English. The LLM will generate targeted detection rules tailored to your dataset.
        </p>
      </div>

      {/* Dataset context pill */}
      {uploadResponse && (
        <div
          className="flex items-center gap-2 px-4 py-2 rounded-full text-sm w-fit"
          style={{
            background: 'rgba(0,212,138,0.08)',
            border: '1px solid rgba(0,212,138,0.2)',
          }}
        >
          <div className="w-2 h-2 rounded-full bg-signal-green" />
          <span className="text-signal-green font-medium">
            {uploadResponse.filename}
          </span>
          <span className="text-text-muted">·</span>
          <span className="text-text-muted">{schemaLabel(uploadResponse.schema_type)}</span>
          <span className="text-text-muted">·</span>
          <span className="text-text-muted">{uploadResponse.rows.toLocaleString()} rows</span>
        </div>
      )}

      {/* Preset scenarios */}
      <div>
        <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-3 flex items-center gap-2">
          <Lightbulb size={12} />
          Quick Presets
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {PRESET_SCENARIOS.map((preset) => (
            <button
              key={preset.label}
              onClick={() => setScenario(preset.prompt)}
              className={cn(
                'text-left p-3 rounded-xl border transition-all duration-200',
                scenario === preset.prompt
                  ? 'border-signal-blue bg-signal-blue/10 text-text-primary'
                  : 'border-border bg-surface-1 text-text-secondary hover:border-border-accent hover:bg-surface-2'
              )}
            >
              <p className="font-semibold text-sm">{preset.label}</p>
              <p className="text-xs text-text-muted mt-0.5 leading-snug">{preset.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Scenario text area */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-text-primary">
          Fraud Pattern Description
        </label>
        <textarea
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          placeholder="e.g. Card testing attack: fraudsters probe stolen card numbers with micro-transactions under $1, with 10+ attempts per card within a 5-minute window across multiple merchants…"
          rows={5}
          className={cn(
            'w-full rounded-xl p-4 text-sm text-text-primary placeholder-text-muted resize-none',
            'border border-border bg-surface-1 focus:outline-none focus:border-signal-blue',
            'transition-colors duration-200 font-body leading-relaxed'
          )}
          style={{ background: 'var(--bg-surface-1)' }}
        />
        <p className="text-xs text-text-muted">
          {scenario.length} chars · Be specific about thresholds, velocities, and column names
        </p>
      </div>

      {/* Advanced settings */}
      <div>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-2 text-sm text-text-muted hover:text-text-secondary transition-colors"
        >
          <Settings2 size={14} />
          Advanced Options
          <span className="text-xs">{showAdvanced ? '▲' : '▼'}</span>
        </button>

        {showAdvanced && (
          <div className="mt-3 card p-4 space-y-4 animate-fade-in">
            <div>
              <label className="text-sm font-medium text-text-primary block mb-2">
                Number of Rules to Generate
                <span
                  className="ml-2 font-mono font-bold px-2 py-0.5 rounded text-xs"
                  style={{ background: 'rgba(61,142,255,0.15)', color: 'var(--signal-blue)' }}
                >
                  {numRules}
                </span>
              </label>
              <input
                type="range"
                min={3}
                max={20}
                value={numRules}
                onChange={(e) => setNumRules(Number(e.target.value))}
                className="w-full accent-signal-blue"
              />
              <div className="flex justify-between text-xs text-text-muted mt-1">
                <span>3 (focused)</span>
                <span>20 (comprehensive)</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Generate button */}
      <div className="flex justify-between items-center pt-2">
        <button className="btn-ghost" onClick={() => setStep(1)}>
          <ChevronLeft size={16} />
          Back
        </button>

        <button
          className="btn-primary text-base px-8 py-3"
          disabled={!scenario.trim() || generating}
          onClick={handleGenerate}
        >
          {generating ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Generating rules{loadingDots}
            </>
          ) : (
            <>
              <Sparkles size={16} />
              Generate {numRules} Rules
            </>
          )}
        </button>
      </div>

      {/* Skeleton preview while generating */}
      {generating && (
        <div className="space-y-3 mt-4">
          <p className="text-xs text-text-muted text-center animate-pulse">
            Calling local LLM · This may take 30–90 seconds depending on your model…
          </p>
          {Array.from({ length: 3 }).map((_, i) => (
            <RuleCardSkeleton key={i} />
          ))}
        </div>
      )}
    </div>
  );
}
