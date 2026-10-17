"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Compass, X } from "lucide-react";
import { getUser } from "@/lib/auth";
import { NAV_GROUPS } from "./sidebar";

type TourStep = { title: string; description: string; href?: string; actionLabel?: string };

const pageDescriptions: Record<string, string> = {
  "/overview": "Your command centre for the health, activity, and next actions across the workspace.",
  "/inbox": "Connect and review inbound email, RFQs, and messages before they become operational work.",
  "/workflows": "See workflow progress, exceptions, and recovery actions in one place.",
  "/workforce": "Coordinate people, attendance, leave, and shift activity.",
  "/recruitment": "Create openings, review candidates, and use evidence-backed screening with recruiter oversight.",
  "/commercial": "Manage customers, quotations, orders, and pricing decisions.",
  "/crm": "Keep sales opportunities and customer support work moving.",
  "/whatsapp": "Pair WhatsApp, prepare approved knowledge, and supervise customer support conversations.",
  "/procurement": "Create requisitions, source suppliers, and follow purchasing through receipt.",
  "/pos": "Process in-person sales with inventory and financial records kept in sync.",
  "/production": "Plan bills of materials, work orders, and shop-floor production.",
  "/quality": "Record inspections, exceptions, and quality controls.",
  "/inventory": "Maintain items, warehouses, stock positions, and replenishment activity.",
  "/subcontracting": "Track outside processing and the materials moving through it.",
  "/maintenance": "Schedule preventive work and respond to equipment issues.",
  "/assets": "Manage fixed assets, depreciation, and asset maintenance history.",
  "/projects": "Plan projects, assign tasks, and review logged time.",
  "/reports": "Review financial and operational reports for your workspace.",
  "/billing": "Create invoices and manage customer billing activity.",
  "/billing/subscription": "Review the workspace plan, payment status, and renewal details.",
  "/accounts-payable": "Match supplier invoices against orders and goods receipts before payment.",
  "/bank-reconciliation": "Match bank activity against accounting records and resolve differences.",
  "/ledger": "Inspect the general ledger and the controls behind each posting.",
  "/audit": "Review the tenant-scoped audit trail and operational evidence.",
};

function storageKey(id: string) {
  const user = getUser();
  return `ai_erp_tour_${id}_${user?.tenant_id || "workspace"}`;
}

function TourDialog({ steps, index, onPrevious, onNext, onDismiss, action }: {
  steps: TourStep[];
  index: number;
  onPrevious: () => void;
  onNext: () => void;
  onDismiss: () => void;
  action?: () => void;
}) {
  const step = steps[index];
  const last = index === steps.length - 1;
  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-cream-900/20 p-4 sm:items-center" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="guided-tour-title" className="w-full max-w-md rounded-2xl border border-cream-200 bg-white p-5 shadow-[0_24px_80px_-24px_rgba(32,41,35,0.45)] sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sage-50 text-sage-700"><Compass className="h-5 w-5" /></div>
          <button onClick={onDismiss} className="rounded-lg p-1 text-cream-500 hover:bg-cream-100 hover:text-cream-900" aria-label="Skip tour"><X className="h-5 w-5" /></button>
        </div>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.14em] text-sage-700">Guided workspace tour · {index + 1} of {steps.length}</p>
        <h2 id="guided-tour-title" className="mt-2 text-xl font-semibold tracking-tight text-cream-900">{step.title}</h2>
        <p className="mt-2 text-sm leading-6 text-cream-700">{step.description}</p>
        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-cream-200"><div className="h-full rounded-full bg-sage-500 transition-all" style={{ width: `${((index + 1) / steps.length) * 100}%` }} /></div>
        {action && step.actionLabel && <button onClick={action} className="mt-5 w-full rounded-lg border border-sage-300 bg-sage-50 px-3 py-2.5 text-sm font-semibold text-sage-800 hover:bg-sage-100">{step.actionLabel} — then continue your setup</button>}
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button onClick={onPrevious} disabled={index === 0} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-cream-300 px-3 py-2 text-sm font-medium text-cream-700 hover:bg-cream-100 disabled:cursor-not-allowed disabled:opacity-40"><ArrowLeft className="h-4 w-4" />Previous</button>
          <button onClick={onNext} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-sage-600 px-3 py-2 text-sm font-semibold text-white hover:bg-sage-700">{last ? "Finish" : "Next"}<ArrowRight className="h-4 w-4" /></button>
        </div>
        <button onClick={onDismiss} className="mt-4 text-xs text-cream-500 underline underline-offset-2 hover:text-cream-800">Skip tour</button>
      </section>
    </div>
  );
}

export function WorkspaceTour() {
  const pathname = usePathname();
  const router = useRouter();
  const steps = useMemo(() => NAV_GROUPS.flatMap((group) => group.items.map((item) => ({ title: item.label, href: item.href, description: pageDescriptions[item.href] || `Explore ${item.label} for this area of your workspace.` }))), []);
  const [index, setIndex] = useState<number | null>(null);

  useEffect(() => {
    const user = getUser();
    if (!user?.setup_complete || pathname === "/setup" || pathname === "/billing/subscription") return;
    try {
      if (localStorage.getItem(storageKey("workspace")) !== "done") setIndex(Math.max(0, steps.findIndex((step) => step.href === pathname)));
    } catch { /* Storage can be unavailable in restricted browser contexts. */ }
  }, [pathname, steps]);

  if (index === null) return null;
  const end = () => { try { localStorage.setItem(storageKey("workspace"), "done"); } catch {} setIndex(null); };
  const move = (nextIndex: number) => { setIndex(nextIndex); const href = steps[nextIndex]?.href; if (href && href !== pathname) router.push(href); };
  return <TourDialog steps={steps} index={index} onPrevious={() => move(Math.max(0, index - 1))} onNext={() => index === steps.length - 1 ? end() : move(index + 1)} onDismiss={end} />;
}

export function AgentSetupTour({ id, steps }: { id: string; steps: TourStep[] }) {
  const [index, setIndex] = useState<number | null>(null);
  const [minimized, setMinimized] = useState(false);
  useEffect(() => {
    try { if (localStorage.getItem(storageKey(id)) !== "done") setIndex(0); } catch { setIndex(0); }
  }, [id]);
  if (index === null) return null;
  const end = () => { try { localStorage.setItem(storageKey(id), "done"); } catch {} setIndex(null); };
  const action = () => {
    const href = steps[index].href;
    setMinimized(true);
    if (!href) return;
    if (href.startsWith("#")) {
      document.querySelector(href)?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    window.location.assign(href);
  };
  if (minimized) {
    return (
      <button
        type="button"
        onClick={() => setMinimized(false)}
        className="fixed bottom-5 right-5 z-[90] inline-flex items-center gap-2 rounded-full border border-sage-700 bg-sage-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-sage-700"
      >
        <Compass className="h-4 w-4" /> Resume setup guide · {index + 1}/{steps.length}
      </button>
    );
  }
  return <TourDialog steps={steps} index={index} onPrevious={() => setIndex(Math.max(0, index - 1))} onNext={() => index === steps.length - 1 ? end() : setIndex(index + 1)} onDismiss={end} action={action} />;
}
