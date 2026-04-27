<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import * as echarts from "echarts/core";
import type { EChartsOption } from "echarts";
import { BarChart, LineChart, RadarChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";


echarts.use([BarChart, LineChart, RadarChart, ScatterChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const props = withDefaults(
  defineProps<{
    option: EChartsOption | null;
    loading?: boolean;
    height?: string;
  }>(),
  {
    loading: false,
    height: "360px",
  }
);

const chartRef = ref<HTMLDivElement | null>(null);
let chart: ReturnType<typeof echarts.init> | null = null;
let resizeObserver: ResizeObserver | null = null;

async function renderChart() {
  await nextTick();

  if (!chartRef.value) {
    return;
  }

  let instance = chart;

  if (!instance) {
    instance = echarts.init(chartRef.value);
    chart = instance;
  }

  if (!props.option) {
    instance.clear();
    return;
  }

  instance.setOption(props.option, true);
  instance.resize();
}

onMounted(async () => {
  await renderChart();

  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(chartRef.value);
  }
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});

watch(
  () => props.option,
  async () => {
    await renderChart();
  },
  { deep: true }
);

watch(
  () => props.loading,
  async () => {
    if (!props.loading) {
      await renderChart();
    }
  }
);
</script>

<template>
  <div class="chart-panel">
    <div ref="chartRef" class="chart-panel__canvas" :style="{ height }" />
    <transition name="fade">
      <div v-if="loading" class="chart-panel__overlay">
        <span class="chart-panel__spinner" />
        <span>正在加载图表数据...</span>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.chart-panel {
  position: relative;
}

.chart-panel__canvas {
  width: 100%;
}

.chart-panel__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.78);
  color: var(--text-secondary);
  backdrop-filter: blur(6px);
}

.chart-panel__spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgba(47, 111, 237, 0.18);
  border-top-color: var(--accent-blue);
  animation: spin 0.8s linear infinite;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
