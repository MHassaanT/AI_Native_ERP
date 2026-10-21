"use client";

import Link from "next/link";
import { HRDeepWorkbench } from "@/components/hr-deep-workbench";

export default function FullAndFinalPage() {
  return <main className="mx-auto max-w-6xl space-y-5 p-6"><header><Link href="/workforce" className="text-xs font-medium text-stone-600 hover:text-stone-900">← Workforce</Link><h1 className="mt-2 text-2xl font-semibold text-stone-900">Full &amp; Final Settlement</h1><p className="mt-1 text-sm text-stone-600">Enter settlement earnings and deductions, calculate the net amount, submit for approval, and record payment.</p></header><HRDeepWorkbench onlyResources={["full-and-final-statements", "full-and-final-items"]}/></main>;
}
