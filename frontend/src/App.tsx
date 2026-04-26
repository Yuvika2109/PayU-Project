import { Toaster } from 'react-hot-toast';
import { Layout } from '@/components/layout/Layout';
import { UploadStep } from '@/components/steps/UploadStep';
import { GenerateStep } from '@/components/steps/GenerateStep';
import { SelectRulesStep } from '@/components/steps/SelectRulesStep';
import { MetricsStep } from '@/components/steps/MetricsStep';
import { useStore } from '@/lib/store';

export default function App() {
  const step = useStore((s) => s.step);

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-surface-2)',
            color: 'var(--text-primary)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '10px',
            fontSize: '13px',
            fontFamily: 'DM Sans, sans-serif',
          },
          success: {
            iconTheme: { primary: 'var(--signal-green)', secondary: 'transparent' },
          },
          error: {
            iconTheme: { primary: 'var(--signal-red)', secondary: 'transparent' },
          },
        }}
      />

      <Layout>
        {step === 1 && <UploadStep />}
        {step === 2 && <GenerateStep />}
        {step === 3 && <SelectRulesStep />}
        {step === 4 && <MetricsStep />}
      </Layout>
    </>
  );
}
