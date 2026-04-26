import axios from 'axios';
import type {
  UploadResponse,
  GenerateRulesRequest,
  GenerateRulesResponse,
  EvaluateRequest,
  EvaluationMetrics,
} from '@/types';

const BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 300_000, // 5 min for LLM calls
});

// Response interceptor for error normalisation
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      'Unknown error';
    return Promise.reject(new Error(message));
  }
);

// ─── Dataset ──────────────────────────────────────────────────────────────────

export async function uploadDataset(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<UploadResponse>('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

// ─── Rules ────────────────────────────────────────────────────────────────────

export async function generateRules(
  req: GenerateRulesRequest
): Promise<GenerateRulesResponse> {
  const { data } = await api.post<GenerateRulesResponse>('/rules/generate', req);
  return data;
}

export async function evaluateRules(
  sessionId: string,
  req: EvaluateRequest
): Promise<EvaluationMetrics> {
  const { data } = await api.post<EvaluationMetrics>(
    `/rules/evaluate/${sessionId}`,
    req
  );
  return data;
}

// ─── Health ───────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{
  service: string;
  llm: { status: string; configured_model: string; model_available: boolean; available_models: string[] };
}> {
  const { data } = await api.get('/health');
  return data;
}
