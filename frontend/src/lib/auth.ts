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
  setup_complete?: boolean;
}

const TOKEN_KEY = "ai_erp_token";
const USER_KEY = "ai_erp_user";

function parseCookie(cookieString: string, key: string): string | null {
  const match = cookieString.match(
    new RegExp("(?:^|; )" + key.replace(/([.$?*|{}()\[\]\\\/+^])/g, "\\$1") + "=([^;]*)")
  );
  return match ? decodeURIComponent(match[1]) : null;
}

export function isTokenValid(token: string | null | undefined): boolean {
  if (!token) return false;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    let base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    while (base64.length % 4) {
      base64 += "=";
    }
    const jsonStr = atob(base64);
    const payload = JSON.parse(jsonStr);
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      return false; // Token expired
    }
    return true;
  } catch {
    return false;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;

  let token = localStorage.getItem(TOKEN_KEY);
  const cookieToken = parseCookie(document.cookie, TOKEN_KEY);

  // Synchronize localStorage and document.cookie if one is missing
  if (!token && cookieToken) {
    token = cookieToken;
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // Ignore localStorage write error
    }
  } else if (token && !cookieToken) {
    document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; path=/; max-age=86400; SameSite=Lax`;
  }

  // Validate token expiration and integrity
  if (token && !isTokenValid(token)) {
    clearAuth();
    return null;
  }

  return token;
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
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // Ignore localStorage remove errors
  }
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`;
  window.dispatchEvent(new Event("auth-changed"));
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  const token = getToken();
  return !!token && isTokenValid(token);
}
