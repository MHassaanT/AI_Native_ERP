/**
 * Authentication and Multi-Tenant Session Management.
 */

export interface UserProfile {
  user_id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: string;
  company_name: string;
  tenant_slug: string;
}

const TOKEN_KEY = "ai_erp_token";
const USER_KEY = "ai_erp_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  const userStr = localStorage.getItem(USER_KEY);
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: UserProfile): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; path=/; max-age=86400; SameSite=Lax`;
  window.dispatchEvent(new Event("auth-changed"));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax`;
  window.dispatchEvent(new Event("auth-changed"));
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem(TOKEN_KEY);
}
