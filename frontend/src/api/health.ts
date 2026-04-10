import { getJson } from "@/api/http";
import type { HealthResponse } from "@/api/types";


export function fetchHealth() {
  return getJson<HealthResponse>("/api/health");
}
