"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

interface WorkflowNode {
  task_id: string;
  name: string;
  agent_id: string;
  status: string;
  error_message?: string | null;
  result?: Record<string, unknown>;
}

interface WorkflowRun {
  dag_id: string;
  status: string;
  updated_at: string;
  recovery_reason?: string | null;
  recovery_notes?: string | null;
  nodes: WorkflowNode[];
}

export default function WorkflowRunsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowRun | null>(null);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [recovering, setRecovering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadWorkflows = useCallback(async (workflowId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listWorkflows();
      if (!Array.isArray(result)) {
        throw new Error("Workflow history returned an unexpected response.");
      }
      setWorkflows(result);
      const selected = workflowId
        ? await api.getWorkflow(workflowId)
        : result[0] ?? null;
      setSelectedWorkflow(selected);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load workflow history.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const workflowId = new URLSearchParams(window.location.search).get("dag_id") ?? undefined;
    void loadWorkflows(workflowId);
  }, [loadWorkflows]);

  const selectWorkflow = async (workflowId: string) => {
    setError(null);
    try {
      const workflow = await api.getWorkflow(workflowId);
      setSelectedWorkflow(workflow);
      router.replace(`/workflows?dag_id=${encodeURIComponent(workflowId)}`);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load this workflow.");
    }
  };

  const recoverWorkflow = async () => {
    if (!selectedWorkflow || notes.trim().length < 10) return;
    setRecovering(true);
    setError(null);
    try {
      await api.recoverWorkflow(selectedWorkflow.dag_id, notes.trim());
      setNotes("");
      await loadWorkflows(selectedWorkflow.dag_id);
    } catch (recoveryError) {
      setError(recoveryError instanceof Error ? recoveryError.message : "Workflow recovery failed.");
    } finally {
      setRecovering(false);
    }
  };

  return (
    <main className="space-y-6 pb-12">
      <header className="flex items-center justify-between border-b border-cream-300 pb-4">
        <div>
          <h1 className="text-2xl font-semibold text-cream-900">Workflow Runs</h1>
          <p className="mt-1 text-sm text-cream-700">
            Inspect tenant workflows and review interrupted execution state.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadWorkflows(selectedWorkflow?.dag_id)}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md border border-cream-300 bg-cream-100 px-3 py-2 text-sm text-cream-800 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </header>

      {error && (
        <p role="alert" className="rounded-md border border-terracotta-300 bg-terracotta-50 p-3 text-sm text-terracotta-800">
          {error}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_2fr]">
        <section className="rounded-lg border border-cream-300 bg-cream-100 p-4">
          <h2 className="mb-3 text-sm font-semibold text-cream-900">Recent workflows</h2>
          {loading ? (
            <p className="text-sm text-cream-700">Loading workflows…</p>
          ) : workflows.length === 0 ? (
            <p className="text-sm text-cream-700">No workflows have been recorded.</p>
          ) : (
            <ul className="space-y-2">
              {workflows.map((workflow) => (
                <li key={workflow.dag_id}>
                  <button
                    type="button"
                    onClick={() => void selectWorkflow(workflow.dag_id)}
                    className={`w-full rounded-md border p-3 text-left ${
                      selectedWorkflow?.dag_id === workflow.dag_id
                        ? "border-cream-700 bg-cream-200"
                        : "border-cream-300 bg-cream-50 hover:bg-cream-200"
                    }`}
                  >
                    <span className="block truncate font-mono text-xs text-cream-900">
                      {workflow.dag_id}
                    </span>
                    <span className="mt-1 block text-xs text-cream-700">
                      {workflow.status} · {new Date(workflow.updated_at).toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-4 rounded-lg border border-cream-300 bg-cream-100 p-4">
          {!selectedWorkflow ? (
            <p className="text-sm text-cream-700">Select a workflow to inspect its tasks.</p>
          ) : (
            <>
              <div>
                <h2 className="font-mono text-sm font-semibold text-cream-900">
                  {selectedWorkflow.dag_id}
                </h2>
                <p className="mt-1 text-sm text-cream-700">Status: {selectedWorkflow.status}</p>
                {selectedWorkflow.recovery_reason && (
                  <p className="mt-2 text-sm text-amberGold-800">
                    {selectedWorkflow.recovery_reason}
                  </p>
                )}
              </div>

              <ol className="space-y-2">
                {selectedWorkflow.nodes.map((node) => (
                  <li key={node.task_id} className="rounded-md border border-cream-300 bg-cream-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-medium text-cream-900">{node.name}</span>
                      <span className="font-mono text-xs text-cream-700">{node.status}</span>
                    </div>
                    <p className="mt-1 text-xs text-cream-600">{node.agent_id}</p>
                    {node.error_message && (
                      <p className="mt-2 text-xs text-terracotta-800">{node.error_message}</p>
                    )}
                  </li>
                ))}
              </ol>

              {selectedWorkflow.status === "RECOVERY_REQUIRED" && (
                <div className="space-y-2 border-t border-cream-300 pt-4">
                  <label htmlFor="workflow-recovery-notes" className="block text-sm font-medium text-cream-900">
                    Finance recovery note (at least 10 characters)
                  </label>
                  <textarea
                    id="workflow-recovery-notes"
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    minLength={10}
                    maxLength={500}
                    rows={3}
                    className="w-full rounded-md border border-cream-300 bg-cream-50 p-2 text-sm text-cream-900"
                  />
                  <button
                    type="button"
                    onClick={() => void recoverWorkflow()}
                    disabled={recovering || notes.trim().length < 10}
                    className="rounded-md bg-cream-900 px-3 py-2 text-sm font-medium text-cream-50 disabled:opacity-50"
                  >
                    {recovering ? "Recovering…" : "Request recovery"}
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
