<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import type { EChartsOption } from "echarts";

import { fetchHealth } from "@/api/health";
import { fetchImportRuns, fetchImportStats } from "@/api/imports";
import type { HealthResponse, ImportRunRead, ImportStatsRead } from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useAuthStore } from "@/stores/auth";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDateTime, getErrorMessage, toStatusTagType } from "@/utils/format";


const runtime = useRuntimeStore();
const auth = useAuthStore();
const health = ref<HealthResponse | null>(null);
const stats = ref<ImportStatsRead | null>(null);
const importRuns = ref<ImportRunRead[]>([]);
const loading = ref(false);
const error = ref("");
const ownerFilterInput = ref("");

const appliedOwnerUserId = computed(() => {
  if (!auth.isAdmin.value) {
    return undefined;
  }

  const parsed = Number(ownerFilterInput.value.trim());
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
});

const summaryCards = computed<
  Array<{ label: string; value: string; hint: string; tone: "neutral" | "teal" | "orange" | "berry" }>
>(() => [
  {
    label: "总导入批次",
    value: String(stats.value?.total_runs ?? 0),
    hint: auth.isAdmin.value ? "管理员视角可查看全站或按用户过滤" : "仅统计当前登录用户的数据",
    tone: "teal",
  },
  {
    label: "成功批次",
    value: String(stats.value?.completed_runs ?? 0),
    hint: "上传成功并完成解析入库的历史导入次数",
    tone: "orange",
  },
  {
    label: "累计记录数",
    value: formatCompact(stats.value?.total_records ?? null, 2),
    hint: "默认不包含已删除的导入批次",
    tone: "berry",
  },
  {
    label: "活跃数据集",
    value: String(stats.value?.active_datasets ?? 0),
    hint: "当前可见范围内去重后的数据集名称数量",
    tone: "neutral",
  },
]);

const monthlyChartOption = computed<EChartsOption | null>(() => {
  if (!stats.value?.monthly_imports.length) {
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
      left: 44,
      right: 24,
      top: 54,
      bottom: 28,
    },
    xAxis: {
      type: "category",
      data: stats.value.monthly_imports.map((item) => item.month),
      axisLabel: { color: "#59676b" },
    },
    yAxis: [
      {
        type: "value",
        name: "批次",
        axisLabel: { color: "#59676b" },
        splitLine: {
          lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
        },
      },
      {
        type: "value",
        name: "记录数",
        axisLabel: { color: "#59676b" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "line",
        name: "导入批次",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: "#0b8f8c" },
        areaStyle: {
          color: "rgba(11, 143, 140, 0.12)",
        },
        data: stats.value.monthly_imports.map((item) => item.runs),
      },
      {
        type: "bar",
        name: "导入记录数",
        yAxisIndex: 1,
        barMaxWidth: 22,
        itemStyle: {
          color: "#f28c28",
          borderRadius: [6, 6, 0, 0],
        },
        data: stats.value.monthly_imports.map((item) => item.records),
      },
    ],
  };
});

async function loadOverview() {
  loading.value = true;
  error.value = "";

  try {
    const [healthResponse, statsResponse, importRunResponse] = await Promise.all([
      fetchHealth(),
      fetchImportStats({ owner_user_id: appliedOwnerUserId.value }),
      fetchImportRuns({
        limit: 12,
        owner_user_id: appliedOwnerUserId.value,
      }),
    ]);
    health.value = healthResponse;
    stats.value = statsResponse;
    importRuns.value = importRunResponse;
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

onMounted(loadOverview);
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Overview</div>
        <h2 class="page__title">上传历史、权限范围和系统状态一屏查看</h2>
        <p class="page__subtitle">
          这里聚焦“我导入了什么、系统现在是否可用、最近的数据历史是什么样子”。管理员登录后，还能切换到按用户过滤的全站视角。
        </p>
      </div>
      <div class="page__actions">
        <el-input
          v-if="auth.isAdmin.value"
          v-model="ownerFilterInput"
          placeholder="管理员可按用户 ID 过滤"
          clearable
          class="overview-owner-filter"
        />
        <el-button type="primary" :loading="loading" @click="loadOverview">刷新总览</el-button>
      </div>
    </section>

    <el-alert
      v-if="error"
      title="总览数据拉取失败"
      type="error"
      :description="error"
      show-icon
      :closable="false"
    />

    <section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in summaryCards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="系统健康状态" description="用于确认后端服务和数据库是否在线。">
        <div v-if="health" class="overview-health">
          <div class="overview-health__line">
            <span class="muted">状态</span>
            <el-tag :type="toStatusTagType(health.status)" effect="dark">{{ health.status }}</el-tag>
          </div>
          <div class="overview-health__line">
            <span class="muted">环境</span>
            <strong>{{ health.environment }}</strong>
          </div>
          <div class="overview-health__line">
            <span class="muted">数据库</span>
            <strong>{{ health.database_ok ? "连接正常" : "连接失败" }}</strong>
          </div>
          <div class="overview-health__detail">{{ health.detail }}</div>
        </div>
        <EmptyState
          v-else
          title="等待健康检查结果"
          description="点击刷新后会展示当前后端和数据库的可用状态。"
        />
      </PanelCard>

      <PanelCard title="按月导入趋势" description="默认按当前可见范围统计，不包含已删除的批次。">
        <EChartPanel v-if="monthlyChartOption" :option="monthlyChartOption" :loading="loading" height="340px" />
        <EmptyState
          v-else
          title="还没有导入趋势数据"
          description="上传交易数据文件后，这里会按月份汇总显示导入批次和记录数。"
        />
      </PanelCard>
    </section>

    <PanelCard
      v-if="auth.isAdmin.value"
      title="管理员用户统计"
      description="管理员可查看当前可见范围内，不同用户的导入批次和记录数概览。"
    >
      <el-table v-if="stats?.owner_summaries.length" :data="stats.owner_summaries" stripe>
        <el-table-column prop="owner_user_id" label="User ID" width="120" />
        <el-table-column prop="owner_username" label="Username" min-width="180" />
        <el-table-column prop="runs" label="Runs" width="120" />
        <el-table-column prop="records" label="Records" min-width="140" />
      </el-table>
      <EmptyState
        v-else
        title="当前没有可展示的用户汇总"
        description="如果管理员筛选了某个用户，或还没有导入数据，这里会显示为空状态。"
      />
    </PanelCard>

    <PanelCard title="最近导入记录" description="用于回看数据集、归属用户、导入状态和时间线。">
      <template #actions>
        <span class="pill">{{ importRuns.length }} 条记录</span>
      </template>

      <el-table v-if="importRuns.length" :data="importRuns" stripe>
        <el-table-column prop="display_id" label="ID" width="90" />
        <el-table-column v-if="auth.isAdmin.value" prop="owner_username" label="Owner" min-width="140" />
        <el-table-column prop="dataset_name" label="Dataset" min-width="180" />
        <el-table-column prop="asset_class" label="Asset" width="110" />
        <el-table-column prop="file_format" label="Format" width="100" />
        <el-table-column label="Status" width="110">
          <template #default="{ row }">
            <el-tag :type="toStatusTagType(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Started At" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Completed At" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.completed_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="record_count" label="Records" width="110" />
      </el-table>

      <EmptyState
        v-else
        title="还没有读取到导入记录"
        description="先在交易分析页面上传一份 CSV 或 XLSX 文件，这里就会开始累积历史导入记录。"
      />
    </PanelCard>
  </div>
</template>

<style scoped>
.overview-owner-filter {
  width: min(240px, 100%);
}

.overview-health {
  display: grid;
  gap: 14px;
}

.overview-health__line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(89, 103, 107, 0.18);
}

.overview-health__detail {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(11, 143, 140, 0.06);
  color: var(--text-secondary);
  line-height: 1.7;
}
</style>
