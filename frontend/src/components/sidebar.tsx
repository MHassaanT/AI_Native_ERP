"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Mail,
  Users,
  DollarSign,
  Factory,
  Layers,
  Wrench,
  FileCheck,
  Landmark,
  BookOpen,
  Lock,
  Building2,
  LogOut,
  ChevronLeft,
  ChevronRight,
  X,
  Store,
  Briefcase,
  Receipt,
  ShoppingBag,
  Headset,
  BarChart3,
  Activity,
  Truck,
  MessageCircle,
} from "lucide-react";
import { getUser, clearAuth, UserProfile } from "@/lib/auth";

export interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "Workspace & AI",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard },
      { href: "/inbox", label: "Email / RFQ Hub", icon: Mail },
      { href: "/workflows", label: "Workflow Runs", icon: Activity },
      { href: "/workforce", label: "Workforce & Shifts", icon: Users },
      { href: "/recruitment", label: "Recruitment & Screening", icon: Briefcase },
    ],
  },
  {
    title: "Commercial & Operations",
    items: [
      { href: "/commercial", label: "Commercial & Sales", icon: DollarSign },
      { href: "/crm", label: "CRM & Support Desk", icon: Headset },
      { href: "/whatsapp", label: "WhatsApp Support", icon: MessageCircle },
      { href: "/procurement", label: "Procurement & Buying", icon: ShoppingBag },
      { href: "/pos", label: "Point of Sale (POS)", icon: Store },
      { href: "/production", label: "Production & BOM", icon: Factory },
      { href: "/quality", label: "Quality & IoT Sensors", icon: Activity },
      { href: "/inventory", label: "Inventory & Warehouses", icon: Layers },
      { href: "/subcontracting", label: "Subcontracting Ops", icon: Truck },
      { href: "/maintenance", label: "Maintenance Hub", icon: Wrench },
      { href: "/assets", label: "Fixed Assets & Dep.", icon: Building2 },
      { href: "/projects", label: "Projects & Timesheets", icon: Briefcase },
    ],
  },
  {
    title: "Finance & Governance",
    items: [
      { href: "/reports", label: "Reports & Analytics", icon: BarChart3 },
      { href: "/billing", label: "Billing & Subscriptions", icon: Receipt },
      { href: "/accounts-payable", label: "3-Way Invoice Match", icon: FileCheck },
      { href: "/bank-reconciliation", label: "Bank Reconciliation", icon: Landmark },
      { href: "/ledger", label: "General Ledger", icon: BookOpen },
      { href: "/audit", label: "SOC 2 Audit Trail", icon: Lock },
    ],
  },
];


interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  isCollapsed,
  onToggleCollapse,
  isOpenMobile,
  onCloseMobile,
}: SidebarProps) {
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

  const renderNavContent = (isRail: boolean) => (
    <div className="flex flex-col h-full select-none">
      {/* 1. Brand & Logo Header */}
      <div className={`flex items-center h-[68px] px-4 border-b border-cream-300/80 bg-white/70 ${isRail ? "justify-center" : "justify-between"}`}>
        <Link
          href="/"
          onClick={onCloseMobile}
          className={`flex items-center gap-3 group ${isRail ? "justify-center" : ""}`}
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sage-500 font-mono text-xs font-bold text-white shadow-sm group-hover:bg-sage-700 transition-colors">
            AI
          </div>
          {!isRail && (
            <div className="flex flex-col">
              <span className="font-semibold tracking-tight text-cream-900 text-sm leading-tight flex items-center gap-1.5">
                AI-Native ERP
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-sage-500 animate-pulse" />
              </span>
              <span className="text-[10px] text-cream-500 tracking-wide">
                Operations workspace
              </span>
            </div>
          )}
        </Link>

        {/* Mobile close button */}
        <button
          onClick={onCloseMobile}
          className="p-1 rounded-md text-cream-600 hover:text-cream-900 hover:bg-cream-200 md:hidden"
          aria-label="Close navigation"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* 2. Tenant Context Badge (Expanded only) */}
      {!isRail && currentUser && (
        <div className="px-3 pt-4 pb-1 space-y-2">
          <div className="flex items-center gap-2.5 p-2.5 rounded-xl border border-cream-300/80 bg-white shadow-sm">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sage-50 border border-sage-500/20 text-sage-600">
              <Building2 className="h-4 w-4" />
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-semibold text-cream-900 truncate">
                {currentUser.company_name || currentUser.tenant_slug}
              </span>
              <span className="text-[10px] font-mono text-cream-600 truncate">
                Role: {currentUser.role.replace("TENANT_", "")}
              </span>
            </div>
          </div>

          {currentUser.setup_complete === false && (
            <Link
              href="/setup"
              onClick={onCloseMobile}
              className="flex items-center justify-between p-2 rounded-lg border border-amberGold-500/30 bg-amberGold-50 text-[11px] text-amberGold-700 hover:bg-amberGold-100 transition-colors font-medium"
            >
              <span>Setup Pending &rarr;</span>
              <span className="font-mono text-[9px] uppercase tracking-wide px-1.5 py-0.5 rounded bg-amberGold-200">
                Action Required
              </span>
            </Link>
          )}
        </div>
      )}

      {/* 3. Navigation Links (Categorized) */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="space-y-1.5">
            {!isRail && (
              <h3 className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-cream-500">
                {group.title}
              </h3>
            )}
            <div className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={onCloseMobile}
                    title={isRail ? label : undefined}
                    className={`flex items-center rounded-lg text-[13px] font-medium transition-all duration-150 ${
                      isRail
                        ? "justify-center p-2.5"
                        : "gap-3 px-3 py-[9px]"
                    } ${
                      active
                        ? "bg-sage-50 text-sage-700 font-semibold shadow-sm ring-1 ring-sage-500/10"
                        : "text-cream-700 hover:bg-white hover:text-cream-900"
                    }`}
                  >
                    <Icon
                      className={`h-4 w-4 shrink-0 transition-opacity ${
                        active ? "text-sage-600 opacity-100" : "text-cream-600 opacity-75"
                      }`}
                    />
                    {!isRail && <span className="truncate">{label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* 4. Footer Section */}
      <div className="border-t border-cream-300/80 p-3 bg-white/70 space-y-2">
        {currentUser ? (
          <div className="space-y-2">
            {!isRail && (
              <div className="flex items-center justify-between px-1 py-1">
                <div className="flex flex-col min-w-0 pr-2">
                  <span className="text-xs font-semibold text-cream-900 truncate">
                    {currentUser.full_name || currentUser.email.split("@")[0]}
                  </span>
                  <span className="text-[10px] text-cream-500 truncate font-mono">
                    {currentUser.email}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  title="Sign Out"
                  className="p-1.5 rounded-md text-cream-600 hover:text-terracotta-700 hover:bg-terracotta-50 transition-colors shrink-0"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            )}

            {isRail && (
              <button
                onClick={handleLogout}
                title={`Sign Out (${currentUser.email})`}
                className="w-full flex items-center justify-center p-2 rounded-md text-cream-600 hover:text-terracotta-700 hover:bg-terracotta-50 transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-1">
            {!isRail ? (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className="flex-1 text-center rounded-md border border-cream-300 bg-cream-100 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  href="/signup"
                  className="flex-1 text-center rounded-md border border-cream-400 bg-cream-900 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Register
                </Link>
              </div>
            ) : (
              <Link
                href="/login"
                title="Sign In"
                className="flex items-center justify-center p-2 rounded-md border border-cream-300 bg-cream-100 text-xs font-medium text-cream-800"
              >
                AI
              </Link>
            )}
          </div>
        )}

        {/* Desktop Collapse Toggle */}
        <button
          onClick={onToggleCollapse}
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={`hidden md:flex w-full items-center rounded-md border border-cream-300 bg-cream-100 py-1.5 text-xs text-cream-700 hover:bg-cream-200 hover:text-cream-900 transition-colors ${
            isRail ? "justify-center px-1" : "justify-between px-2.5"
          }`}
        >
          {!isRail && (
            <span className="text-[11px] font-medium text-cream-600">
              Collapse sidebar
            </span>
          )}
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4 text-cream-600" />
          ) : (
            <ChevronLeft className="h-4 w-4 text-cream-600" />
          )}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Drawer Overlay */}
      {isOpenMobile && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-cream-950/40 backdrop-blur-xs md:hidden transition-opacity"
          aria-hidden="true"
        />
      )}

      {/* Mobile Drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 bg-cream-50 border-r border-cream-300 shadow-xl md:hidden transform transition-transform duration-300 ease-in-out ${
          isOpenMobile ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {renderNavContent(false)}
      </aside>

      {/* Desktop Persistent Sidebar */}
      <aside
        className={`hidden md:flex flex-col shrink-0 border-r border-cream-300/80 bg-[#f8f9f7] transition-[width] duration-200 ease-in-out sticky top-0 h-screen ${
          isCollapsed ? "w-20" : "w-64"
        }`}
      >
        {renderNavContent(isCollapsed)}
      </aside>
    </>
  );
}
