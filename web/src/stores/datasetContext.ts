import { computed, reactive, readonly } from "vue";


interface DatasetContextState {
  importRunId: number | undefined;
  importRunDisplayId: number | undefined;
  stockCode: string;
  startDate: string;
  endDate: string;
}

const state = reactive<DatasetContextState>({
  importRunId: undefined,
  importRunDisplayId: undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
});

export function useDatasetContextStore() {
  const hasSelection = computed(() => Boolean(state.importRunId));

  function applyScope(payload: Partial<DatasetContextState>) {
    if ("importRunId" in payload) {
      state.importRunId = payload.importRunId;

      if (payload.importRunId === undefined && !("importRunDisplayId" in payload)) {
        state.importRunDisplayId = undefined;
      }
    }

    if ("importRunDisplayId" in payload) {
      state.importRunDisplayId = payload.importRunDisplayId;
    }

    if ("stockCode" in payload) {
      state.stockCode = payload.stockCode ?? "";
    }

    if ("startDate" in payload) {
      state.startDate = payload.startDate ?? "";
    }

    if ("endDate" in payload) {
      state.endDate = payload.endDate ?? "";
    }
  }

  function resetScope() {
    applyScope({
      importRunId: undefined,
      importRunDisplayId: undefined,
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

