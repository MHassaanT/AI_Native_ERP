"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Camera,
  Cpu,
  DollarSign,
  FileCheck,
  Layers,
  Landmark,
  Lock,
  ShieldCheck,
  Users,
  LogOut,
  Building2,
  User as UserIcon,
  Mail,
} from "lucide-react";
import { getUser, clearAuth, UserProfile } from "@/lib/auth";

export function Navbar() {
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

  const navItems = [
    { href: "/", label: "Overview", icon: Activity },
    { href: "/inbox", label: "Email / RFQ", icon: Mail },
    { href: "/agents", label: "Agent Mesh", icon: Cpu },
    { href: "/workforce", label: "Workforce", icon: Users },
    { href: "/commercial", label: "Commercial", icon: DollarSign },
    { href: "/production", label: "Production", icon: Activity },
    { href: "/quality", label: "Quality / IoT", icon: Camera },
    { href: "/accounts-payable", label: "3-Way Match", icon: FileCheck },
    { href: "/bank-reconciliation", label: "Bank Recon", icon: Landmark },
    { href: "/inventory", label: "Inventory", icon: Layers },
    { href: "/maintenance", label: "Maintenance", icon: ShieldCheck },
    { href: "/audit", label: "SOC 2 Audit", icon: Lock },
    { href: "/ledger", label: "Ledger", icon: Layers },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-cream-300 bg-cream-50/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-5">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded border border-cream-400 bg-cream-100 font-mono text-xs font-semibold text-cream-900 shadow-sm">
              AI
            </span>
            <span className="font-medium tracking-tight text-cream-900 text-sm">
              AI-Native ERP
            </span>
          </Link>

          <nav className="flex items-center gap-0.5">
            {navItems.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    active
                      ? "bg-cream-200 text-cream-900 shadow-xs"
                      : "text-cream-700 hover:bg-cream-100 hover:text-cream-900"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5 opacity-70" />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {currentUser ? (
            <>
              {/* Active Tenant Badge */}
              <div className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-2.5 py-1 text-xs text-cream-800">
                <Building2 className="h-3 w-3 text-sage-600" />
                <span className="font-medium text-cream-900 truncate max-w-[140px]">
                  {currentUser.company_name || currentUser.tenant_slug}
                </span>
                <span className="text-[10px] font-mono text-cream-500">
                  ({currentUser.role.replace("TENANT_", "")})
                </span>
              </div>

              {/* User Email & Logout */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-cream-600 hidden md:inline truncate max-w-[120px]">
                  {currentUser.email}
                </span>
                <button
                  onClick={handleLogout}
                  title="Sign Out"
                  className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-2.5 py-1 text-xs text-cream-700 hover:bg-cream-200 hover:text-cream-900 transition-colors font-medium"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Logout</span>
                </button>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="rounded-md border border-cream-400 bg-cream-900 px-3 py-1 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
