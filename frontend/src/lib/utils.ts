import { clsx, type ClassValue } from 'clsx';
import type { RuleCategory, RuleSeverity } from '@/types';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

export function severityColor(severity: RuleSeverity): string {
  switch (severity) {
    case 'high': return 'var(--signal-red)';
    case 'medium': return 'var(--signal-amber)';
    case 'low': return 'var(--signal-green)';
  }
}

export function severityClass(severity: RuleSeverity): string {
  switch (severity) {
    case 'high': return 'severity-high';
    case 'medium': return 'severity-medium';
    case 'low': return 'severity-low';
  }
}

export function categoryIcon(category: RuleCategory): string {
  switch (category) {
    case 'velocity': return '⚡';
    case 'amount': return '💰';
    case 'device': return '📱';
    case 'geography': return '🌍';
    case 'authentication': return '🔐';
    case 'behavioral': return '🧠';
    case 'account': return '👤';
    case 'merchant': return '🏪';
    default: return '🔍';
  }
}

export function schemaLabel(schema: string): string {
  return schema === 'emvco_3ds' ? 'EMVCo 3DS' : 'EMVCo';
}

export function scoreColor(score: number): string {
  if (score >= 0.7) return 'var(--signal-green)';
  if (score >= 0.4) return 'var(--signal-amber)';
  return 'var(--signal-red)';
}
