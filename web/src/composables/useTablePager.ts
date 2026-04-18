import { computed, ref, watch, type ComputedRef, type Ref } from "vue";

type TableRowsSource<T> = Ref<T[]> | ComputedRef<T[]>;
type ResetTriggerSource = Ref<unknown> | ComputedRef<unknown>;

interface UseTablePagerOptions {
  initialPage?: number;
  initialPageSize?: number;
  pageSizes?: number[];
  resetTriggers?: ResetTriggerSource[];
}

export function useTablePager<T>(rows: TableRowsSource<T>, options: UseTablePagerOptions = {}) {
  const page = ref(Math.max(1, options.initialPage ?? 1));
  const pageSize = ref(Math.max(1, options.initialPageSize ?? 20));
  const pageSizes = options.pageSizes ?? [10, 20, 50, 100];

  const total = computed(() => rows.value.length);
  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
  const pagedRows = computed(() => {
    const start = (page.value - 1) * pageSize.value;
    return rows.value.slice(start, start + pageSize.value);
  });

  function setPage(next: number) {
    page.value = Math.max(1, Math.min(pageCount.value, next));
  }

  function setPageSize(next: number) {
    if (next <= 0) {
      return;
    }

    pageSize.value = next;
    page.value = 1;
  }

  function resetPage() {
    page.value = 1;
  }

  watch([total, pageSize], () => {
    if (page.value > pageCount.value) {
      page.value = pageCount.value;
    }
  });

  if (options.resetTriggers?.length) {
    watch(options.resetTriggers, resetPage);
  }

  return {
    page,
    pageSize,
    pageSizes,
    total,
    pagedRows,
    pageCount,
    setPage,
    setPageSize,
    resetPage,
  };
}
