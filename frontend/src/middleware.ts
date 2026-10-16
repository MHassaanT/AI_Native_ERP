import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

function parseTokenPayload(token: string | undefined): any {
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    let base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    while (base64.length % 4) {
      base64 += "=";
    }
    const jsonStr = atob(base64);
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

function isTokenValid(token: string | undefined): boolean {
  const payload = parseTokenPayload(token);
  if (!payload) return false;
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    return false; // Token expired
  }
  return true;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow static files, api routes, and Next.js internal bundles
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname === "/favicon.ico" ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const rawToken = request.cookies.get("ai_erp_token")?.value;
  const hasValidToken = isTokenValid(rawToken);
  const payload = parseTokenPayload(rawToken);
  const isLandingPage = pathname === "/";
  const isAuthPage = pathname === "/login" || pathname === "/signup";
  const isSetupPage = pathname === "/setup";
  const isSubscriptionPage = pathname === "/billing/subscription";

  // If user has an invalid/expired token in cookies, clear it immediately
  if (rawToken && !hasValidToken) {
    const response = isAuthPage || isLandingPage
      ? NextResponse.next()
      : NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete("ai_erp_token");
    return response;
  }

  // The landing page and account entry points are public. All workspace routes
  // (including setup) require a valid session.
  if (!hasValidToken && !isAuthPage && !isLandingPage) {
    const loginUrl = new URL("/login", request.url);
    const response = NextResponse.redirect(loginUrl);
    if (rawToken) response.cookies.delete("ai_erp_token");
    return response;
  }

  // If user IS logged in with a valid token:
  if (hasValidToken) {
    const isSetupDone = payload?.setup_complete !== false; // defaults to true if omitted for legacy tokens

    // Require a subscription before setup or workspace access, but keep billing reachable.
    if (!isSetupDone && !isSetupPage && !isSubscriptionPage) {
      return NextResponse.redirect(new URL("/billing/subscription", request.url));
    }

    // If setup is already done and user tries to access /setup, redirect to the overview.
    if (isSetupDone && isSetupPage) {
      return NextResponse.redirect(new URL("/overview", request.url));
    }

    // If user visits /login or /signup while authenticated
    if (isAuthPage) {
      return NextResponse.redirect(new URL("/billing/subscription", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
