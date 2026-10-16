import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Boxes,
  BarChart3,
  BrainCircuit,
  Check,
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

const modules = [
  { icon: BarChart3, title: "Finance & governance", detail: "Track financial health, manage approvals, and keep a clear audit trail." },
  { icon: Boxes, title: "Connected operations", detail: "Bring inventory, procurement, production, and people into one workspace." },
  { icon: Workflow, title: "Workflow management", detail: "Coordinate repeatable work and keep every task moving forward." },
  { icon: CheckCircle2, title: "Quality & control", detail: "Keep operational checks, exceptions, and decisions visible to your team." },
];

const aiSteps = [
  { number: "01", title: "Understand the request", detail: "AI-assisted intake helps organize incoming emails, RFQs, and operational work." },
  { number: "02", title: "Bring forward context", detail: "Relevant records and workflow details help teams see what needs attention." },
  { number: "03", title: "Keep people in control", detail: "Teams review actions, follow approvals, and retain a clear record of decisions." },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#f8faf7] text-cream-900">
      <header className="mx-auto flex h-[76px] max-w-7xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="AI-Native ERP home">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sage-600 text-xs font-bold tracking-wide text-white">AI</span>
          <span>
            <span className="block text-sm font-semibold tracking-tight">AI-Native ERP</span>
            <span className="block text-[11px] text-cream-600">One clear view of your business</span>
          </span>
        </Link>
        <nav className="flex items-center gap-2 sm:gap-3">
          <Link href="#features" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-cream-700 transition hover:bg-white hover:text-cream-900 md:inline-flex">Features</Link>
          <Link href="#ai-capabilities" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-cream-700 transition hover:bg-white hover:text-cream-900 md:inline-flex">AI capabilities</Link>
          <Link href="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-cream-700 transition hover:bg-white hover:text-cream-900">Log in</Link>
          <Link href="/signup" className="inline-flex items-center gap-2 rounded-lg bg-cream-900 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-sage-700">
            Get started <ArrowRight className="h-4 w-4" />
          </Link>
        </nav>
      </header>

      <section className="mx-auto grid max-w-7xl items-center gap-14 px-5 pb-20 pt-12 sm:px-8 sm:pt-20 lg:grid-cols-[1fr_0.95fr] lg:gap-12 lg:pb-28">
        <div className="max-w-2xl">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-sage-200 bg-white/80 px-3 py-1.5 text-xs font-medium text-sage-700 shadow-sm">
            <Sparkles className="h-3.5 w-3.5" /> A calmer way to run your business
          </div>
          <h1 className="max-w-xl text-4xl font-semibold leading-[1.08] tracking-[-0.045em] text-cream-900 sm:text-5xl lg:text-[62px]">
            Your whole business, <span className="text-sage-600">working as one.</span>
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-cream-600 sm:text-lg sm:leading-8">
            Bring finance, operations, and everyday work into one considered workspace. See what matters, keep teams aligned, and move forward with confidence.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/signup" className="inline-flex h-12 items-center justify-center gap-2 rounded-lg border-2 border-sage-700 bg-sage-500 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-sage-700">
              Create your workspace <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/login" className="inline-flex h-12 items-center justify-center gap-2 rounded-lg border border-cream-300 bg-white px-5 text-sm font-semibold text-cream-800 transition hover:border-sage-300 hover:bg-sage-50">
              Sign in to your account
            </Link>
          </div>
          <div className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-xs text-cream-600">
            {["A workspace for every team", "Built-in controls", "One connected operation"].map((item) => (
              <span key={item} className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-sage-600" />{item}</span>
            ))}
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-[560px]">
          <div className="absolute -inset-8 rounded-[40px] bg-gradient-to-br from-sage-100/70 via-transparent to-[#edf1e9] blur-2xl" />
          <div className="relative rounded-2xl border border-cream-200 bg-white p-3 shadow-[0_24px_80px_-32px_rgba(37,55,40,0.28)] sm:p-4">
            <div className="flex items-center justify-between border-b border-cream-100 px-2 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sage-50 text-sage-700"><BarChart3 className="h-4 w-4" /></span>
                <div><p className="text-xs font-semibold">Business overview</p><p className="mt-0.5 text-[10px] text-cream-500">Monday, October 19</p></div>
              </div>
              <span className="rounded-full border border-sage-100 bg-sage-50 px-2.5 py-1 text-[10px] font-medium text-sage-700">All systems clear</span>
            </div>
            <div className="grid grid-cols-3 gap-2.5 py-3 sm:gap-3 sm:py-4">
              {[["Cash position", "$248.6k", "+8.2%"], ["Open orders", "184", "On track"], ["Team capacity", "92%", "This week"]].map(([label, value, note]) => (
                <div key={label} className="rounded-xl border border-cream-100 bg-[#fbfcfa] p-3 sm:p-4">
                  <p className="text-[9px] leading-4 text-cream-500 sm:text-[10px]">{label}</p>
                  <p className="mt-2 text-base font-semibold tracking-tight text-cream-900 sm:text-xl">{value}</p>
                  <p className="mt-1 text-[9px] text-sage-700 sm:text-[10px]">{note}</p>
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-cream-100 p-4 sm:p-5">
              <div className="flex items-start justify-between">
                <div><p className="text-xs font-semibold">Operations at a glance</p><p className="mt-1 text-[10px] text-cream-500">Activity across your workspace</p></div>
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-sage-50 text-sage-700"><Workflow className="h-3.5 w-3.5" /></span>
              </div>
              <div className="mt-5 flex h-24 items-end gap-2 sm:h-28 sm:gap-3">
                {[35, 48, 43, 66, 55, 72, 61, 86, 70, 94, 78, 100].map((height, index) => (
                  <div key={index} className="flex-1 rounded-t-md bg-sage-100" style={{ height: `${height}%` }}>
                    <div className={`h-full w-full rounded-t-md ${index > 8 ? "bg-sage-500" : ""}`} />
                  </div>
                ))}
              </div>
              <div className="mt-3 flex justify-between text-[9px] text-cream-400"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span></div>
            </div>
            <div className="mt-3 flex items-center gap-3 rounded-xl bg-[#f6f8f5] p-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-sage-700 shadow-sm"><ShieldCheck className="h-4 w-4" /></span>
              <div className="min-w-0 flex-1"><p className="text-[11px] font-semibold">Your controls are in place</p><p className="mt-0.5 truncate text-[10px] text-cream-500">Approvals, access, and audit history in one view</p></div>
              <ArrowUpRight className="h-4 w-4 text-cream-400" />
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="border-y border-cream-200/80 bg-white/65">
        <div className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-16">
          <div className="max-w-xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage-700">Features</p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">The tools your teams need, together.</h2>
            <p className="mt-3 text-sm leading-6 text-cream-600">A connected set of capabilities for the daily work of running your business.</p>
          </div>
          <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {modules.map(({ icon: Icon, title, detail }) => (
              <article key={title} className="rounded-xl border border-cream-200 bg-white p-5 shadow-sm">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sage-50 text-sage-700"><Icon className="h-5 w-5" /></span>
                <h3 className="mt-4 text-sm font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-cream-600">{detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="ai-capabilities" className="mx-auto grid max-w-7xl gap-10 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-sage-100 bg-white px-3 py-1.5 text-xs font-medium text-sage-700 shadow-sm">
            <Sparkles className="h-3.5 w-3.5" /> AI, with oversight
          </div>
          <h2 className="mt-5 max-w-lg text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">Useful intelligence, built into the work.</h2>
          <p className="mt-4 max-w-lg text-sm leading-7 text-cream-600 sm:text-base">
            AI capabilities help teams handle incoming requests and coordinate workflows, while approvals, roles, and operational controls keep people at the center of decisions.
          </p>
          <Link href="/signup" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-sage-700 hover:text-sage-500">
            Explore your workspace <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="rounded-2xl border border-cream-200 bg-white p-5 shadow-sm sm:p-7">
          <div className="mb-5 flex items-center gap-3 border-b border-cream-100 pb-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sage-50 text-sage-700"><BrainCircuit className="h-5 w-5" /></span>
            <div><p className="text-sm font-semibold">A clear path from request to action</p><p className="mt-1 text-xs text-cream-500">AI support in a controlled workflow</p></div>
          </div>
          <div className="space-y-5">
            {aiSteps.map((step) => (
              <div key={step.number} className="flex gap-4">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-sage-100 bg-sage-50 text-[10px] font-semibold text-sage-700">{step.number}</span>
                <div><h3 className="text-sm font-semibold">{step.title}</h3><p className="mt-1 text-sm leading-6 text-cream-600">{step.detail}</p></div>
              </div>
            ))}
          </div>
          <div className="mt-6 flex items-center gap-2 rounded-lg border border-sage-100 bg-sage-50/70 px-3 py-2.5 text-xs text-sage-700">
            <ShieldCheck className="h-4 w-4 shrink-0" /> Role-based access and approvals stay part of the process.
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-6 text-xs text-cream-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <span>© {new Date().getFullYear()} AI-Native ERP</span>
        <span>One thoughtful workspace for the work that matters.</span>
      </footer>
    </main>
  );
}
