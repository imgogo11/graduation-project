const STATUS_TEXT_MAP: Record<string, string> = {
  completed: "已完成",
  complete: "已完成",
  failed: "失败",
  fail: "失败",
  pending: "待处理",
  ready: "就绪",
  building: "构建中",
  running: "运行中",
  ok: "正常",
  degraded: "降级",
  success: "成功",
  context: "上下文",
};

const ROLE_TEXT_MAP: Record<string, string> = {
  admin: "管理员",
  user: "普通用户",
};

const SEVERITY_TEXT_MAP: Record<string, string> = {
  critical: "严重",
  high: "高",
  medium: "中",
  low: "低",
};

const ALGO_METHOD_TEXT_MAP: Record<string, string> = {
  persistent_segment_tree: "精确算法",
  t_digest: "近似算法",
};

export const TECHNICAL_TEXT = {
  returnZ20: "收益Z分数(Return Z20)",
  volumeRatio20: "量比(Volume Ratio20)",
  amplitudeRatio20: "振幅比(Amplitude Ratio20)",
  close: "收盘价(Close)",
  price: "价格(Price)",
  volume: "成交量(Volume)",
  ma5: "5日均线(MA5)",
  ma20: "20日均线(MA20)",
  macd: "平滑异同均线(MACD)",
  rsi14: "相对强弱指标(RSI14)",
  atr14: "平均真实波幅(ATR14)",
  ohc: "开/高/收(O/H/C)",
} as const;

function normalizeDisplayKey(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  return String(value).trim().toLowerCase();
}

function mapByNormalized(raw: unknown, map: Record<string, string>) {
  const normalized = normalizeDisplayKey(raw);
  if (!normalized) {
    return "--";
  }

  return map[normalized] || String(raw);
}

export function formatStatusText(status: unknown) {
  return mapByNormalized(status, STATUS_TEXT_MAP);
}

export function formatRoleText(role: unknown) {
  return mapByNormalized(role, ROLE_TEXT_MAP);
}

export function formatSeverityText(severity: unknown) {
  return mapByNormalized(severity, SEVERITY_TEXT_MAP);
}

export function formatAlgoMethodText(method: unknown) {
  return mapByNormalized(method, ALGO_METHOD_TEXT_MAP);
}
