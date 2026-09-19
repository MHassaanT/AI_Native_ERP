import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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

  const token = request.cookies.get("ai_erp_token")?.value;
  const isAuthPage = pathname === "/login" || pathname === "/signup";

  // If user is NOT logged in and trying to access ANY protected page (including /), redirect to /signup
  if (!token && !isAuthPage) {
    const signupUrl = new URL("/signup", request.url);
    return NextResponse.redirect(signupUrl);
  }

  // If user IS logged in and visits /login or /signup, redirect to /
  if (token && isAuthPage) {
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
