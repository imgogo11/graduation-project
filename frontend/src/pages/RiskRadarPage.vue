<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";

import { fetchImportRuns } from "@/api/imports";
import {
  fetchAlgoIndexStatus,
  fetchRiskRadarCalendar,
  fetchRiskRadarEventContext,
  fetchRiskRadarEvents,
  fetchRiskRadarInstruments,
  fetchRiskRadarOverview,
  rebuildAlgoIndex,
} from "@/api/riskRadar";
import type {
  AlgoIndexStatusRead,
  ImportRunRead,
  TradingRiskRadarCalendarDayRead,
  TradingRiskRadarEventContextRead,
  TradingRiskRadarEventRead,
  TradingRiskRadarOverviewRead,
  TradingInstrumentRiskProfileRead,
} from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useRuntimeStore } from "@/stores/runtime";
import {
  formatCompact,
  formatDate,
  formatDateTime,
  formatNumberish,
  formatPercent,
  getErrorMessage,
  toNumber,
  toStatusTagType,
} from "@/utils/format";


const runtime = useRuntimeStore();
const loadingRuns = ref(false);
const loadingRadar = ref(false);
const rebuilding = ref(false);
const error = ref("");
const importRuns = ref<ImportRunRead[]>([]);
const indexStatus = ref<AlgoIndexStatusRead | null>(null);
const overview = ref<TradingRiskRadarOverviewRead | null>(null);
const events = ref<TradingRiskRadarEventRead[]>([]);
const instrumentProfiles = ref<TradingInstrumentRiskProfileRead[]>([]);
const calendarRows = ref<TradingRiskRadarCalendarDayRead[]>([]);
const eventContext = ref<TradingRiskRadarEventContextRead | null>(null);
const selectedEventKey = ref("");

const filters = reactive({
  importRunId: undefined as number | undefined,
  startDate: "",
  endDate: "",
  severity: "",
  topNInput: "50",
});

const severityOptions = [
  { label: "全部严重度", value: "" },
  { label: "medium", value: "medium" },
  { label: "high", value: "high" },
  { label: "critical", value: "critical" },
];

const statusCards = computed(() => [
  {
    label: "索引状态",
    value: indexStatus.value?.status ?? "--",
    hint: indexStatus.value?.build_completed_at ? `完成于 ${formatDateTime(indexStatus.value.build_completed_at)}` : "等待选择批次",
    tone: "teal" as const,
  },
  {
    label: "异常事件数",
    value: String(overview.value?.total_events ?? 0),
    hint: `事件窗口 ${overview.value?.lookback_window ?? 20} 日`,
    tone: "orange" as const,
  },
  {
    label: "受影响标的",
    value: String(overview.value?.impacted_instrument_count ?? 0),
    hint: indexStatus.value?.instrument_count ? `${indexStatus.value.instrument_count} 个已建索引标的` : "等待索引完成",
    tone: "berry" as const,
  },
  {
    label: "Critical 事件",
    value: String(overview.value?.critical_count ?? 0),
    hint: overview.value ? `${overview.value.high_count} 个 high / ${overview.value.medium_count} 个 medium` : "等待雷达结果",
    tone: "neutral" as const,
  },
]);

const radarScatterOption = computed<EChartsOption | null>(() => {
  if (!events.value.length) {
    return null;
  }

  const severityGroups = {
    medium: events.value.filter((item) => item.severity === "medium"),
    high: events.value.filter((item) => item.severity === "high"),
    critical: events.value.filter((item) => item.severity === "critical"),
  };

  const buildSeries = (rows: TradingRiskRadarEventRead[], name: string, color: string) => ({
    type: "scatter" as const,
    name,
    itemStyle: { color },
    data: rows.map((item) => ({
      value: [
        toNumber(item.return_z20),
        toNumber(item.volume_ratio20),
        toNumber(item.amplitude_ratio20),
        item.instrument_code,
        item.trade_date,
      ],
      symbolSize: 10 + Math.min(toNumber(item.amplitude_ratio20) * 6, 26),
    })),
  });

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(24, 50, 47, 0.9)",
      borderWidth: 0,
      textStyle: { color: "#fffdf7" },
      formatter: (params) => {
        const point = Array.isArray((params as { value?: unknown }).value)
          ? ((params as { value: Array<string | number> }).value ?? [])
          : [];
        const [returnZ, volumeRatio, amplitudeRatio, instrumentCode, tradeDate] = point;
        return [
          `${instrumentCode} · ${tradeDate}`,
          `Return Z20: ${Number(returnZ).toFixed(2)}`,
          `Volume Ratio20: ${Number(volumeRatio).toFixed(2)}`,
          `Amplitude Ratio20: ${Number(amplitudeRatio).toFixed(2)}`,
        ].join("<br/>");
      },
    },
    legend: {
      top: 0,
      textStyle: { color: "#59676b" },
    },
    grid: {
      left: 72,
      right: 40,
      top: 56,
      bottom: 68,
      containLabel: true,
    },
    xAxis: {
      type: "value",
      name: "Return Z20",
      nameLocation: "middle",
      nameGap: 36,
      axisLabel: { color: "#59676b" },
      splitLine: {
        lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
      },
    },
    yAxis: {
      type: "value",
      name: "Volume Ratio20",
      nameLocation: "middle",
      nameGap: 56,
      axisLabel: { color: "#59676b" },
      splitLine: {
        lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
      },
    },
    series: [
      buildSeries(severityGroups.medium, "medium", "#f2b233"),
      buildSeries(severityGroups.high, "high", "#f28c28"),
      buildSeries(severityGroups.critical, "critical", "#b9524f"),
    ],
  };
});

const calendarChartOption = computed<EChartsOption | null>(() => {
  if (!calendarRows.value.length) {
    return null;
  }

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(24, 50, 47, 0.9)",
      borderWidth: 0,
      textStyle: { color: "#fffdf7" },
    },
    legend: {
      top: 0,
      textStyle: { color: "#59676b" },
    },
    grid: {
      left: 60,
      right: 52,
      top: 56,
      bottom: 72,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: calendarRows.value.map((item) => item.trade_date),
      axisLabel: { color: "#59676b", rotate: 35, margin: 14, hideOverlap: false },
    },
    yAxis: [
      {
        type: "value",
        name: "事件数",
        axisLabel: { color: "#59676b" },
        splitLine: {
          lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
        },
      },
      {
        type: "value",
        name: "最大百分位",
        axisLabel: { color: "#59676b" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "bar",
        name: "事件数",
        barMaxWidth: 18,
        itemStyle: {
          color: "#0b8f8c",
          borderRadius: [6, 6, 0, 0],
        },
        data: calendarRows.value.map((item) => item.event_count),
      },
      {
        type: "line",
        name: "最大百分位",
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        lineStyle: {
          width: 3,
          color: "#b9524f",
        },
        data: calendarRows.value.map((item) => toNumber(item.max_joint_percentile)),
      },
    ],
  };
});

function parseTopN() {
  const normalized = filters.topNInput.trim();
  if (!normalized) {
    return undefined;
  }
  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("Top N 必须是正整数，留空则表示不限制。");
  }
  return parsed;
}

function clearRadarData() {
  overview.value = null;
  events.value = [];
  instrumentProfiles.value = [];
  calendarRows.value = [];
  eventContext.value = null;
  selectedEventKey.value = "";
}

async function loadRuns(preferredRunId?: number) {
  loadingRuns.value = true;
  error.value = "";
  try {
    const rows = await fetchImportRuns({ limit: 50 });
    importRuns.value = rows;
    if (!rows.length) {
      filters.importRunId = undefined;
      indexStatus.value = null;
      clearRadarData();
      return;
    }

    const nextRunId =
      preferredRunId && rows.some((item) => item.id === preferredRunId)
        ? preferredRunId
        : filters.importRunId && rows.some((item) => item.id === filters.importRunId)
          ? filters.importRunId
          : rows[0].id;
    filters.importRunId = nextRunId;
    await loadRadar();
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingRuns.value = false;
  }
}

async function loadRadar() {
  if (!filters.importRunId) {
    indexStatus.value = null;
    clearRadarData();
    return;
  }

  loadingRadar.value = true;
  error.value = "";
  try {
    indexStatus.value = await fetchAlgoIndexStatus({ import_run_id: filters.importRunId });
    if (!indexStatus.value.is_ready) {
      clearRadarData();
      return;
    }

    const topN = parseTopN();
    const [overviewPayload, eventPayload, instrumentPayload, calendarPayload] = await Promise.all([
      fetchRiskRadarOverview({ import_run_id: filters.importRunId }),
      fetchRiskRadarEvents({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        severity: filters.severity || undefined,
        top_n: topN,
      }),
      fetchRiskRadarInstruments({
        import_run_id: filters.importRunId,
        severity: filters.severity || undefined,
        top_n: 20,
      }),
      fetchRiskRadarCalendar({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
      }),
    ]);

    overview.value = overviewPayload;
    events.value = eventPayload.rows;
    instrumentProfiles.value = instrumentPayload.rows;
    calendarRows.value = calendarPayload.rows;

    if (events.value.length) {
      await loadEventContext(events.value[0]);
    } else {
      eventContext.value = null;
      selectedEventKey.value = "";
    }
  } catch (err) {
    clearRadarData();
    error.value = getErrorMessage(err);
  } finally {
    loadingRadar.value = false;
  }
}

async function loadEventContext(event: TradingRiskRadarEventRead) {
  if (!filters.importRunId) {
    return;
  }

  try {
    eventContext.value = await fetchRiskRadarEventContext({
      import_run_id: filters.importRunId,
      instrument_code: event.instrument_code,
      trade_date: event.trade_date,
    });
    selectedEventKey.value = `${event.instrument_code}:${event.trade_date}`;
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

function radarEventRowClassName(payload: { row: TradingRiskRadarEventRead }) {
  return selectedEventKey.value === `${payload.row.instrument_code}:${payload.row.trade_date}` ? "is-current" : "";
}

async function handleRebuild() {
  if (!filters.importRunId) {
    return;
  }

  rebuilding.value = true;
  error.value = "";
  try {
    indexStatus.value = await rebuildAlgoIndex(filters.importRunId);
    await loadRadar();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    rebuilding.value = false;
  }
}

onMounted(() => {
  void loadRuns();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Risk Radar</div>
        <h2 class="page__title">3 维联合异常风险雷达</h2>
        <p class="page__subtitle">
          导入完成后，系统会自动构建风险雷达索引，并从价格冲击、成交量放大、振幅异常三个维度找出真正稀有的风险事件。
        </p>
      </div>
      <div class="page__actions">
        <el-button :loading="loadingRuns || loadingRadar" @click="loadRuns(filters.importRunId)">刷新雷达</el-button>
        <el-button type="primary" plain :loading="rebuilding" @click="handleRebuild">重建索引</el-button>
      </div>
    </section>

    <el-alert
      v-if="error"
      title="风险雷达加载失败"
      type="error"
      :description="error"
      show-icon
      :closable="false"
    />

    <PanelCard title="雷达筛选" description="选择一个导入批次后，系统会先检查算法索引状态，再加载风险雷达结果。">
      <el-form class="radar-filters" label-position="top">
        <el-form-item label="导入批次">
          <el-select v-model="filters.importRunId" placeholder="选择批次" class="radar-filters__control" @change="loadRadar">
            <el-option
              v-for="item in importRuns"
              :key="item.id"
              :label="`#${item.display_id} · ${item.dataset_name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="filters.startDate" type="date" value-format="YYYY-MM-DD" class="radar-filters__control" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="filters.endDate" type="date" value-format="YYYY-MM-DD" class="radar-filters__control" />
        </el-form-item>
        <el-form-item label="严重度">
          <el-select v-model="filters.severity" class="radar-filters__control">
            <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="Top N">
          <el-input v-model="filters.topNInput" placeholder="默认 50" class="radar-filters__control" />
        </el-form-item>
      </el-form>
      <div class="radar-filters__actions">
        <el-button type="primary" :loading="loadingRadar" @click="loadRadar">应用筛选</el-button>
      </div>
    </PanelCard>

    <section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in statusCards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <PanelCard title="索引状态" description="Risk Radar 页面只有在索引 ready 后才会继续加载详细结果。">
      <el-descriptions v-if="indexStatus" :column="2" border>
        <el-descriptions-item label="状态">
          <el-tag :type="toStatusTagType(indexStatus.status)" effect="plain">{{ indexStatus.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="复用次数">
          {{ indexStatus.reuse_count }}
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">
          {{ formatDateTime(indexStatus.build_started_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="完成时间">
          {{ formatDateTime(indexStatus.build_completed_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="构建耗时">
          {{ indexStatus.build_duration_ms === null ? "--" : `${indexStatus.build_duration_ms} ms` }}
        </el-descriptions-item>
        <el-descriptions-item label="事件数量">
          {{ indexStatus.event_count ?? "--" }}
        </el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="indexStatus?.last_error"
        title="最近一次构建失败"
        type="error"
        :closable="false"
        :description="indexStatus.last_error"
      />
      <EmptyState
        v-if="!indexStatus"
        title="等待选择批次"
        description="先选择一个导入批次，然后这里会展示索引构建状态。"
      />
    </PanelCard>

    <template v-if="indexStatus?.is_ready">
      <section class="page__grid page__grid--double">
        <PanelCard title="异常分布散点" description="横轴为价格冲击，纵轴为成交量放大，点大小映射振幅异常。">
          <EChartPanel v-if="radarScatterOption" :option="radarScatterOption" :loading="loadingRadar" height="380px" />
          <EmptyState v-else title="暂无异常事件" description="当前筛选范围内还没有满足阈值的雷达事件。" />
        </PanelCard>

        <PanelCard title="系统性冲击时间带" description="按日期聚合异常事件数，并叠加当日最大联合百分位。">
          <EChartPanel v-if="calendarChartOption" :option="calendarChartOption" :loading="loadingRadar" height="380px" />
          <EmptyState v-else title="暂无日期聚合结果" description="索引 ready 后，这里会显示按日期汇总的异常分布。" />
        </PanelCard>
      </section>

      <section class="page__grid page__grid--double">
        <PanelCard title="批次总览" description="优先展示最异常的标的和最密集的异常日期。">
          <div v-if="overview" class="radar-stack">
            <div>
              <div class="radar-subtitle">最异常标的</div>
              <div class="radar-tags">
                <span v-for="item in overview.top_instruments" :key="`top-inst-${item.instrument_code}`" class="pill">
                  {{ item.instrument_code }} · {{ item.event_count }} 次
                </span>
              </div>
            </div>
            <div>
              <div class="radar-subtitle">最密集日期</div>
              <div class="radar-tags">
                <span v-for="item in overview.busiest_dates" :key="`busy-day-${item.trade_date}`" class="pill">
                  {{ item.trade_date }} · {{ item.event_count }} 条
                </span>
              </div>
            </div>
          </div>
          <EmptyState v-else title="暂无批次总览" description="索引 ready 后，这里会展示该批次的整体风险画像。" />
        </PanelCard>

        <PanelCard title="事件钻取" description="点击异常榜单中的某一行后，这里会解释该事件在不同窗口中的位置。">
          <div v-if="eventContext" class="radar-stack">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="标的">{{ eventContext.event.instrument_code }}</el-descriptions-item>
              <el-descriptions-item label="日期">{{ eventContext.event.trade_date }}</el-descriptions-item>
              <el-descriptions-item label="严重度">
                <el-tag :type="toStatusTagType(eventContext.event.severity)" effect="plain">{{ eventContext.event.severity }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="主因">{{ eventContext.event.cause_label }}</el-descriptions-item>
            </el-descriptions>

            <div>
              <div class="radar-subtitle">成交量窗口分位</div>
              <el-table :data="eventContext.volume_windows" stripe class="data-table" max-height="420">
                <el-table-column prop="window_days" label="窗口天数" width="100" />
                <el-table-column label="当前值" min-width="110">
                  <template #default="{ row }">{{ formatCompact(row.current_value, 2) }}</template>
                </el-table-column>
                <el-table-column label="精确百分位" min-width="120">
                  <template #default="{ row }">{{ formatPercent(row.exact_percentile, 2) }}</template>
                </el-table-column>
                <el-table-column label="P50 / P90 / P95" min-width="220">
                  <template #default="{ row }">
                    {{ formatCompact(row.p50, 2) }} / {{ formatCompact(row.p90, 2) }} / {{ formatCompact(row.p95, 2) }}
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div>
              <div class="radar-subtitle">振幅窗口分位</div>
              <el-table :data="eventContext.amplitude_windows" stripe class="data-table" max-height="420">
                <el-table-column prop="window_days" label="窗口天数" width="100" />
                <el-table-column label="当前值" min-width="110">
                  <template #default="{ row }">{{ formatNumberish(row.current_value, 4) }}</template>
                </el-table-column>
                <el-table-column label="精确百分位" min-width="120">
                  <template #default="{ row }">{{ formatPercent(row.exact_percentile, 2) }}</template>
                </el-table-column>
                <el-table-column label="P50 / P90 / P95" min-width="220">
                  <template #default="{ row }">
                    {{ formatNumberish(row.p50, 4) }} / {{ formatNumberish(row.p90, 4) }} / {{ formatNumberish(row.p95, 4) }}
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div>
              <div class="radar-subtitle">前后窗口分布变化</div>
              <el-table :data="eventContext.distribution_changes" stripe class="data-table" max-height="420">
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column label="Before" min-width="220">
                  <template #default="{ row }">
                    {{ formatNumberish(row.before_median, 4) }} / {{ formatNumberish(row.before_p90, 4) }} / {{ formatNumberish(row.before_p95, 4) }}
                  </template>
                </el-table-column>
                <el-table-column label="After" min-width="220">
                  <template #default="{ row }">
                    {{ formatNumberish(row.after_median, 4) }} / {{ formatNumberish(row.after_p90, 4) }} / {{ formatNumberish(row.after_p95, 4) }}
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div v-if="eventContext.local_amount_peak">
              <div class="radar-subtitle">事件附近成交额峰值</div>
              <el-alert
                type="info"
                :closable="false"
                :title="`峰值成交额 ${formatCompact(eventContext.local_amount_peak.peak_amount, 2)}`"
                :description="`${eventContext.local_amount_peak.start_date} ~ ${eventContext.local_amount_peak.end_date}`"
              />
              <div class="radar-tags">
                <span v-for="item in eventContext.local_amount_peak.peak_dates" :key="`peak-date-${item.trade_date}`" class="pill">
                  {{ item.trade_date }}
                </span>
              </div>
            </div>
          </div>
          <EmptyState
            v-else
            title="等待选择异常事件"
            description="点击左侧异常榜单中的某一行后，这里会展示窗口分位、分布变化和成交额峰值解释。"
          />
        </PanelCard>
      </section>

      <section class="page__grid page__grid--double">
        <PanelCard title="异常事件榜单" description="按联合百分位倒序排列，点击某一行可查看事件上下文。">
          <el-table
            v-if="events.length"
            :data="events"
            stripe
            class="data-table"
            max-height="420"
            highlight-current-row
            :row-class-name="radarEventRowClassName"
            @row-click="loadEventContext"
          >
            <el-table-column prop="trade_date" label="Date" width="120" />
            <el-table-column prop="instrument_code" label="Code" min-width="120" />
            <el-table-column prop="cause_label" label="Cause" min-width="160" />
            <el-table-column label="Severity" width="110">
              <template #default="{ row }">
                <el-tag :type="toStatusTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Joint Percentile" min-width="130">
              <template #default="{ row }">{{ formatPercent(row.joint_percentile, 2) }}</template>
            </el-table-column>
            <el-table-column label="Return Z20" min-width="110">
              <template #default="{ row }">{{ formatNumberish(row.return_z20, 2) }}</template>
            </el-table-column>
            <el-table-column label="Volume Ratio20" min-width="130">
              <template #default="{ row }">{{ formatNumberish(row.volume_ratio20, 2) }}</template>
            </el-table-column>
            <el-table-column label="Amplitude Ratio20" min-width="140">
              <template #default="{ row }">{{ formatNumberish(row.amplitude_ratio20, 2) }}</template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="暂无异常榜单" description="调整日期或严重度后，如果仍无结果，说明当前范围内没有命中事件。" />
        </PanelCard>

        <PanelCard title="标的风险画像" description="用于识别哪几个标的在当前批次中最容易反复触发异常。">
          <el-table v-if="instrumentProfiles.length" :data="instrumentProfiles" stripe class="data-table" max-height="420">
            <el-table-column prop="instrument_code" label="Code" min-width="120" />
            <el-table-column prop="event_count" label="事件数" width="90" />
            <el-table-column label="最高百分位" min-width="120">
              <template #default="{ row }">{{ formatPercent(row.max_joint_percentile, 2) }}</template>
            </el-table-column>
            <el-table-column label="平均百分位" min-width="120">
              <template #default="{ row }">{{ formatPercent(row.avg_joint_percentile, 2) }}</template>
            </el-table-column>
            <el-table-column prop="latest_event_date" label="最近异常" min-width="120" />
            <el-table-column prop="top_event_severity" label="最高级别" min-width="110" />
          </el-table>
          <EmptyState v-else title="暂无标的画像" description="风险雷达构建完成后，这里会按标的聚合异常频次和严重度。" />
        </PanelCard>
      </section>

      <PanelCard title="日期聚合表" description="识别市场级冲击日，看某一天有多少标的一起异常。">
        <el-table v-if="calendarRows.length" :data="calendarRows" stripe class="data-table" max-height="420">
          <el-table-column prop="trade_date" label="Date" min-width="120" />
          <el-table-column prop="event_count" label="事件数" width="100" />
          <el-table-column prop="impacted_instrument_count" label="标的数" width="100" />
          <el-table-column prop="critical_count" label="Critical" width="100" />
          <el-table-column prop="high_count" label="High" width="90" />
          <el-table-column prop="medium_count" label="Medium" width="100" />
          <el-table-column label="最大百分位" min-width="120">
            <template #default="{ row }">{{ formatPercent(row.max_joint_percentile, 2) }}</template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="暂无日期聚合结果" description="索引 ready 后，这里会展示系统性冲击日的聚合结果。" />
      </PanelCard>
    </template>

    <EmptyState
      v-else-if="filters.importRunId"
      title="索引尚未就绪"
      :description="indexStatus?.last_error || `当前索引状态为 ${indexStatus?.status ?? 'pending'}，可以稍后刷新，或手动点击“重建索引”。`"
    />
  </div>
</template>

<style scoped>
.radar-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.radar-filters :deep(.el-form-item) {
  margin-bottom: 0;
}

.radar-filters__control {
  width: 100%;
}

.radar-filters__actions {
  margin-top: 14px;
}

.radar-stack {
  display: grid;
  gap: 18px;
}

.radar-subtitle {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.radar-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
