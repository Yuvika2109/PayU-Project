import type { ReactNode } from 'react';
import { Shield } from 'lucide-react';
import { useStore } from '@/lib/store';
import { StepIndicator } from '@/components/ui/StepIndicator';
import type { AppStep } from '@/types';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { step, setStep, uploadResponse, generateResponse } = useStore();

  const handleStepNav = (target: AppStep) => {
    // Only allow backwards nav to completed steps
    if (target >= step) return;
    if (target === 1) setStep(1);
    if (target === 2 && uploadResponse) setStep(2);
    if (target === 3 && generateResponse) setStep(3);
  };

  return (
    <div className="min-h-screen flex flex-col relative">
      {/* Background glow */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 70% 40% at 50% -5%, rgba(61,142,255,0.1) 0%, transparent 60%)',
        }}
      />

      {/* Header */}
      <header className="relative z-10 border-b border-border/50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(61,142,255,0.15)', border: '1px solid rgba(61,142,255,0.3)' }}
            >
              <Shield size={18} color="var(--signal-blue)" />
            </div>
            <div>
              <span className="font-display font-bold text-text-primary tracking-tight">
                Fraud Rule Engine
              </span>
              <span className="text-xs text-text-muted ml-2 font-mono">v1.0</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full"
              style={{ background: 'var(--signal-green)', boxShadow: '0 0 6px var(--signal-green)' }}
            />
            <span className="text-xs text-text-muted font-medium">Ollama Connected</span>
          </div>
        </div>
      </header>

      {/* Step Progress */}
      <div className="relative z-10 border-b border-border/30 bg-surface-1/50">
        <div className="max-w-7xl mx-auto px-6 py-5">
          <StepIndicator currentStep={step} onStepClick={handleStepNav} />
        </div>
      </div>

      {/* Main Content */}
      <main className="relative z-10 flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border/30 py-4">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between text-xs text-text-muted">
          <span>Fraud Rule Engine · Local LLM Powered</span>
          <span className="font-mono">Powered by Ollama</span>
        </div>
      </footer>
    </div>
  );
}
