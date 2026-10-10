"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Database, FileUp, Globe, MessageCircle, RefreshCw, Send, Smartphone, Trash2, Wifi, WifiOff } from "lucide-react";
import { api } from "@/lib/api";
import { getUser } from "@/lib/auth";

type ConnectionStatus = {
  status: string;
  qr?: string | null;
  phone_number?: string | null;
};

type Conversation = {
  conversation_id: string;
  phone_number: string;
  contact_name: string | null;
  status: string;
  issue_id: string | null;
  last_message_at: string | null;
};

type Message = {
  message_id: string;
  direction: "INBOUND" | "OUTBOUND";
  content: string;
  delivery_status: string;
  created_at: string;
};

type ToolBinding = { name: string; description: string; enabled: boolean };
type KnowledgeEntry = { knowledge_id: string; title: string; content: string };
type KnowledgeSource = {
  source_id: string;
  source_type: "FILE" | "WEB" | "AIRTABLE";
  name: string;
  status: string;
  source_url: string | null;
  airtable_base_id: string | null;
  airtable_table_id: string | null;
  airtable_table_name: string | null;
  airtable_fields: string[] | null;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
};
type AirtableBase = { id: string; name: string };
type AirtableTable = { id: string; name: string; fields: string[] };

export default function WhatsAppSupportPage() {
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [issue, setIssue] = useState<{ issue_number: string; status: string } | null>(null);
  const [tools, setTools] = useState<ToolBinding[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeEntry[]>([]);
  const [knowledgeSources, setKnowledgeSources] = useState<KnowledgeSource[]>([]);
  const [knowledgeFile, setKnowledgeFile] = useState<File | null>(null);
  const [knowledgeUrl, setKnowledgeUrl] = useState("");
  const [airtableConnected, setAirtableConnected] = useState(false);
  const [airtableBases, setAirtableBases] = useState<AirtableBase[]>([]);
  const [airtableTables, setAirtableTables] = useState<AirtableTable[]>([]);
  const [selectedAirtableBase, setSelectedAirtableBase] = useState("");
  const [selectedAirtableTable, setSelectedAirtableTable] = useState("");
  const [selectedAirtableFields, setSelectedAirtableFields] = useState<string[]>([]);
  const [knowledgeTitle, setKnowledgeTitle] = useState("");
  const [knowledgeContent, setKnowledgeContent] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [isTenantAdmin, setIsTenantAdmin] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [connection, conversationData, toolData, knowledgeData, sourceData, airtableData] = await Promise.all([
        api.getWhatsAppStatus(),
        api.getWhatsAppConversations(),
        api.getWhatsAppTools(),
        api.getWhatsAppKnowledge(),
        api.getWhatsAppKnowledgeSources(),
        api.getWhatsAppAirtableStatus(),
      ]);
      setStatus(connection);
      setConversations(conversationData.conversations || []);
      setTools(toolData.tools || []);
      setKnowledge(knowledgeData.entries || []);
      setKnowledgeSources(sourceData.sources || []);
      setAirtableConnected(Boolean(airtableData.connected));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load WhatsApp support.");
    }
  }, []);

  useEffect(() => {
    setIsTenantAdmin(getUser()?.role === "TENANT_ADMIN");
    void refresh();
    const timer = window.setInterval(() => void refresh(), 7000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    const result = new URLSearchParams(window.location.search).get("airtable");
    if (!result) return;
    setError(result === "connected" ? "" : "Airtable authorization did not complete. Check its OAuth configuration and try again.");
    window.history.replaceState({}, "", window.location.pathname);
    if (result === "connected") void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      setIssue(null);
      return;
    }
    let active = true;
    const load = async () => {
      try {
        const detail = await api.getWhatsAppConversation(selectedId);
        if (active) {
          setMessages(detail.messages || []);
          setIssue(detail.issue || null);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Could not load conversation.");
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [selectedId]);

  const runConnectionAction = async (action: "connect" | "disconnect") => {
    setBusy(true);
    setError("");
    try {
      if (action === "connect") await api.connectWhatsApp();
      else await api.disconnectWhatsApp();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "WhatsApp action failed.");
    } finally {
      setBusy(false);
    }
  };

  const sendReply = async () => {
    if (!selectedId || !reply.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.replyToWhatsAppConversation(selectedId, reply.trim());
      setReply("");
      const detail = await api.getWhatsAppConversation(selectedId);
      setMessages(detail.messages || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reply.");
    } finally {
      setBusy(false);
    }
  };

  const toggleTool = async (tool: ToolBinding) => {
    const next = tools.map((item) => item.name === tool.name ? { ...item, enabled: !item.enabled } : item);
    setTools(next);
    try {
      await api.updateWhatsAppTools(next.filter((item) => item.enabled).map((item) => item.name));
    } catch (err) {
      setTools(tools);
      setError(err instanceof Error ? err.message : "Could not update the tool allowlist.");
    }
  };

  const saveKnowledge = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.createWhatsAppKnowledge(knowledgeTitle.trim(), knowledgeContent.trim());
      setKnowledgeTitle("");
      setKnowledgeContent("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save support knowledge.");
    } finally {
      setBusy(false);
    }
  };

  const removeKnowledge = async (knowledgeId: string) => {
    setError("");
    try {
      await api.deleteWhatsAppKnowledge(knowledgeId);
      setKnowledge((entries) => entries.filter((entry) => entry.knowledge_id !== knowledgeId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete support knowledge.");
    }
  };

  const uploadKnowledgeFile = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!knowledgeFile) return;
    setBusy(true);
    setError("");
    try {
      await api.uploadWhatsAppKnowledgeFile(knowledgeFile);
      setKnowledgeFile(null);
      const input = document.getElementById("whatsapp-knowledge-file") as HTMLInputElement | null;
      if (input) input.value = "";
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import the selected file.");
    } finally {
      setBusy(false);
    }
  };

  const importKnowledgeLink = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.importWhatsAppKnowledgeLink(knowledgeUrl.trim());
      setKnowledgeUrl("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not crawl this link.");
    } finally {
      setBusy(false);
    }
  };

  const connectAirtable = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api.getWhatsAppAirtableConnectUrl();
      window.location.assign(result.authorization_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start Airtable authorization.");
      setBusy(false);
    }
  };

  const disconnectAirtable = async () => {
    setBusy(true);
    setError("");
    try {
      await api.disconnectWhatsAppAirtable();
      setAirtableConnected(false);
      setAirtableBases([]);
      setAirtableTables([]);
      setSelectedAirtableBase("");
      setSelectedAirtableTable("");
      setSelectedAirtableFields([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect Airtable.");
    } finally {
      setBusy(false);
    }
  };

  const loadAirtableBases = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api.getWhatsAppAirtableBases();
      setAirtableBases(result.bases || []);
      setAirtableTables([]);
      setSelectedAirtableBase("");
      setSelectedAirtableTable("");
      setSelectedAirtableFields([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load Airtable bases.");
    } finally {
      setBusy(false);
    }
  };

  const chooseAirtableBase = async (baseId: string) => {
    setSelectedAirtableBase(baseId);
    setSelectedAirtableTable("");
    setSelectedAirtableFields([]);
    if (!baseId) {
      setAirtableTables([]);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api.getWhatsAppAirtableTables(baseId);
      setAirtableTables(result.tables || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load Airtable tables.");
    } finally {
      setBusy(false);
    }
  };

  const importAirtableTable = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedAirtableBase || !selectedAirtableTable || !selectedAirtableFields.length) return;
    setBusy(true);
    setError("");
    try {
      await api.importWhatsAppAirtableTable({
        base_id: selectedAirtableBase,
        table_id: selectedAirtableTable,
        fields: selectedAirtableFields,
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import the Airtable table.");
    } finally {
      setBusy(false);
    }
  };

  const syncKnowledgeSource = async (sourceId: string) => {
    setBusy(true);
    setError("");
    try {
      await api.syncWhatsAppAirtableSource(sourceId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sync the Airtable table.");
    } finally {
      setBusy(false);
    }
  };

  const removeKnowledgeSource = async (sourceId: string) => {
    setError("");
    try {
      await api.deleteWhatsAppKnowledgeSource(sourceId);
      setKnowledgeSources((items) => items.filter((item) => item.source_id !== sourceId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove the knowledge source.");
    }
  };

  const connected = status?.status === "CONNECTED";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-cream-600">Customer support channel</p>
          <h1 className="mt-1 text-3xl font-bold text-cream-950">WhatsApp Support</h1>
          <p className="mt-2 max-w-2xl text-sm text-cream-700">
            Manage the Baileys connection, review customer conversations, and configure the tenant support agent tools.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="inline-flex items-center gap-2 rounded-lg border border-cream-300 px-3 py-2 text-sm font-medium hover:bg-cream-100"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </header>

      {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
        <div className="rounded-xl border border-cream-300 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-green-100 p-2 text-green-800"><MessageCircle className="h-5 w-5" /></div>
              <div>
                <h2 className="font-semibold text-cream-950">Connection</h2>
                <p className="text-sm text-cream-700">{status?.status || "Loading status..."}</p>
              </div>
            </div>
            <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${connected ? "bg-green-100 text-green-800" : "bg-cream-200 text-cream-800"}`}>
              {connected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {connected ? "Connected" : "Not connected"}
            </span>
          </div>
          {status?.phone_number && <p className="mt-4 text-sm text-cream-700">Linked number: <strong>{status.phone_number}</strong></p>}
          {status?.qr && (
            <div className="mt-5 flex flex-col items-center rounded-lg bg-cream-50 p-4">
              <img src={status.qr} alt="WhatsApp pairing QR code" className="h-64 w-64" />
              <p className="mt-2 text-center text-sm text-cream-700">Scan with WhatsApp on the phone you want to link.</p>
            </div>
          )}
          <div className="mt-5 flex gap-2">
            <button
              type="button"
              disabled={busy || connected || !isTenantAdmin}
              onClick={() => void runConnectionAction("connect")}
              className="inline-flex items-center gap-2 rounded-lg bg-cream-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              <Smartphone className="h-4 w-4" /> Pair WhatsApp
            </button>
            <button
              type="button"
              disabled={busy || !connected || !isTenantAdmin}
              onClick={() => void runConnectionAction("disconnect")}
              className="rounded-lg border border-cream-300 px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              Disconnect
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-cream-300 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-cream-950">Agent tools</h2>
          <p className="mt-1 text-sm text-cream-700">Only enabled actions are available to the support agent.</p>
          <div className="mt-4 max-h-72 space-y-3 overflow-auto">
            {tools.map((tool) => (
              <label key={tool.name} className="flex cursor-pointer items-start gap-3 rounded-lg border border-cream-200 p-3">
                <input
                  type="checkbox"
                  checked={tool.enabled}
                  onChange={() => void toggleTool(tool)}
                  disabled={!isTenantAdmin}
                  className="mt-1 accent-cream-900"
                />
                <span>
                  <span className="block text-sm font-semibold text-cream-900">{tool.name.replaceAll("_", " ")}</span>
                  <span className="mt-1 block text-xs text-cream-700">{tool.description}</span>
                </span>
              </label>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-cream-300 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-cream-700" />
          <h2 className="font-semibold text-cream-950">Approved support knowledge</h2>
        </div>
        <p className="mt-1 text-sm text-cream-700">
          Add tenant-reviewed FAQs, service details, policies, and troubleshooting steps. The agent searches these entries before answering tenant-specific questions.
        </p>
        <form className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_2fr_auto]" onSubmit={(event) => void saveKnowledge(event)}>
          <input
            value={knowledgeTitle}
            onChange={(event) => setKnowledgeTitle(event.target.value)}
            required
            minLength={2}
            maxLength={255}
            placeholder="Entry title"
            className="rounded-lg border border-cream-300 px-3 py-2 text-sm outline-none focus:border-cream-700"
            disabled={!isTenantAdmin}
          />
          <textarea
            value={knowledgeContent}
            onChange={(event) => setKnowledgeContent(event.target.value)}
            required
            minLength={10}
            maxLength={20000}
            rows={2}
            placeholder="Approved answer or troubleshooting guidance"
            className="rounded-lg border border-cream-300 px-3 py-2 text-sm outline-none focus:border-cream-700"
            disabled={!isTenantAdmin}
          />
          <button disabled={!isTenantAdmin || busy || !knowledgeTitle.trim() || !knowledgeContent.trim()} className="rounded-lg bg-cream-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            Add entry
          </button>
        </form>
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          {knowledge.map((entry) => (
            <div key={entry.knowledge_id} className="flex items-start justify-between gap-3 rounded-lg border border-cream-200 p-3">
              <div className="min-w-0">
                <p className="font-semibold text-cream-950">{entry.title}</p>
                <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-sm text-cream-700">{entry.content}</p>
              </div>
              {isTenantAdmin && <button type="button" onClick={() => void removeKnowledge(entry.knowledge_id)} aria-label={`Delete ${entry.title}`} className="rounded p-1 text-cream-600 hover:bg-red-50 hover:text-red-700">
                <Trash2 className="h-4 w-4" />
              </button>}
            </div>
          ))}
          {!knowledge.length && <p className="text-sm text-cream-700">No approved support knowledge has been added yet.</p>}
        </div>

        <div className="mt-6 grid gap-5 border-t border-cream-200 pt-5 lg:grid-cols-2">
          <form onSubmit={(event) => void uploadKnowledgeFile(event)} className="space-y-3 rounded-lg border border-cream-200 p-4">
            <div className="flex items-center gap-2 font-semibold text-cream-950"><FileUp className="h-4 w-4" /> Import a document</div>
            <p className="text-xs text-cream-700">PDF, DOCX, XLSX, or XLS; up to 20 MB. Files are extracted to text; the uploaded binary is not retained.</p>
            <input
              id="whatsapp-knowledge-file"
              type="file"
              accept=".pdf,.docx,.xlsx,.xls,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
              onChange={(event) => setKnowledgeFile(event.target.files?.[0] || null)}
              disabled={!isTenantAdmin || busy}
              className="block w-full text-sm"
            />
            <button disabled={!isTenantAdmin || busy || !knowledgeFile} className="rounded-lg bg-cream-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Import file</button>
          </form>

          <form onSubmit={(event) => void importKnowledgeLink(event)} className="space-y-3 rounded-lg border border-cream-200 p-4">
            <div className="flex items-center gap-2 font-semibold text-cream-950"><Globe className="h-4 w-4" /> Import a web page</div>
            <p className="text-xs text-cream-700">Crawl one public HTTP(S) page with Crawl4AI. Internal and private-network addresses are blocked.</p>
            <input
              type="url"
              value={knowledgeUrl}
              onChange={(event) => setKnowledgeUrl(event.target.value)}
              maxLength={2048}
              required
              placeholder="https://example.com/support"
              disabled={!isTenantAdmin || busy}
              className="w-full rounded-lg border border-cream-300 px-3 py-2 text-sm"
            />
            <button disabled={!isTenantAdmin || busy || !knowledgeUrl.trim()} className="rounded-lg bg-cream-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Crawl link</button>
          </form>
        </div>

        <div className="mt-5 rounded-lg border border-cream-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 font-semibold text-cream-950"><Database className="h-4 w-4" /> Airtable knowledge import</div>
              <p className="mt-1 text-xs text-cream-700">Authorize read-only access, then choose a base, table, and specific fields to import.</p>
            </div>
            {!airtableConnected ? (
              <button type="button" disabled={!isTenantAdmin || busy} onClick={() => void connectAirtable()} className="rounded-lg bg-cream-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Connect Airtable</button>
            ) : (
              <div className="flex gap-2">
                <button type="button" disabled={!isTenantAdmin || busy} onClick={() => void loadAirtableBases()} className="rounded-lg border border-cream-300 px-3 py-2 text-sm font-semibold disabled:opacity-50">Choose table</button>
                <button type="button" disabled={!isTenantAdmin || busy} onClick={() => void disconnectAirtable()} className="rounded-lg border border-cream-300 px-3 py-2 text-sm font-semibold disabled:opacity-50">Disconnect</button>
              </div>
            )}
          </div>
          {airtableConnected && airtableBases.length > 0 && (
            <form onSubmit={(event) => void importAirtableTable(event)} className="mt-4 space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                <select value={selectedAirtableBase} onChange={(event) => void chooseAirtableBase(event.target.value)} disabled={busy} className="rounded-lg border border-cream-300 px-3 py-2 text-sm">
                  <option value="">Select base</option>
                  {airtableBases.map((base) => <option key={base.id} value={base.id}>{base.name}</option>)}
                </select>
                <select
                  value={selectedAirtableTable}
                  onChange={(event) => {
                    setSelectedAirtableTable(event.target.value);
                    setSelectedAirtableFields([]);
                  }}
                  disabled={!selectedAirtableBase || busy}
                  className="rounded-lg border border-cream-300 px-3 py-2 text-sm"
                >
                  <option value="">Select table</option>
                  {airtableTables.map((table) => <option key={table.id} value={table.id}>{table.name}</option>)}
                </select>
              </div>
              {airtableTables.find((table) => table.id === selectedAirtableTable)?.fields.map((field) => (
                <label key={field} className="mr-4 inline-flex items-center gap-2 text-sm text-cream-800">
                  <input
                    type="checkbox"
                    checked={selectedAirtableFields.includes(field)}
                    onChange={() => setSelectedAirtableFields((items) => items.includes(field) ? items.filter((item) => item !== field) : [...items, field])}
                    disabled={busy}
                  />
                  {field}
                </label>
              ))}
              <button type="submit" disabled={!isTenantAdmin || busy || !selectedAirtableTable || !selectedAirtableFields.length} className="block rounded-lg bg-cream-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Import selected fields</button>
            </form>
          )}
          {airtableConnected && airtableBases.length === 0 && <p className="mt-3 text-xs text-cream-700">Use “Choose table” to load the bases you authorized.</p>}
        </div>

        <div className="mt-5">
          <h3 className="font-semibold text-cream-950">Imported sources</h3>
          <div className="mt-2 space-y-2">
            {knowledgeSources.map((source) => (
              <div key={source.source_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-cream-200 p-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-cream-950">{source.name}</p>
                  <p className="text-xs text-cream-700">{source.source_type} · {source.chunk_count} searchable sections · {source.status.toLowerCase()}</p>
                  {source.error_message && <p className="text-xs text-red-700">{source.error_message}</p>}
                </div>
                <div className="flex gap-2">
                  {source.source_type === "AIRTABLE" && <button type="button" disabled={!isTenantAdmin || busy} onClick={() => void syncKnowledgeSource(source.source_id)} className="rounded-lg border border-cream-300 px-3 py-1.5 text-xs font-semibold disabled:opacity-50">Sync now</button>}
                  {isTenantAdmin && <button type="button" disabled={busy} onClick={() => void removeKnowledgeSource(source.source_id)} aria-label={`Delete source ${source.name}`} className="rounded p-1 text-cream-600 hover:bg-red-50 hover:text-red-700"><Trash2 className="h-4 w-4" /></button>}
                </div>
              </div>
            ))}
            {!knowledgeSources.length && <p className="text-sm text-cream-700">No files, web pages, or Airtable tables have been imported yet.</p>}
          </div>
        </div>
      </section>

      <section className="grid min-h-[520px] gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="overflow-hidden rounded-xl border border-cream-300 bg-white shadow-sm">
          <div className="border-b border-cream-200 p-4">
            <h2 className="font-semibold text-cream-950">Conversations</h2>
            <p className="text-xs text-cream-700">{conversations.length} recent conversations</p>
          </div>
          <div className="max-h-[470px] divide-y divide-cream-200 overflow-auto">
            {conversations.map((conversation) => (
              <button
                key={conversation.conversation_id}
                type="button"
                onClick={() => setSelectedId(conversation.conversation_id)}
                className={`w-full p-4 text-left hover:bg-cream-50 ${selectedId === conversation.conversation_id ? "bg-cream-100" : ""}`}
              >
                <span className="block truncate text-sm font-semibold text-cream-950">{conversation.contact_name || conversation.phone_number}</span>
                <span className="mt-1 block text-xs text-cream-700">{conversation.phone_number} · {conversation.status.replaceAll("_", " ").toLowerCase()}</span>
                {conversation.issue_id && <span className="mt-1 block text-xs font-medium text-amber-800">Linked support issue</span>}
              </button>
            ))}
            {!conversations.length && <p className="p-4 text-sm text-cream-700">No WhatsApp conversations yet.</p>}
          </div>
        </div>

        <div className="flex min-h-[520px] flex-col rounded-xl border border-cream-300 bg-white shadow-sm">
          <div className="border-b border-cream-200 p-4">
            <h2 className="font-semibold text-cream-950">Conversation thread</h2>
            {issue && <p className="mt-1 text-xs text-amber-800">Support issue {issue.issue_number} · {issue.status}</p>}
          </div>
          <div className="flex-1 space-y-3 overflow-auto bg-cream-50/60 p-4">
            {!selectedId && <p className="text-sm text-cream-700">Select a conversation to view its messages.</p>}
            {messages.map((message) => (
              <div key={message.message_id} className={`max-w-[85%] rounded-xl p-3 text-sm ${message.direction === "OUTBOUND" ? "ml-auto bg-green-100 text-cream-950" : "bg-white text-cream-950 shadow-sm"}`}>
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
                <p className="mt-2 text-right text-[11px] text-cream-600">{message.delivery_status.toLowerCase()} · {new Date(message.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
          <form
            className="flex gap-2 border-t border-cream-200 p-3"
            onSubmit={(event) => { event.preventDefault(); void sendReply(); }}
          >
            <input
              value={reply}
              onChange={(event) => setReply(event.target.value)}
              disabled={!selectedId || busy || !isTenantAdmin}
              maxLength={4000}
              placeholder="Reply to this customer..."
              className="min-w-0 flex-1 rounded-lg border border-cream-300 px-3 py-2 text-sm outline-none focus:border-cream-700"
            />
            <button
              type="submit"
              disabled={!selectedId || !reply.trim() || busy || !isTenantAdmin}
              className="inline-flex items-center gap-2 rounded-lg bg-cream-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              <Send className="h-4 w-4" /> Send
            </button>
          </form>
        </div>
      </section>
      {!isTenantAdmin && (
        <p className="text-sm text-cream-700">
          You have read-only access. A tenant admin can pair the number, configure tools, manage approved knowledge, and send human-support replies.
        </p>
      )}
    </div>
  );
}
