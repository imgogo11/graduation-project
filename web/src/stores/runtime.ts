import { computed, reactive, readonly } from "vue";


const state = reactive({
  lastSuccessfulSyncAt: "" as string,
});

export function useRuntimeStore() {
  const syncStatusText = computed(() => (state.lastSuccessfulSyncAt ? "已同步" : "未同步"));
  const lastSyncText = computed(() =>
    state.lastSuccessfulSyncAt
      ? new Date(state.lastSuccessfulSyncAt).toLocaleString("zh-CN")
      : "尚无同步记录"
  );

  function markSynced() {
    state.lastSuccessfulSyncAt = new Date().toISOString();
  }

  return {
    state: readonly(state),
    syncStatusText,
    lastSyncText,
    markSynced,
  };
}
