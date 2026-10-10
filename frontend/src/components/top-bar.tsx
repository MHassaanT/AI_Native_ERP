"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Menu,
  ShieldCheck,
  Building2,
  LogOut,
} from "lucide-react";
import { getUser, clearAuth, UserProfile } from "@/lib/auth";
import { NAV_GROUPS } from "./sidebar";

interface TopBarProps {
  onOpenMobile: () => void;
}

export function TopBar({ onOpenMobile }: TopBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    const updateUser = () => setCurrentUser(getUser());
    updateUser();

    window.addEventListener("auth-changed", updateUser);
    return () => window.removeEventListener("auth-changed", updateUser);
  }, []);

  const handleLogout = () => {
    clearAuth();
    router.push("/login");
  };

  // Find active group and item
  let activeGroupTitle = "Workspace";
  let activeItemLabel = "Overview";
  let ActiveIcon = null;

  for (const group of NAV_GROUPS) {
    const matched = group.items.find((item) => item.href === pathname);
    if (matched) {
      activeGroupTitle = group.title;
      activeItemLabel = matched.label;
      ActiveIcon = matched.icon;
      break;
    }
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-cream-300/80 bg-white/90 px-4 md:px-7 backdrop-blur-xl">
      {/* Left: Mobile Toggle + Breadcrumb */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobile}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-cream-300 bg-white text-cream-700 hover:bg-cream-100 hover:text-cream-900 md:hidden transition-colors"
          aria-label="Open navigation menu"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2 text-[13px]">
          <span className="hidden sm:inline text-cream-500">
            {activeGroupTitle}
          </span>
          <span className="hidden sm:inline text-cream-400 font-mono">/</span>
          <span className="font-semibold text-cream-900 flex items-center gap-2">
            {ActiveIcon && <ActiveIcon className="h-4 w-4 text-sage-600" />}
            {activeItemLabel}
          </span>
        </div>
      </div>

      {/* Right: Security & Tenant Context */}
      <div className="flex items-center gap-2.5">
        {/* Deterministic Invariant Firewall Badge */}
        <div className="hidden lg:flex items-center gap-2 rounded-full border border-sage-500/20 bg-sage-50 px-3 py-1.5 text-[11px] font-medium text-sage-700">
          <ShieldCheck className="h-3.5 w-3.5 text-sage-600" />
          <span>Invariant guard active</span>
        </div>

        {currentUser && (
          <div className="flex items-center gap-2">
            {/* Tenant badge */}
            <div className="hidden sm:flex items-center gap-2 rounded-lg border border-cream-300/80 bg-white px-3 py-2 text-xs text-cream-800">
              <Building2 className="h-3.5 w-3.5 text-cream-600" />
              <span className="font-medium text-cream-900 truncate max-w-[150px]">
                {currentUser.company_name || currentUser.tenant_slug}
              </span>
            </div>

            {/* User logout shortcut */}
            <button
              onClick={handleLogout}
              title={`Sign Out (${currentUser.email})`}
              className="flex items-center gap-1.5 rounded-lg border border-cream-300/80 bg-white px-3 py-2 text-xs font-medium text-cream-700 hover:bg-cream-100 hover:text-cream-900 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
