import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { Upload, FileText, Database, ChevronRight, AlertCircle } from 'lucide-react';
import { uploadDataset } from '@/lib/api';
import { useStore } from '@/lib/store';
import { schemaLabel, formatNumber, formatPercent } from '@/lib/utils';
import { cn } from '@/lib/utils';

export function UploadStep() {
  const { setUploadResponse, setStep } = useStore();
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<{ filename: string; size: string } | null>(null);
  const [uploadResult, setUploadResult] = useState(useStore.getState().uploadResponse);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setPreview({
      filename: file.name,
      size: `${(file.size / 1024).toFixed(1)} KB`,
    });

    setUploading(true);
    try {
      const result = await uploadDataset(file);
      setUploadResponse(result);
      setUploadResult(result);
      toast.success(`Dataset loaded — ${formatNumber(result.rows)} rows detected`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      toast.error(msg);
      setPreview(null);
    } finally {
      setUploading(false);
    }
  }, [setUploadResponse]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    maxFiles: 1,
    disabled: uploading,
  });

  const handleNext = () => {
    if (uploadResult) setStep(2);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-slide-up">
      <div className="text-center space-y-2 mb-8">
        <h1 className="font-display text-3xl font-bold text-text-primary tracking-tight">
          Upload Your Dataset
        </h1>
        <p className="text-text-secondary text-base">
          Start by uploading a fraud transaction CSV. We'll auto-detect the schema and prepare it for rule generation.
        </p>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          'relative rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all duration-300',
          isDragActive
            ? 'border-signal-blue bg-signal-blue/5 scale-[1.01]'
            : 'border-border hover:border-border-accent hover:bg-surface-2/50',
          uploading && 'opacity-60 cursor-not-allowed'
        )}
      >
        <input {...getInputProps()} />

        {uploading ? (
          <div className="flex flex-col items-center gap-4">
            <div
              className="w-14 h-14 rounded-full border-2 border-signal-blue border-t-transparent animate-spin"
              style={{ borderTopColor: 'transparent' }}
            />
            <p className="text-text-secondary font-medium">Uploading and detecting schema…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center"
              style={{
                background: isDragActive
                  ? 'rgba(61,142,255,0.2)'
                  : 'rgba(255,255,255,0.05)',
                border: `1px solid ${isDragActive ? 'rgba(61,142,255,0.4)' : 'rgba(255,255,255,0.08)'}`,
              }}
            >
              <Upload
                size={28}
                color={isDragActive ? 'var(--signal-blue)' : 'var(--text-muted)'}
              />
            </div>
            <div>
              <p className="text-text-primary font-semibold text-lg">
                {isDragActive ? 'Drop to upload' : 'Drag & drop your CSV file'}
              </p>
              <p className="text-text-muted text-sm mt-1">
                or <span className="text-signal-blue underline underline-offset-2">browse files</span> · CSV up to 100 MB
              </p>
            </div>
            {preview && !uploading && (
              <div className="flex items-center gap-2 bg-surface-3 px-3 py-2 rounded-lg border border-border">
                <FileText size={14} color="var(--signal-blue)" />
                <span className="text-sm text-text-secondary font-mono">{preview.filename}</span>
                <span className="text-xs text-text-muted">({preview.size})</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Supported schemas info */}
      <div className="grid grid-cols-2 gap-4">
        {[
          {
            name: 'EMVCo Transaction',
            desc: 'Classic card transaction dataset',
            cols: ['transaction_id', 'bin_number', 'transaction_amount', 'foreign_ip_flag', '…'],
          },
          {
            name: 'EMVCo 3DS',
            desc: '3D Secure / money-laundering dataset',
            cols: ['threeds_server_trans_id', 'velocity_1h', 'velocity_24h', 'cross_border_flag', '…'],
          },
        ].map((schema) => (
          <div key={schema.name} className="card p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Database size={14} color="var(--signal-blue)" />
              <span className="text-sm font-semibold text-text-primary font-display">{schema.name}</span>
            </div>
            <p className="text-xs text-text-muted">{schema.desc}</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {schema.cols.map((c) => (
                <span key={c} className="tag">{c}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Dataset summary after upload */}
      {uploadResult && (
        <div className="card-elevated p-6 space-y-4 animate-slide-up">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-semibold text-lg text-text-primary">Dataset Summary</h2>
            <div className="flex items-center gap-2">
              <span
                className="text-xs font-mono font-semibold px-2.5 py-1 rounded-full"
                style={{
                  background: 'rgba(61,142,255,0.15)',
                  color: 'var(--signal-blue)',
                  border: '1px solid rgba(61,142,255,0.3)',
                }}
              >
                {schemaLabel(uploadResult.schema_type)}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Total Rows', value: formatNumber(uploadResult.rows) },
              { label: 'Fraud Cases', value: formatNumber(uploadResult.dataset_summary.fraud_rows) },
              { label: 'Clean Cases', value: formatNumber(uploadResult.dataset_summary.non_fraud_rows) },
              { label: 'Fraud Rate', value: formatPercent(uploadResult.dataset_summary.fraud_rate) },
            ].map((stat) => (
              <div key={stat.label} className="metric-card text-center">
                <p className="text-text-muted text-xs font-medium uppercase tracking-wide">{stat.label}</p>
                <p className="font-display font-bold text-2xl text-text-primary mt-1">{stat.value}</p>
              </div>
            ))}
          </div>

          <div>
            <p className="text-xs text-text-muted mb-2 font-medium uppercase tracking-wide">Detected Columns</p>
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
              {uploadResult.columns.map((col) => (
                <span key={col} className="tag">{col}</span>
              ))}
            </div>
          </div>

          {uploadResult.dataset_summary.fraud_rows === 0 && (
            <div
              className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm"
              style={{
                background: 'rgba(255,176,32,0.08)',
                border: '1px solid rgba(255,176,32,0.25)',
                color: 'var(--signal-amber)',
              }}
            >
              <AlertCircle size={14} />
              <span>No <code className="font-mono">fraud_label</code> column found. Precision/recall will be 0 — rules can still be evaluated for flag rate.</span>
            </div>
          )}
        </div>
      )}

      {/* Next button */}
      <div className="flex justify-end pt-2">
        <button
          className="btn-primary text-base px-6 py-3"
          disabled={!uploadResult}
          onClick={handleNext}
        >
          Continue to Rule Generation
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
