import type { NumericLike } from "@/api/types";


export function toNumber(value: NumericLike, fallback = 0) {
  if (value === null || value === "") {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function formatNumberish(value: NumericLike, digits = 2) {
  if (value === null || value === "") {
    return "--";
  }

  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(toNumber(value));
}

export function formatCompact(value: NumericLike, digits = 1) {
  if (value === null || value === "") {
    return "--";
  }

  return new Intl.NumberFormat("zh-CN", {
    notation: "compact",
    maximumFractionDigits: digits,
  }).format(toNumber(value));
}

export function formatPercent(value: NumericLike, digits = 2) {
  if (value === null || value === "") {
    return "--";
  }

  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(toNumber(value));
}

export function formatDate(value: string | null | undefined) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleDateString("zh-CN");
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN");
}

export function toStatusTagType(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("critical")) {
    return "danger" as const;
  }
  if (normalized.includes("high")) {
    return "danger" as const;
  }
  if (normalized.includes("medium") || normalized.includes("warning")) {
    return "warning" as const;
  }
  if (normalized.includes("complete") || normalized.includes("ok")) {
    return "success" as const;
  }
  if (normalized.includes("running")) {
    return "warning" as const;
  }
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("degraded")) {
    return "danger" as const;
  }
  return "info" as const;
}

export function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "请求失败，请检查后端服务和数据导入状态。";
}
