// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { Simulate } from "react-dom/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as auth from "./api/auth";
import * as scheduling from "./api/scheduling";
import type { Dataset, Instance, Run } from "./types/scheduling";
import type { AuthResponse } from "./types/auth";

vi.mock("./api/auth", () => ({ authenticate: vi.fn(), getCurrentUser: vi.fn(), AuthApiError: class extends Error {} }));
vi.mock("./api/scheduling", () => ({
  createRun: vi.fn(), downloadRunFile: vi.fn(), getCapabilities: vi.fn(), getDataset: vi.fn(),
  getRun: vi.fn(), listDatasets: vi.fn(), listRuns: vi.fn(), uploadDataset: vi.fn(),
}));

const user = { id: "user-1", email: "planner@example.com" };
const token = `header.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.signature`;
const dataset: Dataset = { id: "plan-1", name: "Test rail plan", created_at: "2026-09-19T00:00:00Z",
  summary: { lines: 0, stations: 0, locations: 0, contracts: 0, activities: 0, total_accesses: 0, horizon_start: "2026-09-19", horizon_weeks: 1 } };
const instance: Instance = { activities: [], stations: [], lines: [], locations: [], horizon_weeks: 1 };
const completed: Run = { id: "run-1", dataset_id: dataset.id, scenario: "A", status: "completed", created_at: dataset.created_at,
  message: "Schedule complete", report: null, schedule: null };

let container: HTMLDivElement;
let root: Root;
function button(text: string, scope: ParentNode = container) {
  const result = Array.from(scope.querySelectorAll<HTMLButtonElement>("button")).find(element => element.textContent === text);
  if (!result) throw new Error(`Button missing: ${text}`);
  return result;
}
async function click(element: HTMLElement) { await act(async () => { element.click(); }); }
async function render(signedIn = false) {
  if (signedIn) sessionStorage.setItem("access_token", token);
  await act(async () => { root.render(<App />); });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.resetAllMocks();
  sessionStorage.clear();
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(auth.getCurrentUser).mockResolvedValue(user);
  vi.mocked(scheduling.getCapabilities).mockResolvedValue({ can_schedule: true, can_prepare: true, missing_constraints: [], required_files: [] });
  vi.mocked(scheduling.listDatasets).mockResolvedValue([dataset]);
  vi.mocked(scheduling.listRuns).mockResolvedValue([completed]);
  vi.mocked(scheduling.getDataset).mockResolvedValue({ ...dataset, instance });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

describe("Guest and account navigation", () => {
  it("shows the branded welcome page and disables every workspace control before sign-in", async () => {
    await render();
    expect(container.querySelector("#welcome-title")).not.toBeNull();
    expect(container.querySelector("#workspace")).toBeNull();
    expect(container.querySelectorAll(".transport-logos img")).toHaveLength(2);
    const controls = container.querySelectorAll<HTMLButtonElement>(".sidebar button");
    expect(controls.length).toBe(4);
    for (const control of controls) { expect(control.disabled).toBe(true); await click(control); }
    expect(container.querySelector("[aria-current]")).toBeNull();
    expect(scheduling.listDatasets).not.toHaveBeenCalled();
    expect(button("Sign in to your workspace").disabled).toBe(false);
  });

  it("opens the requested account form and keeps only one account tab selected", async () => {
    await render();
    await click(button("Create account", container.querySelector(".welcome-actions")!));
    expect(container.querySelector("dialog")?.open).toBe(true);
    expect(container.querySelector("#auth-heading")?.textContent).toBe("Create an account");
    await click(button("Sign in", container.querySelector(".auth-tabs")!));
    expect(container.querySelector("#auth-heading")?.textContent).toBe("Sign in");
    expect(container.querySelectorAll('.auth-tabs [aria-pressed="true"]')).toHaveLength(1);
  });

  it("unlocks the workspace after restoration and returns to the welcome page on sign-out", async () => {
    await render(true);
    expect(container.querySelector("#workspace")).not.toBeNull();
    expect(container.querySelector("#welcome-title")).toBeNull();
    expect(button("New plan").disabled).toBe(false);
    await click(container.querySelector<HTMLButtonElement>(".account-button")!);
    await click(button("Sign out"));
    expect(container.querySelector("#welcome-title")).not.toBeNull();
    expect(button("New plan").disabled).toBe(true);
    expect(sessionStorage.getItem("access_token")).toBeNull();
  });

  it("prevents duplicate sign-in requests, recovers after an error and opens the workspace on success", async () => {
    const pending = deferred<AuthResponse>();
    vi.mocked(auth.authenticate).mockReturnValueOnce(pending.promise);
    await render();
    await click(button("Sign in to your workspace"));
    await act(async () => {
      const email = container.querySelector<HTMLInputElement>('.auth-form input[type="email"]')!;
      email.value = user.email; Simulate.change(email);
      const password = container.querySelector<HTMLInputElement>('.auth-form input[type="password"]')!;
      password.value = "test-password"; Simulate.change(password);
    });
    const form = container.querySelector<HTMLFormElement>(".auth-form")!;
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    expect(auth.authenticate).toHaveBeenCalledTimes(1);
    expect(auth.authenticate).toHaveBeenCalledWith("signin", user.email, "test-password", "");
    expect(button("Please wait…").disabled).toBe(true);
    await act(async () => { pending.reject(new Error("Try again")); });
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Try again");
    vi.mocked(auth.authenticate).mockResolvedValueOnce({ access_token: token, token_type: "bearer", expires_in: 3600, user });
    await act(async () => { form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
    expect(container.querySelector("#workspace")).not.toBeNull();
    expect(container.querySelector("dialog")?.open).toBe(false);
  });
});

describe("Workspace selection and pending actions", () => {
  it("keeps one navigation item and one choice in each independent group selected", async () => {
    await render(true);
    await click(button("Planning approach"));
    await click(button("Safety settings"));
    expect(container.querySelectorAll(".nav-link[aria-current]")).toHaveLength(1);
    expect(button("Safety settings").getAttribute("aria-current")).toBe("location");
    await click(container.querySelector<HTMLInputElement>('input[name="scenario"][value="B"]')!);
    await click(container.querySelector<HTMLInputElement>('input[name="scenario"][value="C"]')!);
    await click(container.querySelector<HTMLInputElement>('input[name="safety"][value="possession"]')!);
    expect(container.querySelectorAll('input[name="scenario"]:checked')).toHaveLength(1);
    expect(container.querySelector<HTMLInputElement>('input[name="scenario"]:checked')?.value).toBe("C");
    expect(container.querySelectorAll('input[name="safety"]:checked')).toHaveLength(1);
    expect(container.querySelector<HTMLInputElement>('input[name="safety"]:checked')?.value).toBe("possession");
  });

  it("starts only one schedule on rapid clicks and locks conflicting actions until it responds", async () => {
    const pending = deferred<Run>();
    vi.mocked(scheduling.createRun).mockReturnValue(pending.promise);
    await render(true);
    const generate = button("Generate scenario A");
    await act(async () => { generate.click(); generate.click(); });
    expect(scheduling.createRun).toHaveBeenCalledTimes(1);
    expect(scheduling.createRun).toHaveBeenCalledWith(dataset.id, "A", "week");
    expect(button("Starting schedule…").disabled).toBe(true);
    expect(button("Upload and check files").disabled).toBe(true);
    expect(button("New plan").disabled).toBe(true);
    expect(container.querySelector<HTMLFieldSetElement>("fieldset")?.disabled).toBe(true);
    await act(async () => { pending.resolve({ ...completed, id: "run-2" }); });
    expect(button("New plan").disabled).toBe(false);
    expect(button("Download submission ZIP").disabled).toBe(false);
  });

  it("downloads one ZIP on rapid clicks, recovers from failure, and keeps results on refresh", async () => {
    const pending = deferred<void>();
    vi.mocked(scheduling.downloadRunFile).mockReturnValueOnce(pending.promise);
    await render(true);
    await click(container.querySelector<HTMLButtonElement>(".run-history button")!);
    const download = button("Download submission ZIP");
    await act(async () => { download.click(); download.click(); });
    expect(scheduling.downloadRunFile).toHaveBeenCalledTimes(1);
    expect(scheduling.downloadRunFile).toHaveBeenCalledWith(completed, "submission");
    expect(button("Preparing ZIP…").disabled).toBe(true);
    await act(async () => { pending.reject(new Error("Download interrupted")); });
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Download interrupted");
    vi.mocked(scheduling.downloadRunFile).mockResolvedValueOnce(undefined);
    await click(button("Download submission ZIP"));
    expect(container.querySelector(".download-notice")?.textContent).toContain("Download started");
    expect(container.querySelector('[role="alert"]')).toBeNull();
    await click(button("Refresh"));
    expect(button("Download submission ZIP").disabled).toBe(false);
    expect(container.querySelectorAll('.run-history [aria-pressed="true"]')).toHaveLength(1);
  });
});
