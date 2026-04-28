const CATEGORY_LABELS: Record<string, string> = {
  auth: "认证",
  data_ops: "数据操作",
  analysis_access: "分析访问",
  admin_user: "用户管理",
};

const EVENT_LABELS: Record<string, string> = {
  login: "登录",
  register: "注册",
  "import_run.create": "创建导入批次",
  "import_run.delete": "删除导入批次",
  "user.update": "更新用户",
  "user.enable": "启用用户",
  "user.disable": "禁用用户",
  "user.delete": "删除用户",
  "analysis.summary.view": "查看分析摘要",
  "analysis.quality.view": "查看数据质量",
  "analysis.indicators.view": "查看指标序列",
  "analysis.risk.view": "查看风险指标",
  "analysis.anomalies.view": "查看异常检测",
  "analysis.cross_section.view": "查看横截面对比",
  "analysis.correlation.view": "查看相关性矩阵",
  "analysis.scope_compare.view": "查看范围对比",
  "algo.radar.overview.view": "查看风险雷达概览",
  "algo.radar.events.view": "查看风险事件列表",
  "algo.radar.stocks.view": "查看高风险股票画像",
  "algo.radar.calendar.view": "查看风险日历",
  "algo.radar.event_context.view": "查看风险事件上下文",
  "algo.trading.range_max_amount.query": "查询区间最大成交额",
  "algo.trading.range_kth_volume.query": "查询区间第 K 大成交量",
  "algo.trading.joint_anomaly_ranking.query": "查询联合异常排名",
};

const LEGACY_ANALYSIS_EVENT_MAP: Record<string, string> = {
  "api.trading.analysis.summary.access": "analysis.summary.view",
  "api.trading.analysis.quality.access": "analysis.quality.view",
  "api.trading.analysis.indicators.access": "analysis.indicators.view",
  "api.trading.analysis.risk.access": "analysis.risk.view",
  "api.trading.analysis.anomalies.access": "analysis.anomalies.view",
  "api.trading.analysis.cross-section.access": "analysis.cross_section.view",
  "api.trading.analysis.correlation.access": "analysis.correlation.view",
  "api.trading.analysis.compare-scopes.access": "analysis.scope_compare.view",
  "api.algo.risk-radar.overview.access": "algo.radar.overview.view",
  "api.algo.risk-radar.events.access": "algo.radar.events.view",
  "api.algo.risk-radar.stocks.access": "algo.radar.stocks.view",
  "api.algo.risk-radar.calendar.access": "algo.radar.calendar.view",
  "api.algo.risk-radar.event-context.access": "algo.radar.event_context.view",
  "api.algo.trading.range-max-amount.access": "algo.trading.range_max_amount.query",
  "api.algo.trading.range-kth-volume.access": "algo.trading.range_kth_volume.query",
  "api.algo.trading.joint-anomaly-ranking.access": "algo.trading.joint_anomaly_ranking.query",
};

export function normalizeAuditEventCode(eventType: string): string {
  const normalized = (eventType || "").trim();
  if (!normalized) {
    return "unknown";
  }
  return LEGACY_ANALYSIS_EVENT_MAP[normalized] ?? normalized;
}

export function formatAuditCategory(category: string): string {
  const normalized = (category || "").trim();
  if (!normalized) {
    return "未知分类";
  }
  return CATEGORY_LABELS[normalized] ?? "其他分类";
}

export function formatAuditEvent(eventType: string): string {
  const normalized = normalizeAuditEventCode(eventType);
  const zh = EVENT_LABELS[normalized];
  if (zh) {
    return zh;
  }
  if (normalized === "unknown") {
    return "未知事件";
  }
  return "其他事件";
}
