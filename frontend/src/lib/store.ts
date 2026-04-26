import { create } from 'zustand';
import type {
  AppStep,
  UploadResponse,
  GenerateRulesResponse,
  EvaluationMetrics,
} from '@/types';

interface Store {
  step: AppStep;
  uploadResponse: UploadResponse | null;
  scenario: string;
  numRules: number;
  generateResponse: GenerateRulesResponse | null;
  selectedRuleIds: Set<string>;
  evaluationMetrics: EvaluationMetrics | null;

  // Actions
  setStep: (step: AppStep) => void;
  setUploadResponse: (r: UploadResponse) => void;
  setScenario: (s: string) => void;
  setNumRules: (n: number) => void;
  setGenerateResponse: (r: GenerateRulesResponse) => void;
  toggleRuleSelection: (id: string) => void;
  selectAllRules: () => void;
  deselectAllRules: () => void;
  setEvaluationMetrics: (m: EvaluationMetrics) => void;
  reset: () => void;
}

export const useStore = create<Store>((set, get) => ({
  step: 1,
  uploadResponse: null,
  scenario: '',
  numRules: 10,
  generateResponse: null,
  selectedRuleIds: new Set(),
  evaluationMetrics: null,

  setStep: (step) => set({ step }),
  setUploadResponse: (uploadResponse) => set({ uploadResponse }),
  setScenario: (scenario) => set({ scenario }),
  setNumRules: (numRules) => set({ numRules }),
  setGenerateResponse: (generateResponse) => {
    // Auto-select all rules when first generated
    const ids = new Set(generateResponse.rules.map((r) => r.id));
    set({ generateResponse, selectedRuleIds: ids });
  },
  toggleRuleSelection: (id) => {
    const ids = new Set(get().selectedRuleIds);
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    set({ selectedRuleIds: ids });
  },
  selectAllRules: () => {
    const rules = get().generateResponse?.rules ?? [];
    set({ selectedRuleIds: new Set(rules.map((r) => r.id)) });
  },
  deselectAllRules: () => set({ selectedRuleIds: new Set() }),
  setEvaluationMetrics: (evaluationMetrics) => set({ evaluationMetrics }),
  reset: () =>
    set({
      step: 1,
      uploadResponse: null,
      scenario: '',
      numRules: 10,
      generateResponse: null,
      selectedRuleIds: new Set(),
      evaluationMetrics: null,
    }),
}));
