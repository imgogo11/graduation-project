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
  asset_class: string;
  file: File;
}

export function fetchImportRuns(params: ListImportRunsParams = {}) {
  return getJson<ImportRunRead[]>("/api/imports/runs", params);
}

export function fetchImportStats(params: ImportStatsParams = {}) {
  return getJson<ImportStatsRead>("/api/imports/stats", params);
}

export function uploadTradingFile(params: UploadTradingFileParams) {
  const formData = new FormData();
  formData.append("dataset_name", params.dataset_name);
  formData.append("asset_class", params.asset_class);
  formData.append("file", params.file);
  return postForm<ImportRunRead>("/api/imports/trading", formData);
}

export function deleteImportRun(runId: number) {
  return deleteJson<DeleteImportRunResponse>(`/api/imports/runs/${runId}`);
}
