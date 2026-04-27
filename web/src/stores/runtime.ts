import { computed, reactive, readonly } from "vue";

interface AlgoIndexRuntimeStatus {
  statusText: string;
  completedAtText: string;
  stockCount: number | null;
}

const state = reactive({
  lastSuccessfulSyncAt: "" as string,
  algoIndexStatus: null as AlgoIndexRuntimeStatus | null,
});

export function useRuntimeStore() {
  const syncStatusText = computed(() => (state.lastSuccessfulSyncAt ? "\u5df2\u540c\u6b65" : "\u672a\u540c\u6b65"));
  const lastSyncText = computed(() =>
    state.lastSuccessfulSyncAt
      ? new Date(state.lastSuccessfulSyncAt).toLocaleString("zh-CN")
      : "\u5c1a\u65e0\u540c\u6b65\u8bb0\u5f55"
  );

  function markSynced() {
    state.lastSuccessfulSyncAt = new Date().toISOString();
  }

  function setAlgoIndexStatus(status: AlgoIndexRuntimeStatus | null) {
    state.algoIndexStatus = status;
  }

  return {
    state: readonly(state),
    syncStatusText,
    lastSyncText,
    markSynced,
    setAlgoIndexStatus,
  };
}
