import { API_BASE_URL } from "./client";
import type { AuthResponse, User } from "../types/auth";

export class AuthApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "AuthApiError";
  }
}

async function request<T>(path: string, options: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/auth${path}`, {
      ...options, signal: AbortSignal.timeout(30000),
    });
  } catch (cause) {
    if (cause instanceof DOMException && ["TimeoutError", "AbortError"].includes(cause.name)) {
      throw new AuthApiError("The server did not respond within 30 seconds. Check the backend and its Neon database connection. If signup was submitted, try signing in before submitting again.");
    }
    throw new AuthApiError("Could not reach the backend. Check that the API is running and the frontend API URL is correct.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail
      : Array.isArray(data?.detail) ? data.detail.map((error: { msg?: string }) => error.msg || "Invalid input").join(" ")
      : "Authentication failed. Please try again.";
    throw new AuthApiError(detail, response.status);
  }
  if (!data) throw new AuthApiError("The backend returned an invalid response.");
  return data as T;
}

export function authenticate(mode: "signin" | "signup", email: string, password: string, signupCode: string) {
  return request<AuthResponse>(`/${mode}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, ...(mode === "signup" ? { signup_code: signupCode } : {}) }),
  });
}

export function getCurrentUser(token: string) {
  return request<User>("/me", { headers: { Authorization: `Bearer ${token}` } });
}
