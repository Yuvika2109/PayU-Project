import { cn } from '@/lib/utils';
import type { AppStep } from '@/types';

const STEPS = [
  { id: 1, label: 'Upload Dataset' },
  { id: 2, label: 'Describe Pattern' },
  { id: 3, label: 'Select Rules' },
  { id: 4, label: 'View Metrics' },
] as const;

interface StepIndicatorProps {
  currentStep: AppStep;
  onStepClick?: (step: AppStep) => void;
}

export function StepIndicator({ currentStep, onStepClick }: StepIndicatorProps) {
  return (
    <div className="flex items-center w-full max-w-2xl mx-auto">
      {STEPS.map((step, idx) => {
        const isComplete = step.id < currentStep;
        const isActive = step.id === currentStep;
        const isClickable = isComplete && onStepClick;

        return (
          <div key={step.id} className="flex items-center flex-1">
            <div className="flex flex-col items-center gap-2">
              <button
                onClick={isClickable ? () => onStepClick(step.id as AppStep) : undefined}
                className={cn(
                  'w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold font-mono transition-all duration-300',
                  isComplete && 'bg-signal-blue text-white cursor-pointer',
                  isActive && 'bg-signal-blue text-white ring-4 ring-signal-blue/20 scale-110',
                  !isComplete && !isActive && 'bg-surface-3 text-text-muted border border-border',
                  isClickable && 'hover:ring-4 hover:ring-signal-blue/20'
                )}
              >
                {isComplete ? (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M2 7L5.5 10.5L12 3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : step.id}
              </button>
              <span
                className={cn(
                  'text-xs font-medium whitespace-nowrap transition-colors duration-300',
                  isActive && 'text-text-primary',
                  isComplete && 'text-signal-blue',
                  !isComplete && !isActive && 'text-text-muted'
                )}
              >
                {step.label}
              </span>
            </div>

            {idx < STEPS.length - 1 && (
              <div
                className={cn(
                  'step-line mb-5 mx-1 transition-all duration-500',
                  isComplete && 'active'
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
