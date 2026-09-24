import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

function isTokenValid(token: string | undefined): boolean {
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
  const isAuthPage = pathname === "/login" || pathname === "/signup";

  // If user has an invalid/expired token in cookies, clear it immediately
  if (rawToken && !hasValidToken) {
    const response = isAuthPage
      ? NextResponse.next()
      : NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete("ai_erp_token");
    return response;
  }

  // If user is NOT logged in and trying to access ANY protected page (including /), redirect to /login
  if (!hasValidToken && !isAuthPage) {
    const loginUrl = new URL("/login", request.url);
    const response = NextResponse.redirect(loginUrl);
    if (rawToken) response.cookies.delete("ai_erp_token");
    return response;
  }

  // If user IS logged in with a valid token and visits /login or /signup, redirect to dashboard /
  if (hasValidToken && isAuthPage) {
    return NextResponse.redirect(new URL("/", request.url));
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
