"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Building2,
  Globe2,
  Calendar,
  Layers,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  DollarSign,
  Clock,
  Shield,
  BookOpen,
  Wrench,
  Package,
  TrendingUp,
  FileCheck,
  Users,
  ShieldCheck,
  Activity,
  Database,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import { getUser, setAuth } from "@/lib/auth";
import type { CountryInfo, IndustryInfo, ModuleCatalogItem } from "@/lib/types";

const MODULE_ICONS: Record<string, any> = {
  BookOpen,
  Package,
  Wrench,
  TrendingUp,
  FileCheck,
  Users,
  ShieldCheck,
  Activity,
  Layers,
};

export default function SetupWizardPage() {
  const router = useRouter();
  const [step, setStep] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [provisioning, setProvisioning] = useState<boolean>(false);
  const [provisionStepText, setProvisionStepText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  // Metadata from backend
  const [countries, setCountries] = useState<CountryInfo[]>([]);
  const [industries, setIndustries] = useState<IndustryInfo[]>([]);
  const [allModules, setAllModules] = useState<ModuleCatalogItem[]>([]);
  const [availableCharts, setAvailableCharts] = useState<string[]>([]);

  // User Selections
  const [companyName, setCompanyName] = useState<string>("");
  const [implementingFor, setImplementingFor] = useState<string>("My own business");
  const [companySize, setCompanySize] = useState<string>("11-50");
  const [industry, setIndustry] = useState<string>("Manufacturing");
  const [currentSystem, setCurrentSystem] = useState<string>("Excel / Spreadsheets");
  const [enabledModules, setEnabledModules] = useState<string[]>([
    "accounting",
    "inventory",
    "production",
    "commercial",
    "accounts_payable",
  ]);

  // Financial / Localization
  const [country, setCountry] = useState<string>("Pakistan");
  const [currency, setCurrency] = useState<string>("PKR");
  const [timezone, setTimezone] = useState<string>("Asia/Karachi");
  const [fyStart, setFyStart] = useState<string>("2026-07-01");
  const [fyEnd, setFyEnd] = useState<string>("2027-06-30");
  const [chartTemplate, setChartTemplate] = useState<string>("Standard GAAP");
  const [generateDemoData, setGenerateDemoData] = useState<boolean>(true);

  // Load initial setup data
  useEffect(() => {
    const user = getUser();
    if (user?.company_name) {
      setCompanyName(user.company_name);
    }

    async function loadData() {
      try {
        const [countriesData, industriesData] = await Promise.all([
          api.getSetupCountries(),
          api.getSetupIndustries(),
        ]);
        setCountries(countriesData);
        setIndustries(industriesData.industries);
        setAllModules(industriesData.all_modules);

        // Fetch charts for default country
        const charts = await api.getSetupCharts("Pakistan");
        setAvailableCharts(charts);
        if (charts.length > 0) setChartTemplate(charts[0]);
      } catch (err: any) {
        console.error("Failed to load setup wizard metadata", err);
      }
    }
    loadData();
  }, []);

  // When industry changes, automatically toggle recommended modules
  const handleIndustryChange = (newIndustry: string) => {
    setIndustry(newIndustry);
    const indData = industries.find((i) => i.name === newIndustry);
    if (indData && indData.default_modules) {
      setEnabledModules(indData.default_modules);
    }
  };

  // When country changes, automatically adapt currency, timezone, fiscal year, and CoA templates
  const handleCountryChange = async (newCountryName: string) => {
    setCountry(newCountryName);
    const cData = countries.find((c) => c.country_name === newCountryName);
    if (cData) {
      setCurrency(cData.currency);
      setTimezone(cData.timezone);

      // Auto-compute fiscal dates
      const currentYear = new Date().getFullYear();
      const sParts = cData.fiscal_year_start.split("-");
      const eParts = cData.fiscal_year_end.split("-");

      let sYear = currentYear;
      let eYear = currentYear;
      if (parseInt(sParts[0], 10) > new Date().getMonth() + 1) {
        sYear = currentYear - 1;
      }
      if (sParts[0] !== "01") {
        eYear = sYear + 1;
      }

      setFyStart(`${sYear}-${cData.fiscal_year_start}`);
      setFyEnd(`${eYear}-${cData.fiscal_year_end}`);
    }

    // Fetch localized CoA templates
    try {
      const charts = await api.getSetupCharts(newCountryName);
      setAvailableCharts(charts);
      if (charts.length > 0) {
        setChartTemplate(charts[0]);
      }
    } catch {
      // Keep existing chart template
    }
  };

  const toggleModule = (slug: string) => {
    if (slug === "accounting") return; // Accounting is mandatory
    setEnabledModules((prev) =>
      prev.includes(slug) ? prev.filter((m) => m !== slug) : [...prev, slug]
    );
  };

  const handleFinalSubmit = async () => {
    setError(null);
    setLoading(true);
    setProvisioning(true);

    const steps = [
      "Installing localized Chart of Accounts & Tax codes...",
      `Configuring ${industry} Cost Centers & Warehouses...`,
      "Creating 12-Month Fiscal Calendar...",
      "Generating Security Settings & Margin Defense Invariants...",
      generateDemoData ? "Seeding Realistic Industry Operations Data..." : "Initializing Clean-Slate Master Partitions...",
      "Cryptographically Chaining Genesis Block #0...",
    ];

    let stepIndex = 0;
    setProvisionStepText(steps[0]);
    const interval = setInterval(() => {
      stepIndex++;
      if (stepIndex < steps.length) {
        setProvisionStepText(steps[stepIndex]);
      }
    }, 700);

    try {
      const res = await api.completeSetup({
        country,
        industry,
        currency,
        timezone,
        fiscal_year_start: fyStart,
        fiscal_year_end: fyEnd,
        company_size: companySize,
        chart_of_accounts: chartTemplate,
        enabled_modules: enabledModules,
        generate_demo_data: generateDemoData,
      });

      clearInterval(interval);
      setProvisionStepText("Complete! Directing to Executive Control Center...");

      // Update stored auth with new JWT containing setup_complete: true
      const currentUser = getUser();
      if (currentUser) {
        currentUser.setup_complete = true;
        setAuth(res.access_token, currentUser);
      }

      setTimeout(() => {
        window.location.href = "/";
      }, 800);
    } catch (err: any) {
      clearInterval(interval);
      setProvisioning(false);
      setLoading(false);
      setError(err.message || "Failed to complete setup. Please check the logs.");
    }
  };

  return (
    <div className="min-h-screen bg-cream-50 flex flex-col justify-center items-center px-4 py-10">
      <div className="w-full max-w-3xl space-y-6">
        {/* Wizard Header & Stepper */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-cream-300 bg-cream-100 text-[11px] font-mono text-cream-800">
            <Sparkles className="h-3.5 w-3.5 text-sage-600" />
            <span>Autonomous ERP Setup Wizard &bull; {companyName || "Organization"}</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-cream-900">
            {step === 1 && "Tailor Your Autonomous Setup"}
            {step === 2 && "Configure Financial & Localization Substrate"}
            {step === 3 && "Review & Provision Enterprise Blueprint"}
          </h1>
          <p className="text-xs text-cream-700 max-w-xl mx-auto">
            {step === 1 && "Select your industry vertical and functional modules. The system will pre-configure specialized cost centers and workstations."}
            {step === 2 && "Configure your country localization. We will automatically load localized Chart of Accounts, tax roots, and fiscal periods."}
            {step === 3 && "Confirm your operational blueprint. Everything configured here directly generates underlying database partitions and cryptographic genesis blocks."}
          </p>

          {/* Stepper Progress Bar */}
          <div className="flex items-center justify-center gap-3 pt-2">
            {[
              { num: 1, label: "Persona & Modules" },
              { num: 2, label: "Financial Substrate" },
              { num: 3, label: "Review & Provision" },
            ].map((s) => (
              <div key={s.num} className="flex items-center gap-2">
                <div
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-mono font-medium transition-colors ${
                    step === s.num
                      ? "bg-cream-900 text-cream-50 ring-2 ring-cream-400"
                      : step > s.num
                      ? "bg-sage-600 text-white"
                      : "bg-cream-200 text-cream-700"
                  }`}
                >
                  {step > s.num ? <Check className="h-3.5 w-3.5" /> : s.num}
                </div>
                <span className={`text-xs font-medium ${step === s.num ? "text-cream-900 font-semibold" : "text-cream-600"}`}>
                  {s.label}
                </span>
                {s.num < 3 && <div className="h-px w-8 bg-cream-300" />}
              </div>
            ))}
          </div>
        </div>

        {/* Card Body */}
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 md:p-8 shadow-xs space-y-6">
          {error && (
            <div className="p-3.5 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
              {error}
            </div>
          )}

          {/* STEP 1: Persona & Modules */}
          {step === 1 && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1.5">
                    Who are you setting this up for?
                  </label>
                  <select
                    value={implementingFor}
                    onChange={(e) => setImplementingFor(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-800"
                  >
                    <option value="My own business">My own business</option>
                    <option value="A company I work for">A company I work for</option>
                    <option value="A client I'm consulting for">A client I&apos;m consulting for</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1.5">
                    How big is the team?
                  </label>
                  <select
                    value={companySize}
                    onChange={(e) => setCompanySize(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-800"
                  >
                    <option value="1–10">1–10 employees</option>
                    <option value="11–50">11–50 employees</option>
                    <option value="51–200">51–200 employees</option>
                    <option value="201–1,000">201–1,000 employees</option>
                    <option value="1,000+">1,000+ enterprise</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1.5">
                    What kind of work do you do? (Industry)
                  </label>
                  <select
                    value={industry}
                    onChange={(e) => handleIndustryChange(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 font-medium focus:outline-none focus:ring-1 focus:ring-cream-800"
                  >
                    {industries.map((ind) => (
                      <option key={ind.name} value={ind.name}>
                        {ind.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1.5">
                    What do you use today?
                  </label>
                  <select
                    value={currentSystem}
                    onChange={(e) => setCurrentSystem(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-800"
                  >
                    <option value="Excel / Spreadsheets">Excel / Spreadsheets</option>
                    <option value="Tally">Tally</option>
                    <option value="QuickBooks">QuickBooks</option>
                    <option value="Zoho">Zoho</option>
                    <option value="SAP">SAP ERP</option>
                    <option value="Oracle NetSuite">Oracle NetSuite</option>
                    <option value="Microsoft Dynamics">Microsoft Dynamics</option>
                    <option value="Nothing yet - starting fresh">Nothing yet - starting fresh</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              {/* Module Selection Grid */}
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-semibold text-cream-900">
                    Functional Modules to Implement
                  </label>
                  <span className="text-[11px] text-cream-600 font-mono">
                    Auto-tuned for {industry}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {allModules.map((mod) => {
                    const isChecked = enabledModules.includes(mod.slug);
                    const isMandatory = mod.slug === "accounting";
                    const IconComp = MODULE_ICONS[mod.icon] || Layers;

                    return (
                      <div
                        key={mod.slug}
                        onClick={() => toggleModule(mod.slug)}
                        className={`flex items-start gap-3 p-3 rounded-lg border transition-all cursor-pointer select-none ${
                          isChecked
                            ? "border-cream-400 bg-cream-50 ring-1 ring-cream-800/10"
                            : "border-cream-300/80 bg-cream-50/50 hover:bg-cream-50 opacity-60"
                        }`}
                      >
                        <div
                          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                            isChecked
                              ? "border-cream-900 bg-cream-900 text-cream-50"
                              : "border-cream-400 bg-white"
                          }`}
                        >
                          {isChecked && <Check className="h-3 w-3" />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <IconComp className="h-3.5 w-3.5 text-cream-800" />
                            <span className="text-xs font-semibold text-cream-900">
                              {mod.name}
                            </span>
                            {isMandatory && (
                              <span className="text-[9px] font-mono uppercase px-1 rounded bg-cream-200 text-cream-700">
                                Required
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-cream-600 mt-0.5 leading-tight">
                            {mod.description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Financial Foundation & Localization */}
          {step === 2 && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1.5 flex items-center gap-1">
                    <Globe2 className="h-3.5 w-3.5 text-cream-700" />
                    <span>Country of Operation</span>
                  </label>
                  <select
                    value={country}
                    onChange={(e) => handleCountryChange(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 font-medium focus:outline-none focus:ring-1 focus:ring-cream-800"
                  >
                    {countries.map((c) => (
                      <option key={c.country_name} value={c.country_name}>
                        {c.country_name} ({c.currency})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1.5 flex items-center gap-1">
                    <DollarSign className="h-3.5 w-3.5 text-cream-700" />
                    <span>Base Functional Currency</span>
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={3}
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-cream-800"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1.5 flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 text-cream-700" />
                    <span>Timezone</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 font-mono focus:outline-none focus:ring-1 focus:ring-cream-800"
                  />
                </div>
              </div>

              {/* Fiscal Year Configuration */}
              <div className="rounded-lg border border-cream-300 bg-cream-50 p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-cream-800" />
                  <span className="text-xs font-semibold text-cream-900">
                    Statutory Fiscal Year & Financial Calendar
                  </span>
                </div>
                <p className="text-[11px] text-cream-700">
                  Defines the 12-month period boundaries for financial statements, journal locking, and tax reporting.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                  <div>
                    <label className="block text-[11px] font-medium text-cream-800 mb-1">
                      Financial Year Begins On
                    </label>
                    <input
                      type="date"
                      required
                      value={fyStart}
                      onChange={(e) => setFyStart(e.target.value)}
                      className="w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 font-mono focus:outline-none focus:ring-1 focus:ring-cream-800"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-cream-800 mb-1">
                      Financial Year Ends On
                    </label>
                    <input
                      type="date"
                      required
                      value={fyEnd}
                      onChange={(e) => setFyEnd(e.target.value)}
                      className="w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 font-mono focus:outline-none focus:ring-1 focus:ring-cream-800"
                    />
                  </div>
                </div>
              </div>

              {/* Localized Chart of Accounts */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-cream-900 flex items-center gap-1.5">
                    <BookOpen className="h-4 w-4 text-cream-800" />
                    <span>Localized Chart of Accounts Template</span>
                  </label>
                  <span className="text-[10px] font-mono text-sage-700 bg-sage-50 px-2 py-0.5 rounded border border-sage-500/20">
                    ERPNext Verified Reference
                  </span>
                </div>

                <select
                  value={chartTemplate}
                  onChange={(e) => setChartTemplate(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2.5 text-xs text-cream-900 font-medium focus:outline-none focus:ring-1 focus:ring-cream-800"
                >
                  {availableCharts.map((ch) => (
                    <option key={ch} value={ch}>
                      {ch}
                    </option>
                  ))}
                </select>

                <p className="text-[11px] text-cream-600">
                  Loads standard localized tax asset/liability accounts, regional statutory structure, and guarantees compatibility with the autonomous 3-way match, ledger and bank clearing engines.
                </p>
              </div>
            </div>
          )}

          {/* STEP 3: Review & Provision */}
          {step === 3 && (
            <div className="space-y-5">
              {/* Configuration Summary Card */}
              <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-cream-300 pb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-cream-900">
                      Enterprise Operational Blueprint
                    </h3>
                    <p className="text-[11px] text-cream-600">
                      Summary of structural partitions ready to be committed
                    </p>
                  </div>
                  <span className="px-2.5 py-1 rounded-full bg-sage-100 text-sage-800 border border-sage-500/30 text-[10px] font-mono font-medium">
                    Ready to Provision
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-3.5 text-xs">
                  <div>
                    <span className="text-cream-600 block text-[10px]">Organization</span>
                    <span className="font-semibold text-cream-900">{companyName}</span>
                  </div>
                  <div>
                    <span className="text-cream-600 block text-[10px]">Industry Vertical</span>
                    <span className="font-semibold text-cream-900">{industry}</span>
                  </div>
                  <div>
                    <span className="text-cream-600 block text-[10px]">Team Size</span>
                    <span className="font-semibold text-cream-900">{companySize}</span>
                  </div>
                  <div>
                    <span className="text-cream-600 block text-[10px]">Jurisdiction</span>
                    <span className="font-semibold text-cream-900">{country}</span>
                  </div>
                  <div>
                    <span className="text-cream-600 block text-[10px]">Base Currency</span>
                    <span className="font-mono font-semibold text-cream-900">{currency}</span>
                  </div>
                  <div>
                    <span className="text-cream-600 block text-[10px]">Fiscal Year</span>
                    <span className="font-mono text-cream-900">{fyStart.slice(5)} to {fyEnd.slice(5)}</span>
                  </div>
                </div>

                <div className="border-t border-cream-300 pt-3 space-y-1.5">
                  <div className="text-[11px] font-semibold text-cream-900">
                    Selected Chart of Accounts:
                  </div>
                  <div className="text-xs font-mono text-cream-800 bg-white p-2 rounded border border-cream-300">
                    {chartTemplate}
                  </div>
                </div>

                <div className="border-t border-cream-300 pt-3 space-y-1.5">
                  <div className="text-[11px] font-semibold text-cream-900">
                    Active Modules ({enabledModules.length}):
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {enabledModules.map((slug) => (
                      <span
                        key={slug}
                        className="px-2 py-0.5 rounded bg-cream-200 text-cream-800 text-[10px] font-mono"
                      >
                        {slug}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Demo Data Option Checkbox */}
              <div
                onClick={() => setGenerateDemoData(!generateDemoData)}
                className="flex items-start gap-3 p-4 rounded-lg border border-cream-300 bg-cream-50 hover:bg-cream-100/70 cursor-pointer transition-colors"
              >
                <div
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                    generateDemoData
                      ? "border-cream-900 bg-cream-900 text-cream-50"
                      : "border-cream-400 bg-white"
                  }`}
                >
                  {generateDemoData && <Check className="h-3 w-3" />}
                </div>
                <div>
                  <div className="text-xs font-semibold text-cream-900 flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-cream-700" />
                    <span>Generate Realistic Demo Data for Exploration</span>
                  </div>
                  <p className="text-[11px] text-cream-600 mt-0.5">
                    Seeds realistic sample items, trade customers, vendors, an initial Purchase Order, Goods Receipt, and a 3-Way Matched invoice in {currency} so you can test workflows immediately.
                  </p>
                </div>
              </div>

              {/* Security & Cryptographic Invariant Notice */}
              <div className="flex items-center gap-2 p-3 rounded-lg bg-cream-200/60 text-[11px] text-cream-700 font-mono">
                <Shield className="h-4 w-4 text-sage-600 shrink-0" />
                <span>
                  All seeded accounts and records are cryptographically anchored to Genesis Block #0 (SHA-256).
                </span>
              </div>
            </div>
          )}

          {/* Provisioning Progress Overlay */}
          {provisioning && (
            <div className="p-5 rounded-lg border border-cream-400 bg-cream-900 text-cream-50 space-y-3 animate-pulse">
              <div className="flex items-center gap-2.5">
                <div className="h-3 w-3 rounded-full bg-sage-400 animate-ping" />
                <span className="text-xs font-mono font-semibold tracking-wide uppercase">
                  Provisioning Operational Substrate...
                </span>
              </div>
              <p className="text-xs text-cream-200 font-mono">
                {provisionStepText}
              </p>
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between border-t border-cream-300 pt-5">
            {step > 1 ? (
              <button
                type="button"
                disabled={loading}
                onClick={() => setStep(step - 1)}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-cream-300 bg-cream-50 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors disabled:opacity-50"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Back</span>
              </button>
            ) : (
              <div />
            )}

            {step < 3 ? (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-cream-900 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
              >
                <span>Continue</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            ) : (
              <button
                type="button"
                disabled={loading}
                onClick={handleFinalSubmit}
                className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-cream-900 text-xs font-semibold text-cream-50 hover:bg-cream-800 transition-all shadow-sm disabled:opacity-50"
              >
                <CheckCircle2 className="h-4 w-4 text-sage-400" />
                <span>Complete Setup & Launch ERP</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
