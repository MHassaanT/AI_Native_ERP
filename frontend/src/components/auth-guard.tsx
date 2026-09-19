"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const [isAuthorized, setIsAuthorized] = useState(false);

  useEffect(() => {
    setMounted(true);
    const isPublic = pathname === "/login" || pathname === "/signup";
    const authStatus = isAuthenticated();

    if (!authStatus && !isPublic) {
      setIsAuthorized(false);
      router.replace("/signup");
    } else if (authStatus && isPublic) {
      setIsAuthorized(true);
      router.replace("/");
    } else {
      setIsAuthorized(true);
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

  const isPublic = pathname === "/login" || pathname === "/signup";
  if (!isAuthorized && !isPublic) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <div className="flex items-center gap-2 text-xs font-mono text-cream-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-cream-800 border-t-transparent" />
          <span>Redirecting to organization signup...</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
