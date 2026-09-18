import { API_BASE_URL } from "./client";
import type { Capabilities, Dataset, Instance, Run } from "../types/scheduling";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem("access_token");
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    ...options, signal: AbortSignal.timeout(30000),
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem("access_token");
      window.dispatchEvent(new Event("auth:expired"));
    }
    const detail = data.detail;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail?.errors) ? detail.errors.join("\n") : "Request failed. Check the uploaded files and backend configuration.";
    throw new Error(message);
  }
  return data as T;
}

export const getCapabilities = () => request<Capabilities>("/runs/capabilities");
export const listDatasets = () => request<Dataset[]>("/instances");
export const getDataset = (id: string) => request<Dataset & { instance: Instance }>(`/instances/${id}`);
export const listRuns = () => request<Run[]>("/runs");
export const getRun = (id: string) => request<Run>(`/runs/${id}`);
export const createRun = (datasetId: string, scenario: string) => request<Run>("/runs", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id: datasetId, scenario }),
});
export function uploadDataset(name: string, files: File[]) {
  const body = new FormData();
  body.append("name", name);
  files.forEach(file => body.append("files", file));
  return request<Dataset>("/instances", { method: "POST", body });
}
export async function downloadRunFile(run: Run, kind: "report" | "submission") {
  const token = sessionStorage.getItem("access_token");
  const response = await fetch(`${API_BASE_URL}/api/runs/${run.id}/${kind}`, {
    headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error("Download unavailable. Check the run status or sign in again.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = kind === "report" ? `report-${run.id}.json` : `scenario-${run.scenario}-${run.id}.zip`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
