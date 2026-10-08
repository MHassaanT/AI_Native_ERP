"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Search,
  Filter,
  Check,
  X,
  FileText,
  DollarSign,
  Package,
  Layers,
  Activity,
  Users,
  ChevronDown,
  ChevronRight,
  MessageSquare,
} from "lucide-react";
import { api } from "@/lib/api";

interface AgentApproval {
  approval_id: string;
  tenant_id: string;
  run_id: string;
  agent_id: string;
  agent_name: string;
  domain: string;
  action_type: string;
  action_payload: any;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  required_role: string;
  ai_rationale: string;
  status: "PENDING" | "APPROVED" | "MODIFIED" | "REJECTED" | "AUTO_APPROVED";
  action_execution_status: "NOT_STARTED" | "NOT_REQUIRED" | "SUCCEEDED" | "FAILED" | "UNKNOWN";
  action_execution_result?: {
    status?: string;
    document_type?: string;
    document_id?: string;
    previous_credit_limit?: string;
    new_credit_limit?: string;
  } | null;
  reviewed_by?: string | null;
  reviewer_notes?: string | null;
  modified_payload?: any | null;
  created_at: string;
  reviewed_at?: string | null;
}

const DOMAIN_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  PROCUREMENT: { label: "Procurement", color: "bg-sage-100 text-sage-800 border-sage-300", icon: Package },
  FINANCE: { label: "Finance & GL", color: "bg-indigo-50 text-indigo-800 border-indigo-200", icon: DollarSign },
  MANUFACTURING: { label: "Quality & MES", color: "bg-amberGold-100 text-amberGold-800 border-amberGold-300", icon: Activity },
  HR: { label: "HR & Workforce", color: "bg-cyan-50 text-cyan-800 border-cyan-200", icon: Users },
  INVENTORY: { label: "Inventory", color: "bg-purple-50 text-purple-800 border-purple-200", icon: Layers },
  SALES: { label: "Sales & SDR", color: "bg-blue-50 text-blue-800 border-blue-200", icon: FileText },
};

const RISK_BADGES: Record<string, { label: string; badge: string }> = {
  CRITICAL: { label: "CRITICAL", badge: "bg-terracotta-100 text-terracotta-800 border-terracotta-300" },
  HIGH: { label: "HIGH RISK", badge: "bg-terracotta-100 text-terracotta-800 border-terracotta-300" },
  MEDIUM: { label: "MEDIUM", badge: "bg-amberGold-100 text-amberGold-800 border-amberGold-300" },
  LOW: { label: "LOW RISK", badge: "bg-cream-200 text-cream-700 border-cream-300" },
};

const EXECUTABLE_APPROVAL_ACTIONS = new Set([
  "CREATE_PURCHASE_ORDER",
  "POST_GL_JOURNAL",
  "MODIFY_CREDIT_LIMIT",
]);

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<AgentApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("PENDING");
  const [filterDomain, setFilterDomain] = useState<string>("ALL");
  const [filterRisk, setFilterRisk] = useState<string>("ALL");
  const [expandedPayloads, setExpandedPayloads] = useState<Record<string, boolean>>({});

  // Action modals / state
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [actionModal, setActionModal] = useState<{
    approval: AgentApproval;
    decision: "APPROVED" | "REJECTED";
  } | null>(null);
  const [reviewerNotes, setReviewerNotes] = useState("");
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchApprovals = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.listApprovals();
      if (Array.isArray(data)) {
        setApprovals(data);
      }
    } catch (err: any) {
      console.error("Failed to load approvals:", err);
      setFeedbackMsg({ type: "error", text: err.message || "Failed to load approvals list" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleExecuteDecision = async () => {
    if (!actionModal) return;
    const { approval, decision } = actionModal;
    setActionInProgress(approval.approval_id);

    try {
      if (decision === "APPROVED") {
        const result = await api.approveRequest(approval.approval_id, reviewerNotes);
        setFeedbackMsg({
          type: "success",
          text: result.execution_result?.document_id
            ? `${approval.action_type} executed. ${result.execution_result.document_type} ${result.execution_result.document_id} was recorded.`
            : `${approval.action_type} execution status: ${result.action_execution_status || "UNKNOWN"}.`,
        });
      } else {
        await api.rejectRequest(approval.approval_id, reviewerNotes);
        setFeedbackMsg({
          type: "success",
          text: `Action ${approval.action_type} rejected.`,
        });
      }
      setActionModal(null);
      setReviewerNotes("");
      await fetchApprovals();
    } catch (err: any) {
      setFeedbackMsg({ type: "error", text: err.message || "Failed to process approval request" });
    } finally {
      setActionInProgress(null);
    }
  };

  const togglePayloadExpand = (id: string) => {
    setExpandedPayloads((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Filtered dataset
  const filteredApprovals = approvals.filter((item) => {
    if (
      filterStatus !== "ALL" &&
      !(filterStatus === "APPROVED" && item.status === "MODIFIED") &&
      item.status !== filterStatus
    ) return false;
    if (filterDomain !== "ALL" && item.domain !== filterDomain) return false;
    if (filterRisk !== "ALL" && item.risk_level !== filterRisk) return false;
    return true;
  });

  const pendingCount = approvals.filter((a) => a.status === "PENDING").length;
  const approvedCount = approvals.filter((a) => a.action_execution_status === "SUCCEEDED").length;
  const rejectedCount = approvals.filter((a) => a.status === "REJECTED").length;
  const criticalCount = approvals.filter(
    (a) => a.status === "PENDING" && (a.risk_level === "CRITICAL" || a.risk_level === "HIGH")
  ).length;

  return (
    <div className="space-y-6 pb-16">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-cream-300 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cream-200 text-cream-900 border border-cream-300 shadow-2xs">
              <ShieldCheck className="w-5 h-5 text-cream-900" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-cream-900 font-serif">
                  Human-in-the-Loop Governance & Approvals
                </h1>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-cream-200 text-cream-800 border border-cream-300 font-medium">
                  Autonomous Workforce
                </span>
              </div>
              <p className="text-xs text-cream-700 mt-1">
                Review, modify, and authorize high-impact proposals generated by autonomous domain supervisors.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => fetchApprovals()}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium bg-cream-100 hover:bg-cream-200 text-cream-800 rounded-lg border border-cream-300 transition shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh Inbox
          </button>
        </div>
      </div>

      {/* KPI Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-cream-100 border border-cream-300 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-cream-700">Pending Review</span>
            <Clock className="w-4 h-4 text-amberGold-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-amberGold-700">{pendingCount}</div>
          <span className="text-[11px] text-cream-600">Awaiting executive sign-off</span>
        </div>

        <div className="bg-cream-100 border border-cream-300 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-cream-700">High / Critical Risk</span>
            <ShieldAlert className="w-4 h-4 text-terracotta-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-terracotta-700">{criticalCount}</div>
          <span className="text-[11px] text-cream-600">Requires multi-factor check</span>
        </div>

        <div className="bg-cream-100 border border-cream-300 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-cream-700">Approved & Executed</span>
            <CheckCircle2 className="w-4 h-4 text-sage-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-sage-700">{approvedCount}</div>
          <span className="text-[11px] text-cream-600">Committed to ledger / ERP</span>
        </div>

        <div className="bg-cream-100 border border-cream-300 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-cream-700">Rejected Actions</span>
            <XCircle className="w-4 h-4 text-cream-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-cream-800">{rejectedCount}</div>
          <span className="text-[11px] text-cream-600">Blocked by governance</span>
        </div>
      </div>

      {/* Notification Banner */}
      {feedbackMsg && (
        <div
          className={`flex items-center justify-between p-4 rounded-xl border text-sm shadow-2xs ${
            feedbackMsg.type === "success"
              ? "bg-sage-50 text-sage-800 border-sage-300"
              : "bg-terracotta-50 text-terracotta-800 border-terracotta-300"
          }`}
        >
          <div className="flex items-center gap-2">
            {feedbackMsg.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-sage-600" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-terracotta-600" />
            )}
            <span>{feedbackMsg.text}</span>
          </div>
          <button onClick={() => setFeedbackMsg(null)} className="text-xs opacity-75 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Filter and Tab Bar */}
      <div className="bg-cream-100 border border-cream-300 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-2xs">
        {/* Status Tabs */}
        <div className="flex items-center gap-1.5 bg-cream-50 p-1 rounded-lg border border-cream-300">
          {(["PENDING", "APPROVED", "REJECTED", "ALL"] as const).map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                filterStatus === st
                  ? "bg-cream-900 text-cream-50 shadow-xs"
                  : "text-cream-700 hover:text-cream-900 hover:bg-cream-200"
              }`}
            >
              {st === "ALL" ? "All History" : st.charAt(0) + st.slice(1).toLowerCase()}
              {st === "PENDING" && pendingCount > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 rounded-full bg-amberGold-100 text-amberGold-800 border border-amberGold-300 text-[10px]">
                  {pendingCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Domain & Risk Filters */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-cream-700 font-medium">Domain:</span>
            <select
              value={filterDomain}
              onChange={(e) => setFilterDomain(e.target.value)}
              className="bg-cream-50 border border-cream-300 text-cream-900 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cream-500 shadow-2xs"
            >
              <option value="ALL">All Domains</option>
              <option value="PROCUREMENT">Procurement</option>
              <option value="FINANCE">Finance</option>
              <option value="MANUFACTURING">MES / Quality</option>
              <option value="HR">HR & Workforce</option>
              <option value="INVENTORY">Inventory</option>
              <option value="SALES">Sales</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-cream-700 font-medium">Risk:</span>
            <select
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value)}
              className="bg-cream-50 border border-cream-300 text-cream-900 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cream-500 shadow-2xs"
            >
              <option value="ALL">All Risk Levels</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </div>
      </div>

      {/* Approvals List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-cream-600 bg-cream-100 border border-cream-300 rounded-xl">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-cream-700" />
            Loading pending approvals...
          </div>
        ) : filteredApprovals.length === 0 ? (
          <div className="p-12 text-center text-cream-700 bg-cream-100 border border-cream-300 rounded-xl shadow-2xs">
            <CheckCircle2 className="w-9 h-9 text-sage-600 mx-auto mb-2.5" />
            <h3 className="text-sm font-semibold text-cream-900">Inbox Clean</h3>
            <p className="text-xs text-cream-600 mt-1">
              No approval requests match the selected filters.
            </p>
          </div>
        ) : (
          filteredApprovals.map((item) => {
            const domainCfg = DOMAIN_CONFIG[item.domain] || {
              label: item.domain,
              color: "bg-cream-200 text-cream-800 border-cream-300",
              icon: FileText,
            };
            const riskCfg = RISK_BADGES[item.risk_level] || RISK_BADGES.LOW;
            const isPending = item.status === "PENDING";
            const isSupportedAction = EXECUTABLE_APPROVAL_ACTIONS.has(item.action_type);
            const DomainIcon = domainCfg.icon;
            const isExpanded = !!expandedPayloads[item.approval_id];

            return (
              <div
                key={item.approval_id}
                className={`bg-cream-100 border rounded-xl p-5 transition shadow-2xs ${
                  isPending
                    ? "border-cream-300 hover:border-cream-400"
                    : "border-cream-200 opacity-90"
                }`}
              >
                {/* Header row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cream-300 pb-3.5">
                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border ${domainCfg.color}`}
                    >
                      <DomainIcon className="w-3.5 h-3.5" />
                      {domainCfg.label}
                    </span>

                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wider border ${riskCfg.badge}`}
                    >
                      {riskCfg.label}
                    </span>

                    <h3 className="font-mono text-sm font-semibold text-cream-900">
                      {item.action_type}
                    </h3>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-cream-600 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-cream-200 text-cream-800 text-[11px] border border-cream-300">
                      Role: {item.required_role}
                    </span>
                  </div>
                </div>

                {/* AI Rationale Box */}
                <div className="my-4 p-3.5 rounded-lg bg-amberGold-50/70 border border-amberGold-200 text-cream-900">
                  <div className="flex items-center gap-2 text-xs font-semibold text-amberGold-900 mb-1.5">
                    <Sparkles className="w-4 h-4 text-amberGold-600" />
                    Agent Rationale ({item.agent_name}):
                  </div>
                  <p className="text-xs leading-relaxed text-cream-800">{item.ai_rationale}</p>
                </div>

                {/* Structured Payload Preview */}
                <div className="my-3 p-3 rounded-lg bg-cream-50 border border-cream-300/80 text-xs">
                  <div className="flex items-center justify-between text-cream-600 mb-2">
                    <span className="font-semibold uppercase tracking-wider text-[10px] text-cream-500">
                      Proposed Transaction Payload
                    </span>
                    <button
                      onClick={() => togglePayloadExpand(item.approval_id)}
                      className="text-xs text-cream-800 hover:text-cream-900 font-medium flex items-center gap-1"
                    >
                      {isExpanded ? "Collapse JSON" : "View Raw JSON"}
                      {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </button>
                  </div>

                  {/* Summary key-values */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                    {Object.entries(item.action_payload || {}).map(([k, v]) => {
                      if (typeof v === "object" && v !== null) {
                        return null;
                      }
                      return (
                        <div key={k} className="p-2 rounded bg-cream-100 border border-cream-200">
                          <span className="text-[10px] text-cream-500 uppercase block font-mono">{k}</span>
                          <span className="font-mono text-cream-900 text-xs truncate block font-semibold">{String(v)}</span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Raw JSON expandable */}
                  {isExpanded && (
                    <pre className="mt-3 p-3 rounded bg-cream-100 font-mono text-[11px] text-cream-900 overflow-x-auto border border-cream-300">
                      {JSON.stringify(item.action_payload, null, 2)}
                    </pre>
                  )}
                </div>

                {/* Footer Review status & Buttons */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-cream-300">
                  <div className="text-xs">
                    {item.status === "PENDING" ? (
                      <span className="inline-flex items-center gap-1.5 text-amberGold-800 font-medium">
                        <Clock className="w-3.5 h-3.5" />
                        Awaiting Manager Review
                      </span>
                    ) : item.status === "APPROVED" || item.status === "MODIFIED" ? (
                      <span className="inline-flex items-center gap-1.5 text-sage-800 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5 text-sage-600" />
                        {item.status === "MODIFIED" ? "Approved with changes" : "Approved"} · Execution {item.action_execution_status || "UNKNOWN"} {item.reviewed_at && `· ${new Date(item.reviewed_at).toLocaleDateString()}`}
                        {item.reviewer_notes && ` ("${item.reviewer_notes}")`}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-terracotta-800 font-medium">
                        <XCircle className="w-3.5 h-3.5 text-terracotta-600" />
                        Rejected {item.reviewer_notes && `("${item.reviewer_notes}")`}
                      </span>
                    )}
                  </div>

                  {item.action_execution_result?.document_id && (
                    <div className="mt-2 text-[11px] font-mono text-cream-700">
                      Result: {item.action_execution_result.document_type} · {item.action_execution_result.document_id}
                      {item.action_execution_result.previous_credit_limit !== undefined &&
                        ` · credit limit ${item.action_execution_result.previous_credit_limit} → ${item.action_execution_result.new_credit_limit}`}
                    </div>
                  )}

                  {isPending && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          setActionModal({ approval: item, decision: "REJECTED" });
                          setReviewerNotes("");
                        }}
                        disabled={actionInProgress === item.approval_id}
                        className="px-3 py-1.5 text-xs font-medium bg-terracotta-50 hover:bg-terracotta-100 text-terracotta-800 border border-terracotta-300 rounded-lg transition flex items-center gap-1.5"
                      >
                        <X className="w-3.5 h-3.5" />
                        Reject
                      </button>
                      <button
                        onClick={() => {
                          setActionModal({ approval: item, decision: "APPROVED" });
                          setReviewerNotes("Approved via Workforce Operations Console.");
                        }}
                        disabled={actionInProgress === item.approval_id || !isSupportedAction}
                        className="px-4 py-1.5 text-xs font-medium bg-cream-900 hover:bg-cream-800 text-cream-50 rounded-lg shadow-xs transition flex items-center gap-1.5"
                      >
                        <Check className="w-3.5 h-3.5" />
                        {isSupportedAction ? "Approve & Execute" : "Execution unavailable"}
                      </button>
                    </div>
                  )}
                  {isPending && !isSupportedAction && (
                    <p className="mt-2 text-[11px] text-terracotta-700">
                      This action type is not enabled for execution. You can reject it; approval is unavailable until a safe handler is implemented.
                    </p>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Reviewer Action Modal */}
      {actionModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-xl text-cream-900">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="text-base font-semibold text-cream-900 flex items-center gap-2">
                {actionModal.decision === "APPROVED" ? (
                  <>
                    <CheckCircle2 className="w-5 h-5 text-sage-600" />
                    Authorize Action Execution
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-terracotta-600" />
                    Reject Action Proposal
                  </>
                )}
              </h3>
              <button
                onClick={() => setActionModal(null)}
                className="text-cream-500 hover:text-cream-900"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="text-xs text-cream-800 space-y-2">
              <p>
                Action: <strong className="font-mono text-cream-900">{actionModal.approval.action_type}</strong>
              </p>
              <p>
                Agent: <strong className="text-cream-900">{actionModal.approval.agent_name}</strong>
              </p>
              <p className="text-cream-700 italic">"{actionModal.approval.ai_rationale}"</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream-700 mb-1.5">
                Reviewer Notes / Justification:
              </label>
              <textarea
                value={reviewerNotes}
                onChange={(e) => setReviewerNotes(e.target.value)}
                placeholder={
                  actionModal.decision === "APPROVED"
                    ? "Enter sign-off comments..."
                    : "Specify reason for rejection..."
                }
                rows={3}
                className="w-full bg-cream-100 border border-cream-300 rounded-lg p-2.5 text-xs text-cream-900 focus:outline-none focus:border-cream-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-cream-300">
              <button
                onClick={() => setActionModal(null)}
                className="px-3.5 py-1.5 text-xs text-cream-700 hover:text-cream-900"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteDecision}
                disabled={actionInProgress === actionModal.approval.approval_id}
                className={`px-4 py-1.5 text-xs font-medium text-cream-50 rounded-lg flex items-center gap-1.5 transition ${
                  actionModal.decision === "APPROVED"
                    ? "bg-cream-900 hover:bg-cream-800"
                    : "bg-terracotta-700 hover:bg-terracotta-600"
                }`}
              >
                {actionInProgress === actionModal.approval.approval_id ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Check className="w-3.5 h-3.5" />
                )}
                Confirm {actionModal.decision === "APPROVED" ? "Approval" : "Rejection"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
