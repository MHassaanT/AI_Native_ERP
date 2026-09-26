"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, Mail, Lock, User, Sparkles, CheckCircle2, AlertCircle, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { setAuth } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompanyNameChange = (val: string) => {
    setCompanyName(val);
    const autoSlug = val
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    setTenantSlug(autoSlug);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await api.register({
        company_name: companyName.trim(),
        tenant_slug: tenantSlug.trim().toLowerCase(),
        email: email.trim().toLowerCase(),
        password,
        full_name: fullName.trim(),
      });

      setAuth(res.access_token, res.user);
      window.location.href = "/setup";
    } catch (err: any) {
      setError(err.message || "Registration failed. Please check the details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex flex-col justify-center items-center px-4 py-8">
      <div className="w-full max-w-xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-cream-300 bg-cream-100 text-[11px] font-mono text-cream-800">
            <Sparkles className="h-3 w-3 text-sage-600" />
            <span>Autonomous Enterprise Tenant Registration</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-cream-900">
            Create Your Enterprise Organization
          </h1>
          <p className="text-xs text-cream-700 max-w-md mx-auto">
            Stage 1: Register your master tenant credentials. You will then configure your localized Chart of Accounts, fiscal calendar, and industry modules in the Setup Wizard.
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1.5">
                  Company Name
                </label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-2.5 h-4 w-4 text-cream-600" />
                  <input
                    type="text"
                    required
                    value={companyName}
                    onChange={(e) => handleCompanyNameChange(e.target.value)}
                    placeholder="Acme Aerospace Ltd."
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 pl-9 pr-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1.5">
                  Organization Slug
                </label>
                <input
                  type="text"
                  required
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  placeholder="acme-aerospace"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1.5">
                  Administrator Full Name
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-2.5 h-4 w-4 text-cream-600" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Marcus Vance"
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 pl-9 pr-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800"
                  />
                </div>
              </div>

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
                    placeholder="admin@acme.com"
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 pl-9 pr-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream-900 mb-1.5">
                Master Security Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-cream-600" />
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters (hashed with bcrypt)"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 pl-9 pr-3 py-2 text-xs text-cream-900 placeholder-cream-500 focus:outline-none focus:ring-1 focus:ring-cream-800"
                />
              </div>
            </div>

            {/* Next Step Preview Note */}
            <div className="rounded-lg border border-cream-300 bg-cream-50 p-3 text-[11px] text-cream-700 space-y-1.5">
              <div className="font-semibold text-cream-900 flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-sage-600" />
                <span>Next Step: Enterprise Setup Wizard</span>
              </div>
              <p className="text-[11px] text-cream-600">
                You will tailor your country fiscal calendar, currency, localized Chart of Accounts, and factory modules before launch.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-cream-400 bg-cream-900 px-4 py-2.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
            >
              {loading ? (
                <span>Creating Organization...</span>
              ) : (
                <>
                  <span>Register & Proceed to Setup Wizard</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Footer Link */}
        <div className="text-center text-xs text-cream-700">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-cream-900 hover:underline">
            Sign in &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
}
