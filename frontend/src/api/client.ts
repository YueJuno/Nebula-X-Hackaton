import type { HealthResponse } from "../types/api";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, { signal });
  if (!response.ok) {
    throw new Error(`Backend returned HTTP ${response.status}.`);
  }
  const data: unknown = await response.json();
  if (
    typeof data !== "object" || data === null ||
    !("status" in data) || data.status !== "ok" ||
    !("service" in data) || typeof data.service !== "string"
  ) {
    throw new Error("Backend returned an unexpected health response.");
  }
  return { status: data.status, service: data.service };
}
