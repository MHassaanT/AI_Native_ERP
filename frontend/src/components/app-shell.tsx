"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { AuthGuard } from "./auth-guard";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isOpenMobile, setIsOpenMobile] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("ai_erp_sidebar_collapsed");
      if (saved !== null) {
        setIsCollapsed(saved === "true");
      }
    } catch {
      // Ignore localStorage read errors in restricted contexts
    }
  }, []);

  const handleToggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("ai_erp_sidebar_collapsed", String(next));
      } catch {
        // Ignore write errors
      }
      return next;
    });
  };

  const isAuthPage = pathname === "/login" || pathname === "/signup";

  // Auth pages (Login / Signup) render clean without the sidebar
  if (isAuthPage) {
    return (
      <div className="min-h-screen flex flex-col justify-center bg-cream-50 text-cream-900 font-sans">
        <main className="w-full">
          <AuthGuard>{children}</AuthGuard>
        </main>
        <footer className="py-4 text-center text-xs text-cream-600">
          AI-Native Multi-Agent ERP &bull; Deterministic Invariant Firewall Active
        </footer>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-cream-50 text-cream-900 antialiased font-sans">
      {/* 1. Left Vertical Sidebar (Desktop Persistent + Mobile Drawer) */}
      <Sidebar
        isCollapsed={isCollapsed}
        onToggleCollapse={handleToggleCollapse}
        isOpenMobile={isOpenMobile}
        onCloseMobile={() => setIsOpenMobile(false)}
      />

      {/* 2. Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        <TopBar onOpenMobile={() => setIsOpenMobile(true)} />

        <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 lg:p-8">
          <AuthGuard>{children}</AuthGuard>
        </main>

        <footer className="border-t border-cream-300 py-4 text-center text-xs text-cream-700 bg-cream-50/50">
          AI-Native Multi-Agent ERP &bull; Deterministic Invariant Firewall Active &bull; Multi-Tenant Isolated
        </footer>
      </div>
    </div>
  );
}
