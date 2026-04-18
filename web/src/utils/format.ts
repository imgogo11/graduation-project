import type { NumericLike } from "@/api/types";


export const DATA_INSUFFICIENT_PREFIX = "数据不足分析";

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

export function toStatusTagType(status: unknown) {
  const normalized =
    typeof status === "string"
      ? status.toLowerCase()
      : status === null || status === undefined
        ? ""
        : String(status).toLowerCase();

  if (!normalized) {
    return "info" as const;
  }

  if (normalized.includes("critical") || normalized.includes("high")) {
    return "error" as const;
  }
  if (normalized.includes("medium") || normalized.includes("warning") || normalized.includes("running")) {
    return "warning" as const;
  }
  if (normalized.includes("complete") || normalized.includes("ok") || normalized.includes("ready")) {
    return "success" as const;
  }
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("degraded")) {
    return "error" as const;
  }
  return "info" as const;
}

export function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "请求失败，请检查后端服务和数据导入状态。";
}

export function isDataInsufficientMessage(message: string) {
  return message.startsWith(DATA_INSUFFICIENT_PREFIX);
}
