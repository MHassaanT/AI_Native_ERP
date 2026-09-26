"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Clock,
  ArrowRight,
  Sparkles,
  BookOpen,
  Package,
  Wrench,
  TrendingUp,
  FileCheck,
  Users,
  ShieldCheck,
  Activity,
  Layers,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";
import type { OnboardingOverview, OnboardingModuleProgress, OnboardingStepItem } from "@/lib/types";

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

export function ModuleOnboardingWidget() {
  const [data, setData] = useState<OnboardingOverview | null>(null);
  const [selectedModuleSlug, setSelectedModuleSlug] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [validatingStepId, setValidatingStepId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ stepId: string; message: string; isError?: boolean } | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchProgress = async () => {
    try {
      const res: OnboardingOverview = await api.getOnboardingProgress();
      setData(res);
      if (!selectedModuleSlug && res.modules.length > 0) {
        // Default to first incomplete module, or first module
        const firstIncomplete = res.modules.find((m) => !m.is_complete);
        setSelectedModuleSlug(firstIncomplete ? firstIncomplete.module_slug : res.modules[0].module_slug);
      }
    } catch (err) {
      console.error("Failed to fetch onboarding checklist progress", err);
    }
  };

  useEffect(() => {
    fetchProgress();
  }, []);

  if (!data || data.modules.length === 0) {
    return null;
  }

  // If 100% complete and collapsed, render minimal badge
  if (data.is_all_complete && collapsed) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-sage-500/30 bg-sage-50 px-4 py-2.5 text-xs text-sage-800 shadow-xs">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-sage-600" />
          <span className="font-semibold">Enterprise Onboarding 100% Complete</span>
          <span className="text-[11px] text-sage-700">&bull; All operational partitions active & verified</span>
        </div>
        <button
          onClick={() => setCollapsed(false)}
          className="text-[11px] font-medium text-sage-800 hover:underline"
        >
          View Checklist
        </button>
      </div>
    );
  }

  const activeModule = data.modules.find((m) => m.module_slug === selectedModuleSlug) || data.modules[0];
  const ActiveIcon = MODULE_ICONS[activeModule?.icon] || Layers;

  const handleValidateStep = async (step: OnboardingStepItem) => {
    setValidatingStepId(step.step_id);
    setActionFeedback(null);
    try {
      const res = await api.validateOnboardingStep(step.step_id);
      setActionFeedback({
        stepId: step.step_id,
        message: res.message,
        isError: !res.is_complete,
      });
      await fetchProgress();
    } catch (err: any) {
      setActionFeedback({
        stepId: step.step_id,
        message: err.message || "Failed to validate step",
        isError: true,
      });
    } finally {
      setValidatingStepId(null);
    }
  };

  const handleCompleteManualStep = async (stepId: string) => {
    setLoading(true);
    setActionFeedback(null);
    try {
      await api.completeOnboardingStep(stepId);
      await fetchProgress();
    } catch (err: any) {
      console.error("Failed to complete manual step", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSkipModule = async (slug: string) => {
    setLoading(true);
    try {
      await api.skipOnboardingModule(slug);
      await fetchProgress();
    } catch (err: any) {
      console.error("Failed to skip module", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 md:p-6 shadow-xs space-y-4">
      {/* Widget Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cream-300 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-sage-500 animate-pulse" />
            <h2 className="text-sm font-semibold text-cream-900">
              Interactive Enterprise Onboarding Checklist
            </h2>
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-cream-200 text-cream-800 border border-cream-300">
              Stage 3 &bull; Live DB Grounded
            </span>
          </div>
          <p className="text-xs text-cream-700 mt-0.5">
            Steps automatically verify actual database entries. Create records in each module to complete your operational setup.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs font-mono font-semibold text-cream-900">
              {data.completed_steps} / {data.total_steps} Completed ({data.overall_progress_pct}%)
            </div>
            <div className="w-36 h-1.5 bg-cream-200 rounded-full overflow-hidden mt-1">
              <div
                className="h-full bg-sage-600 transition-all duration-500"
                style={{ width: `${data.overall_progress_pct}%` }}
              />
            </div>
          </div>

          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 rounded-md text-cream-700 hover:bg-cream-200 transition-colors"
            title={collapsed ? "Expand Checklist" : "Collapse Checklist"}
          >
            {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="space-y-4">
          {/* Module Tab Selector */}
          <div className="flex flex-wrap gap-1.5 border-b border-cream-200 pb-2">
            {data.modules.map((m) => {
              const IconComp = MODULE_ICONS[m.icon] || Layers;
              const isSelected = m.module_slug === selectedModuleSlug;

              return (
                <button
                  key={m.module_slug}
                  onClick={() => setSelectedModuleSlug(m.module_slug)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isSelected
                      ? "bg-cream-900 text-cream-50 shadow-xs"
                      : "bg-cream-50 text-cream-700 hover:bg-cream-200/70 border border-cream-300"
                  }`}
                >
                  <IconComp className="h-3.5 w-3.5" />
                  <span>{m.module_name}</span>
                  <span
                    className={`ml-1 text-[10px] font-mono px-1.5 py-0.2 rounded ${
                      m.is_complete
                        ? isSelected
                          ? "bg-sage-600 text-white"
                          : "bg-sage-100 text-sage-800"
                        : isSelected
                        ? "bg-cream-700 text-cream-100"
                        : "bg-cream-200 text-cream-700"
                    }`}
                  >
                    {m.completed_steps}/{m.total_steps}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Active Module Steps List */}
          {activeModule && (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs text-cream-700 px-1">
                <div className="flex items-center gap-1.5">
                  <ActiveIcon className="h-4 w-4 text-cream-800" />
                  <span className="font-semibold text-cream-900">{activeModule.module_name} Workflow</span>
                  <span className="text-[11px] text-cream-600">&bull; {activeModule.module_description}</span>
                </div>

                {!activeModule.is_complete && (
                  <button
                    onClick={() => handleSkipModule(activeModule.module_slug)}
                    disabled={loading}
                    className="text-[11px] text-cream-600 hover:text-cream-900 font-mono underline"
                  >
                    Skip Module
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 gap-2">
                {activeModule.steps.map((st) => (
                  <div
                    key={st.step_id}
                    className={`flex flex-col sm:flex-row sm:items-center justify-between p-3.5 rounded-lg border transition-all ${
                      st.is_complete
                        ? "border-sage-500/20 bg-sage-50/40 text-cream-800"
                        : "border-cream-300 bg-cream-50 hover:border-cream-400"
                    }`}
                  >
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <div className="mt-0.5">
                        {st.is_complete ? (
                          <CheckCircle2 className="h-4 w-4 text-sage-600 shrink-0" />
                        ) : (
                          <div className="h-4 w-4 rounded-full border border-cream-400 bg-white flex items-center justify-center text-[10px] font-mono text-cream-600">
                            {st.sort_order}
                          </div>
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`text-xs font-semibold ${
                              st.is_complete ? "line-through text-cream-600" : "text-cream-900"
                            }`}
                          >
                            {st.step_title}
                          </span>
                          <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-cream-200 text-cream-700">
                            {st.action_type.replace("_", " ")}
                          </span>
                          {st.reference_entity && (
                            <span className="text-[9px] font-mono text-cream-600">
                              [{st.reference_entity}]
                            </span>
                          )}
                        </div>

                        {st.step_description && (
                          <p className="text-[11px] text-cream-600 mt-0.5">
                            {st.step_description}
                          </p>
                        )}

                        {actionFeedback?.stepId === st.step_id && (
                          <p
                            className={`text-[10px] mt-1 font-mono ${
                              actionFeedback.isError ? "text-terracotta-600" : "text-sage-700 font-semibold"
                            }`}
                          >
                            {actionFeedback.message}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Action Controls */}
                    <div className="flex items-center gap-2 mt-2 sm:mt-0 sm:ml-4 shrink-0">
                      {st.is_complete ? (
                        <span className="text-[11px] font-mono text-sage-700 flex items-center gap-1 font-medium">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          <span>Verified</span>
                        </span>
                      ) : (
                        <>
                          <button
                            onClick={() => handleValidateStep(st)}
                            disabled={validatingStepId === st.step_id}
                            className="flex items-center gap-1 px-2.5 py-1 rounded border border-cream-300 bg-white text-[11px] font-medium text-cream-800 hover:bg-cream-100 transition-colors disabled:opacity-50"
                            title="Query database to verify record exists"
                          >
                            <RefreshCw
                              className={`h-3 w-3 ${validatingStepId === st.step_id ? "animate-spin" : ""}`}
                            />
                            <span>Verify in DB</span>
                          </button>

                          {st.action_type === "CREATE_ENTRY" && st.target_route && (
                            <Link
                              href={st.target_route}
                              className="flex items-center gap-1 px-3 py-1 rounded bg-cream-900 text-cream-50 text-[11px] font-medium hover:bg-cream-800 transition-colors"
                            >
                              <span>Create &rarr;</span>
                            </Link>
                          )}

                          {st.action_type !== "CREATE_ENTRY" && st.target_route && (
                            <Link
                              href={st.target_route}
                              className="flex items-center gap-1 px-2.5 py-1 rounded border border-cream-300 bg-white text-[11px] font-medium text-cream-800 hover:bg-cream-100 transition-colors"
                            >
                              <span>View</span>
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          )}

                          {st.action_type !== "CREATE_ENTRY" && (
                            <button
                              onClick={() => handleCompleteManualStep(st.step_id)}
                              disabled={loading}
                              className="px-2.5 py-1 rounded bg-cream-200 text-cream-800 text-[11px] font-medium hover:bg-cream-300 transition-colors disabled:opacity-50"
                            >
                              Mark Done
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
