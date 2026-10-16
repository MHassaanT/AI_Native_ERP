"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";
import { api } from "@/lib/api";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [authorizedPath, setAuthorizedPath] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    const isPublic = pathname === "/" || pathname === "/login" || pathname === "/signup";
    const authStatus = isAuthenticated();

    if (!authStatus && !isPublic) {
      setIsAuthorized(false);
      setAuthorizedPath(null);
      router.replace("/login");
    } else if (authStatus && (pathname === "/login" || pathname === "/signup")) {
      setIsAuthorized(false);
      setAuthorizedPath(null);
      router.replace("/billing/subscription");
    } else if (authStatus && pathname !== "/billing/subscription" && pathname !== "/") {
      let active = true;
      setIsAuthorized(false);
      setAuthorizedPath(null);
      api.getAccountSubscription().then((result) => {
        if (!active) return;
        if (result?.has_access) {
          setIsAuthorized(true);
          setAuthorizedPath(pathname);
        } else {
          router.replace("/billing/subscription");
        }
      }).catch(() => {
        if (active) router.replace("/billing/subscription");
      });
      return () => { active = false; };
    } else {
      setIsAuthorized(true);
      setAuthorizedPath(pathname);
    }
  }, [pathname, router]);

  // Before client mount, avoid layout flash
  if (!mounted) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <div className="flex items-center gap-2 text-xs font-mono text-cream-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-cream-800 border-t-transparent" />
          <span>Verifying security credentials...</span>
        </div>
      </div>
    );
  }

  const isPublic = pathname === "/" || pathname === "/login" || pathname === "/signup";
  if (isAuthenticated() && pathname !== "/billing/subscription" && pathname !== "/" &&
      (!isAuthorized || authorizedPath !== pathname)) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <div className="flex items-center gap-2 text-xs font-mono text-cream-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-cream-800 border-t-transparent" />
          <span>Checking workspace subscription...</span>
        </div>
      </div>
    );
  }
  if (!isAuthorized && !isPublic) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <div className="flex items-center gap-2 text-xs font-mono text-cream-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-cream-800 border-t-transparent" />
          <span>Redirecting to login portal...</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
