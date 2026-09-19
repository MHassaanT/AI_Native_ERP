"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Lock, Mail, Building2, ArrowRight, AlertCircle, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { setAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await api.login({
        email: email.trim().toLowerCase(),
        password,
        tenant_slug: tenantSlug.trim() ? tenantSlug.trim().toLowerCase() : undefined,
      });

      setAuth(res.access_token, res.user);
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Please verify your email and password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex flex-col justify-center items-center px-4">
      <div className="w-full max-w-md space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-cream-300 bg-cream-100 text-[11px] font-mono text-cream-800">
            <Sparkles className="h-3 w-3 text-sage-600" />
            <span>Multi-Tenant Enterprise Portal</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-cream-900">
            Sign In to Autonomous ERP
          </h1>
          <p className="text-xs text-cream-700">
            Cryptographic role-based isolation across General Ledger, Shop Floor & Supply Chain.
          </p>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-sm space-y-5">
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-cream-900 mb-1.5">
                Corporate Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-cream-600" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@yourcompany.com"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 pl-9 pr-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream-900 mb-1.5">
                Master Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-cream-600" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 pl-9 pr-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream-900 mb-1.5">
                Organization Slug <span className="text-cream-500 font-normal">(Optional)</span>
              </label>
              <div className="relative">
                <Building2 className="absolute left-3 top-2.5 h-4 w-4 text-cream-600" />
                <input
                  type="text"
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  placeholder="e.g. acme-aerospace"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 pl-9 pr-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800 font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-cream-400 bg-cream-900 px-4 py-2 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
            >
              {loading ? (
                <span>Authenticating JWT...</span>
              ) : (
                <>
                  <span>Sign In to Workspace</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Footer Link */}
        <div className="text-center text-xs text-cream-700">
          Need a dedicated enterprise tenant?{" "}
          <Link href="/signup" className="font-medium text-cream-900 hover:underline">
            Register your company &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
}
