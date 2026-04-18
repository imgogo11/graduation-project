import { deleteJson, getJson, postForm } from "@/api/http";
import type { DeleteImportRunResponse, ImportRunRead, ImportStatsRead } from "@/api/types";


export interface ListImportRunsParams {
  limit?: number;
  owner_user_id?: number;
}

export interface ImportStatsParams {
  owner_user_id?: number;
}

export interface UploadTradingFileParams {
  dataset_name: string;
  file: File;
}

function ensureArray<T>(payload: T[] | T | null | undefined) {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (payload === null || payload === undefined) {
    return [] as T[];
  }

  return [payload];
}

export async function fetchImportRuns(params: ListImportRunsParams = {}) {
  const payload = await getJson<ImportRunRead[] | ImportRunRead | null>("/api/imports/runs", params);
  return ensureArray(payload);
}

export function fetchImportStats(params: ImportStatsParams = {}) {
  return getJson<ImportStatsRead>("/api/imports/stats", params);
}

export function uploadTradingFile(params: UploadTradingFileParams) {
  const formData = new FormData();
  formData.append("dataset_name", params.dataset_name);
  formData.append("file", params.file);
  return postForm<ImportRunRead>("/api/imports/trading", formData);
}

export function deleteImportRun(runId: number) {
  return deleteJson<DeleteImportRunResponse>(`/api/imports/runs/${runId}`);
}
