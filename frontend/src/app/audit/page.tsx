"use client";

import { useEffect, useState } from "react";
import {
  AlertOctagon,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Fingerprint,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  Clock,
  Key,
} from "lucide-react";
import { api } from "@/lib/api";

interface AuditBlockVerification {
  block_index: number;
  log_id: string;
  agent_id: string;
  trace_id: string;
  previous_hash: string;
  record_hash: string;
  is_valid: boolean;
  tamper_reason?: string | null;
}

interface SOC2Report {
  audit_id: string;
  evaluated_at: string;
  total_blocks_verified: number;
  is_chain_unbroken: boolean;
  tampered_blocks_count: number;
  compliance_certification: string;
  merkle_root_hash: string;
  verified_blocks: AuditBlockVerification[];
}

interface MeshExecutionSummary {
  execution_id: string;
  event_type: string;
  initiating_agent: string;
  participating_agents: string[];
  tasks_dispatched: number;
  tasks_completed: number;
  is_conflict_arbitrated: boolean;
  is_compliance_verified: boolean;
  status: string;
  output_summary: {
    customer_name: string;
    sku: string;
    quantity: number;
    makespan_minutes: number;
    quoted_unit_price: number;
    guaranteed_margin: number;
    compliance_token: string;
  };
}

export default function AuditSOC2Page() {
  const [report, setReport] = useState<SOC2Report | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTamperTesting, setIsTamperTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tamperModeActive, setTamperModeActive] = useState(false);

  // Mesh RFQ Execution State
  const [isExecutingMesh, setIsExecutingMesh] = useState(false);
  const [meshCustomer, setMeshCustomer] = useState("Tesla Energy Inc.");
  const [meshSku, setMeshSku] = useState("SOLAR-INV-50KW");
  const [meshQty, setMeshQty] = useState(250);
  const [meshDeadlineDays, setMeshDeadlineDays] = useState(14);
  const [meshSummary, setMeshSummary] = useState<MeshExecutionSummary | null>(null);

  // Load Real SOC 2 Report from Database
  const loadReport = async () => {
    try {
      setIsLoading(true);
      setError(null);
      setTamperModeActive(false);
      const data = await api.getSOC2Report();
      setReport(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load live SOC 2 audit report");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
  }, []);

  // Run Real Tamper Detection Test against Backend Engine
  const handleTamperTest = async () => {
    try {
      setIsTamperTesting(true);
      setError(null);
      const tamperedReport = await api.runTamperTest({
        tamper_block_index: 0,
        tampered_payload_key: "unauthorized_override",
        tampered_payload_value: "malicious_price_manipulation_attempt",
      });
      setReport(tamperedReport);
      setTamperModeActive(true);
    } catch (err: any) {
      alert("Tamper test error: " + (err?.message || err));
    } finally {
      setIsTamperTesting(false);
    }
  };

  // Run End-to-End 7-Agent Mesh Pipeline
  const handleRunMeshPipeline = async () => {
    try {
      setIsExecutingMesh(true);
      setError(null);
      const res = await api.executeMeshRFQ({
        customer_name: meshCustomer,
        target_sku: meshSku,
        quantity: Number(meshQty),
        delivery_deadline_days: Number(meshDeadlineDays),
      });
      setMeshSummary(res);
      // Refresh audit report to immediately reveal the appended block
      await loadReport();
    } catch (err: any) {
      alert("Agent Mesh execution failed: " + (err?.message || err));
    } finally {
      setIsExecutingMesh(false);
    }
  };

  const isChainValid = report?.is_chain_unbroken ?? true;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900 flex items-center gap-2">
            <span>SOC 2 Type II Compliance &bull; Cryptographic Audit Chain &amp; Agent Mesh</span>
            <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[11px] font-mono font-medium text-cream-800">
              Live DB
            </span>
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Genesis-to-tip SHA-256 hash continuity verification with autonomous multi-agent OpenTelemetry context propagation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={loadReport}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>{isLoading ? "Verifying..." : "Verify Live Chain"}</span>
          </button>
          <button
            onClick={handleTamperTest}
            disabled={isTamperTesting || isLoading}
            className="flex items-center gap-1.5 rounded-md border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-800 hover:bg-rose-100 disabled:opacity-50"
          >
            <AlertOctagon className="h-3.5 w-3.5 text-rose-600" />
            <span>{isTamperTesting ? "Simulating..." : "Run Tamper Detection Test"}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadReport} className="underline font-semibold">Retry</button>
        </div>
      )}

      {/* Audit Chain Compliance Banner */}
      <div
        className={`rounded-lg border p-4 text-xs flex flex-col md:flex-row md:items-center md:justify-between gap-4 transition-colors ${
          isChainValid
            ? "border-sage-500/30 bg-sage-50 text-sage-900"
            : "border-rose-500/30 bg-rose-50/90 text-rose-900"
        }`}
      >
        <div className="flex items-center gap-3">
          {isChainValid ? (
            <ShieldCheck className="h-7 w-7 text-sage-600 flex-shrink-0" />
          ) : (
            <ShieldAlert className="h-7 w-7 text-rose-600 flex-shrink-0" />
          )}
          <div>
            <div className="font-semibold text-sm flex items-center gap-2">
              <span>
                {isChainValid
                  ? "SOC 2 Type II Status: CERTIFIED_COMPLIANT"
                  : "Security Alert: NON_COMPLIANT_TAMPER_DETECTED"}
              </span>
              {tamperModeActive && (
                <span className="rounded bg-rose-200 border border-rose-400 px-1.5 py-0.2 text-[10px] font-mono text-rose-900 uppercase">
                  Tamper Test Active
                </span>
              )}
            </div>
            <div className="text-[11px] font-mono mt-0.5 opacity-90">
              {isChainValid
                ? `All ${report?.total_blocks_verified || 0} sequential blocks cryptographically verified. SHA-256 hash continuity unbroken. Zero mutations detected.`
                : `Deliberate record mutation detected at Block #0! Recomputed SHA-256 diverges from stored record hash. Cryptographic seal broken.`}
            </div>
          </div>
        </div>

        <div className="font-mono text-[11px] space-y-0.5 md:text-right border-t md:border-t-0 pt-2 md:pt-0 border-cream-300">
          <div>Verified Blocks: {report?.total_blocks_verified || 0} / {report?.total_blocks_verified || 0}</div>
          <div className="truncate max-w-[280px]">
            Merkle Root: {report?.merkle_root_hash ? `${report.merkle_root_hash.slice(0, 16)}...` : "—"}
          </div>
          {report?.evaluated_at && (
            <div className="text-[10px] text-cream-600">
              Evaluated: {new Date(report.evaluated_at).toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>

      {/* Visual Block Chain Explorer */}
      <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-cream-200 pb-3">
          <div className="flex items-center gap-2">
            <Fingerprint className="h-4 w-4 text-cream-800" />
            <h2 className="text-sm font-semibold text-cream-900">
              Genesis-to-Tip Cryptographic Audit Chain ({report?.verified_blocks.length || 0} Blocks)
            </h2>
          </div>
          <span className="text-[11px] font-mono text-cream-600">
            Hash = SHA-256(prev_hash : trace_id : agent : canonical_payload)
          </span>
        </div>

        {isLoading && !report ? (
          <div className="py-8 text-center text-xs text-cream-600 font-mono">
            Verifying cryptographic lineage from PostgreSQL...
          </div>
        ) : !report?.verified_blocks || report.verified_blocks.length === 0 ? (
          <div className="py-8 text-center text-xs text-cream-500 italic">
            No audit records found. Run the Agent Mesh pipeline below or register an organization to provision the genesis block.
          </div>
        ) : (
          <div className="space-y-3">
            {report.verified_blocks.map((block) => (
              <div
                key={block.log_id || block.block_index}
                className={`rounded-lg border p-3.5 text-xs transition-colors ${
                  block.is_valid
                    ? "border-cream-300 bg-cream-100/70"
                    : "border-rose-400 bg-rose-50/90 shadow-sm"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between pb-2 border-b border-cream-200/60 font-mono text-[11px] gap-2">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-cream-200 px-1.5 py-0.5 font-bold text-cream-900">
                      Block #{block.block_index}
                    </span>
                    <span className="font-semibold text-cream-800">{block.agent_id}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-cream-500 truncate max-w-[180px]">{block.trace_id}</span>
                    {block.is_valid ? (
                      <span className="inline-flex items-center gap-1 text-sage-700 font-semibold">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Valid Seal
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-rose-700 font-semibold">
                        <XCircle className="h-3.5 w-3.5" /> Tampered Record
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2.5 font-mono text-[10.5px]">
                  <div className="text-cream-600 truncate">
                    <span className="text-cream-500 uppercase tracking-wider block text-[9.5px]">
                      Parent Hash Pointer:
                    </span>
                    {block.previous_hash}
                  </div>
                  <div className="text-cream-900 font-semibold truncate">
                    <span className="text-cream-500 uppercase tracking-wider block text-[9.5px]">
                      Record Hash (SHA-256):
                    </span>
                    {block.record_hash}
                  </div>
                </div>

                {block.tamper_reason && (
                  <div className="mt-2.5 rounded border border-rose-300 bg-white/90 p-2 font-mono text-[10.5px] text-rose-800">
                    <strong>TAMPER DETECTED:</strong> {block.tamper_reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Autonomous 7-Agent Mesh Coordination Pipeline */}
      <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-5">
        <div className="flex items-center justify-between border-b border-cream-200 pb-3">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-cream-800" />
            <h2 className="text-sm font-semibold text-cream-900">
              Autonomous 7-Agent Mesh &bull; Inbound RFQ Pipeline Execution
            </h2>
          </div>
          <span className="text-[11px] font-mono text-cream-600">
            PRD &sect;Autonomous Agent Mesh
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div>
            <label className="text-cream-600 text-[11px] block font-medium">Customer Organization</label>
            <input
              type="text"
              value={meshCustomer}
              onChange={(e) => setMeshCustomer(e.target.value)}
              className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1.5 text-cream-900"
            />
          </div>
          <div>
            <label className="text-cream-600 text-[11px] block font-medium">Target SKU Code</label>
            <input
              type="text"
              value={meshSku}
              onChange={(e) => setMeshSku(e.target.value)}
              className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1.5 font-mono text-cream-900"
            />
          </div>
          <div>
            <label className="text-cream-600 text-[11px] block font-medium">Order Quantity (Units)</label>
            <input
              type="number"
              value={meshQty}
              onChange={(e) => setMeshQty(parseInt(e.target.value) || 1)}
              className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1.5 font-mono text-cream-900"
            />
          </div>
          <div>
            <label className="text-cream-600 text-[11px] block font-medium">Action Trigger</label>
            <button
              onClick={handleRunMeshPipeline}
              disabled={isExecutingMesh}
              className="w-full mt-1 flex items-center justify-center gap-1.5 rounded bg-cream-900 text-cream-50 px-3 py-1.5 font-medium hover:bg-cream-800 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              <span>{isExecutingMesh ? "Running Mesh..." : "Execute 7-Agent Mesh"}</span>
            </button>
          </div>
        </div>

        {/* 7-Agent Mesh Execution Trace Card */}
        {meshSummary && (
          <div className="rounded-lg border border-sage-500/30 bg-sage-50 p-4 text-xs space-y-3">
            <div className="flex items-center justify-between font-semibold">
              <div className="flex items-center gap-2 text-sage-900">
                <CheckCircle2 className="h-4 w-4 text-sage-600" />
                <span>Multi-Agent Workflow Arbitrated: {meshSummary.event_type}</span>
              </div>
              <span className="font-mono text-[10px] bg-sage-200 text-sage-800 px-2 py-0.5 rounded">
                {meshSummary.execution_id}
              </span>
            </div>

            {/* Participating Agents Badges */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-cream-600 text-[11px]">Active Mesh Subagents:</span>
              {meshSummary.participating_agents.map((agent: string) => (
                <span
                  key={agent}
                  className="rounded border border-sage-300 bg-white px-2 py-0.5 font-mono text-[10px] text-sage-900"
                >
                  {agent}
                </span>
              ))}
            </div>

            {/* Mesh Results Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2 border-t border-sage-200 text-center font-mono text-xs">
              <div className="rounded bg-white p-2 border border-sage-200">
                <span className="text-[10px] text-cream-600 block uppercase font-sans">CP-SAT Makespan</span>
                <span className="font-semibold text-cream-900">
                  {meshSummary.output_summary.makespan_minutes} mins
                </span>
              </div>
              <div className="rounded bg-white p-2 border border-sage-200">
                <span className="text-[10px] text-cream-600 block uppercase font-sans">Margin Defended Price</span>
                <span className="font-semibold text-cream-900">
                  ${Number(meshSummary.output_summary.quoted_unit_price).toFixed(2)}
                </span>
              </div>
              <div className="rounded bg-white p-2 border border-sage-200">
                <span className="text-[10px] text-cream-600 block uppercase font-sans">Guaranteed Margin</span>
                <span className="font-semibold text-sage-700">
                  {Number(meshSummary.output_summary.guaranteed_margin).toFixed(1)}% (&ge; 22%)
                </span>
              </div>
              <div className="rounded bg-white p-2 border border-sage-200">
                <span className="text-[10px] text-cream-600 block uppercase font-sans">Compliance Token</span>
                <span className="font-semibold text-cream-700 text-[10.5px]">
                  {meshSummary.output_summary.compliance_token.slice(0, 14)}...
                </span>
              </div>
            </div>

            <p className="text-[10.5px] text-sage-800 italic pt-1">
              &bull; Cryptographic block automatically signed and committed to the tenant&apos;s immutable audit trail in PostgreSQL.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
