import { computed, reactive, readonly } from "vue";


interface DatasetContextState {
  importRunId: number | undefined;
  importRunDisplayId: number | undefined;
  stockCode: string;
  startDate: string;
  endDate: string;
  sampleLimitInput: string;
  crossMetric: string;
  topNInput: string;
  correlationStockCodes: string[];
  kInput: string;
  kthMethod: "persistent_segment_tree" | "t_digest";
  jointTopNInput: string;
  severity: string;
  eventTopNInput: string;
  appliedRevision: number;
}

type PersistedDatasetContextState = Omit<DatasetContextState, "appliedRevision">;

const STORAGE_KEY = "graduation-project:dataset-context:v1";

const defaultState: DatasetContextState = {
  importRunId: undefined,
  importRunDisplayId: undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
  sampleLimitInput: "200",
  crossMetric: "total_return",
  topNInput: "10",
  correlationStockCodes: [],
  kInput: "1",
  kthMethod: "persistent_segment_tree",
  jointTopNInput: "20",
  severity: "",
  eventTopNInput: "50",
  appliedRevision: 0,
};

function readPersistedState(): Partial<PersistedDatasetContextState> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const payload = JSON.parse(raw) as Partial<PersistedDatasetContextState>;
    if (!payload || typeof payload !== "object") {
      return {};
    }
    return {
      importRunId: payload.importRunId,
      importRunDisplayId: payload.importRunDisplayId,
      stockCode: payload.stockCode,
      startDate: payload.startDate,
      endDate: payload.endDate,
      sampleLimitInput: payload.sampleLimitInput,
      crossMetric: payload.crossMetric,
      topNInput: payload.topNInput,
      correlationStockCodes: payload.correlationStockCodes,
      kInput: payload.kInput,
      kthMethod: payload.kthMethod,
      jointTopNInput: payload.jointTopNInput,
      severity: payload.severity,
      eventTopNInput: payload.eventTopNInput,
    };
  } catch {
    window.sessionStorage.removeItem(STORAGE_KEY);
    return {};
  }
}

function persistState() {
  if (typeof window === "undefined") {
    return;
  }

  const { appliedRevision: _appliedRevision, ...payload } = state;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function clearPersistedState() {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.removeItem(STORAGE_KEY);
}

const state = reactive<DatasetContextState>({
  ...defaultState,
  ...readPersistedState(),
  appliedRevision: 0,
});

export function useDatasetContextStore() {
  const hasSelection = computed(() => Boolean(state.importRunId));

  function applyScope(payload: Partial<DatasetContextState>, options: { commit?: boolean } = {}) {
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

    if ("sampleLimitInput" in payload) {
      state.sampleLimitInput = payload.sampleLimitInput ?? "200";
    }

    if ("crossMetric" in payload) {
      state.crossMetric = payload.crossMetric || "total_return";
    }

    if ("topNInput" in payload) {
      state.topNInput = payload.topNInput ?? "10";
    }

    if ("correlationStockCodes" in payload) {
      state.correlationStockCodes = [...(payload.correlationStockCodes ?? [])];
    }

    if ("kInput" in payload) {
      state.kInput = payload.kInput ?? "1";
    }

    if ("kthMethod" in payload) {
      state.kthMethod = payload.kthMethod ?? "persistent_segment_tree";
    }

    if ("jointTopNInput" in payload) {
      state.jointTopNInput = payload.jointTopNInput ?? "20";
    }

    if ("severity" in payload) {
      state.severity = payload.severity ?? "";
    }

    if ("eventTopNInput" in payload) {
      state.eventTopNInput = payload.eventTopNInput ?? "50";
    }

    if (options.commit) {
      state.appliedRevision += 1;
    }

    persistState();
  }

  function resetScope() {
    applyScope({
      importRunId: undefined,
      importRunDisplayId: undefined,
      stockCode: "",
      startDate: "",
      endDate: "",
      sampleLimitInput: "200",
      crossMetric: "total_return",
      topNInput: "10",
      correlationStockCodes: [],
      kInput: "1",
      kthMethod: "persistent_segment_tree",
      jointTopNInput: "20",
      severity: "",
      eventTopNInput: "50",
    });
    state.appliedRevision = 0;
    clearPersistedState();
  }

  return {
    state: readonly(state),
    hasSelection,
    applyScope,
    resetScope,
  };
}

