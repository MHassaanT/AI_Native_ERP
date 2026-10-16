"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight, Check, CreditCard, Loader2, RefreshCw, ShieldCheck,
  Sparkles, XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { getUser } from "@/lib/auth";

type Plan = {
  code: "monthly" | "annual";
  configured: boolean;
  name: string;
  amount: string;
  currency: string;
  interval: string;
  environment: string;
};

type Subscription = {
  id: string;
  plan_name: string;
  status: string;
  currency: string;
  amount: string | null;
  billing_interval: string;
  current_period_end: string | null;
  last_payment_at: string | null;
  cancellation_requested_at: string | null;
};

type BillingStatus = {
  plans: Plan[];
  subscription: Subscription | null;
  history: Subscription[];
  has_access: boolean;
};

const formatDate = (value: string | null) => value
  ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value))
  : "—";

export default function SubscriptionBillingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"monthly" | "annual" | "cancel" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const user = typeof window !== "undefined" ? getUser() : null;
  const isAdmin = user?.role === "TENANT_ADMIN";

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getAccountSubscription() as BillingStatus;
      setBilling(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load subscription details.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (searchParams.get("payment") === "returned") {
      setNotice("Checkout returned. We are waiting for SafePay to confirm the first payment; access starts after confirmation.");
      const timer = window.setInterval(() => void refresh(), 5000);
      const stop = window.setTimeout(() => window.clearInterval(timer), 60000);
      return () => { window.clearInterval(timer); window.clearTimeout(stop); };
    }
    if (searchParams.get("payment") === "cancelled") {
      setNotice("Checkout was cancelled. No subscription has been activated.");
    }
  }, [searchParams, refresh]);

  const startCheckout = async (plan: "monthly" | "annual") => {
    setBusy(plan);
    setError(null);
    try {
      const result = await api.createAccountSubscriptionCheckout(plan);
      if (!result?.checkout_url) throw new Error("SafePay did not return a checkout link.");
      window.location.assign(result.checkout_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout.");
      setBusy(null);
    }
  };

  const cancelSubscription = async () => {
    if (!window.confirm("Request cancellation of this subscription? SafePay will confirm the final status.")) return;
    setBusy("cancel");
    setError(null);
    try {
      await api.cancelAccountSubscription();
      setNotice("Cancellation request sent to SafePay. Your status will update when SafePay confirms it.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not request cancellation.");
    } finally {
      setBusy(null);
    }
  };

  const openWorkspace = () => {
    router.push(user?.setup_complete === false ? "/setup" : "/overview");
  };

  const plans = billing?.plans ?? [];
  const subscription = billing?.subscription;
  const active = billing?.has_access ?? false;

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-sage-500/20 bg-sage-50 px-3 py-1 text-xs font-medium text-sage-700">
            <CreditCard className="h-3.5 w-3.5" /> Workspace plan
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-cream-950">Subscription & billing</h1>
          <p className="mt-2 max-w-2xl text-sm text-cream-600">Choose a plan to unlock your AI-Native ERP workspace. Secure recurring payments are handled by SafePay.</p>
        </div>
        <button onClick={() => void refresh()} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-lg border border-cream-300 bg-white px-4 py-2.5 text-sm font-medium text-cream-800 shadow-sm hover:bg-cream-50 disabled:opacity-60">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh status
        </button>
      </div>

      {error && <div role="alert" className="mb-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
      {notice && <div className="mb-5 flex gap-2 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />{notice}</div>}

      {loading && !billing ? (
        <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-cream-600"><Loader2 className="h-4 w-4 animate-spin" />Loading your billing details…</div>
      ) : (
        <>
          {active && subscription && (
            <section className="mb-8 rounded-2xl border border-sage-300 bg-sage-50/70 p-5 sm:p-6">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-sage-700"><span className="h-2 w-2 rounded-full bg-sage-500" /> Active subscription</div>
                  <h2 className="text-xl font-semibold text-cream-950">{subscription.plan_name}</h2>
                  <p className="mt-1 text-sm text-cream-700">{subscription.currency} {subscription.amount ?? "—"} / {subscription.billing_interval === "YEAR" ? "year" : "month"} · Renews {formatDate(subscription.current_period_end)}</p>
                  {subscription.cancellation_requested_at && <p className="mt-2 text-xs text-amberGold-700">Cancellation requested; SafePay confirmation is pending.</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={openWorkspace} className="inline-flex items-center gap-2 rounded-lg bg-cream-950 px-4 py-2.5 text-sm font-medium text-white hover:bg-cream-800">Open workspace <ArrowRight className="h-4 w-4" /></button>
                  {isAdmin && !subscription.cancellation_requested_at && <button onClick={() => void cancelSubscription()} disabled={busy === "cancel"} className="rounded-lg border border-cream-300 bg-white px-4 py-2.5 text-sm font-medium text-cream-700 hover:border-rose-300 hover:text-rose-700 disabled:opacity-60">{busy === "cancel" ? "Sending…" : "Cancel plan"}</button>}
                </div>
              </div>
            </section>
          )}

          {!active && subscription && (
            <section className="mb-8 flex items-start gap-3 rounded-xl border border-amberGold-300 bg-amberGold-50 p-4 text-sm text-amberGold-800">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div><p className="font-semibold">Subscription {subscription.status.replaceAll("_", " ")}</p><p className="mt-1">Workspace access is enabled after SafePay confirms a successful subscription payment.</p></div>
            </section>
          )}

          {!active && <>
            <div className="mb-4 flex items-center gap-2"><Sparkles className="h-4 w-4 text-sage-600" /><h2 className="text-lg font-semibold text-cream-950">Choose your plan</h2></div>
            <div className="grid gap-5 md:grid-cols-2">
              {plans.map((plan) => {
                const annual = plan.code === "annual";
                return <section key={plan.code} className={`relative flex flex-col rounded-2xl border bg-white p-6 shadow-sm ${annual ? "border-sage-400 ring-1 ring-sage-300" : "border-cream-300"}`}>
                  {annual && <span className="absolute -top-3 right-5 rounded-full bg-sage-600 px-3 py-1 text-[11px] font-semibold text-white">One month free · Save $50</span>}
                  <p className="text-sm font-semibold text-cream-800">{plan.name}</p>
                  <div className="mt-4 flex items-baseline gap-2"><span className="text-4xl font-semibold tracking-tight text-cream-950">${Number(plan.amount).toLocaleString("en-US")}</span><span className="text-sm text-cream-600">/{annual ? "year" : "month"}</span></div>
                  <p className="mt-2 min-h-5 text-xs text-cream-600">{annual ? "Equivalent to $45.83 per month, billed annually." : "Billed monthly. Cancel any time."}</p>
                  <ul className="my-6 space-y-3 text-sm text-cream-700">
                    {["Full ERP workspace access", "AI workflows and operational insights", "Secure, recurring SafePay billing"].map((feature) => <li key={feature} className="flex items-center gap-2"><Check className="h-4 w-4 text-sage-600" />{feature}</li>)}
                  </ul>
                  <button onClick={() => void startCheckout(plan.code)} disabled={!isAdmin || !plan.configured || !!busy} className={`mt-auto flex w-full items-center justify-center gap-2 rounded-lg border px-4 py-3 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${annual ? "border-sage-700 bg-sage-700 text-white hover:bg-sage-800" : "border-cream-300 bg-white text-cream-900 hover:bg-cream-50"}`}>
                    {busy === plan.code ? <><Loader2 className="h-4 w-4 animate-spin" />Starting checkout…</> : !isAdmin ? "Ask a workspace admin to subscribe" : !plan.configured ? "Plan setup required" : <>Continue to SafePay <ArrowRight className="h-4 w-4" /></>}
                  </button>
                </section>;
              })}
            </div>
            <p className="mt-5 text-center text-xs text-cream-500">Payments are processed by SafePay. Your workspace activates after SafePay confirms the initial payment.</p>
          </>}

          {!!billing?.history?.length && <section className="mt-10 rounded-2xl border border-cream-300 bg-white p-5 sm:p-6">
            <h2 className="text-base font-semibold text-cream-950">Subscription history</h2>
            <div className="mt-4 divide-y divide-cream-200">
              {billing.history.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"><div><p className="font-medium text-cream-800">{item.plan_name}</p><p className="mt-0.5 text-xs text-cream-500">Started {formatDate(item.last_payment_at)}</p></div><span className="rounded-full border border-cream-300 px-2.5 py-1 text-xs capitalize text-cream-700">{item.status.replaceAll("_", " ")}</span></div>)}
            </div>
          </section>}
        </>
      )}
    </main>
  );
}
