import { computed, reactive, readonly } from "vue";


interface DatasetContextState {
  importRunId: number | undefined;
  stockCode: string;
  startDate: string;
  endDate: string;
}

const state = reactive<DatasetContextState>({
  importRunId: undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
});

export function useDatasetContextStore() {
  const hasSelection = computed(() => Boolean(state.importRunId));

  function applyScope(payload: Partial<DatasetContextState>) {
    state.importRunId = payload.importRunId;
    state.stockCode = payload.stockCode ?? "";
    state.startDate = payload.startDate ?? "";
    state.endDate = payload.endDate ?? "";
  }

  function resetScope() {
    applyScope({
      importRunId: undefined,
      stockCode: "",
      startDate: "",
      endDate: "",
    });
  }

  return {
    state: readonly(state),
    hasSelection,
    applyScope,
    resetScope,
  };
}

