import { API_BASE_URL } from "./client";
import type { AuthResponse, User } from "../types/auth";

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/auth${path}`, {
    ...options, signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Check your email and password. Passwords require at least 8 characters and at most 72 UTF-8 bytes.";
    throw new Error(detail);
  }
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
