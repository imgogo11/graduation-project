import { computed, reactive, readonly } from "vue";


const state = reactive({
  lastSuccessfulSyncAt: "" as string,
  apiBase: (import.meta.env.VITE_API_BASE || "").trim(),
});

export function useRuntimeStore() {
  const apiLabel = computed(() => (state.apiBase ? state.apiBase : "/api (Vite proxy)"));
  const lastSyncText = computed(() =>
    state.lastSuccessfulSyncAt ? `最近同步：${new Date(state.lastSuccessfulSyncAt).toLocaleString("zh-CN")}` : "尚未完成联调请求"
  );

  function markSynced() {
    state.lastSuccessfulSyncAt = new Date().toISOString();
  }

  return {
    state: readonly(state),
    apiLabel,
    lastSyncText,
    markSynced,
  };
}
