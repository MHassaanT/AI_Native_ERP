"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, MessageCircle, RefreshCw, Send, Smartphone, Trash2, Wifi, WifiOff } from "lucide-react";
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

export default function WhatsAppSupportPage() {
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [issue, setIssue] = useState<{ issue_number: string; status: string } | null>(null);
  const [tools, setTools] = useState<ToolBinding[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeEntry[]>([]);
  const [knowledgeTitle, setKnowledgeTitle] = useState("");
  const [knowledgeContent, setKnowledgeContent] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [isTenantAdmin, setIsTenantAdmin] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [connection, conversationData, toolData, knowledgeData] = await Promise.all([
        api.getWhatsAppStatus(),
        api.getWhatsAppConversations(),
        api.getWhatsAppTools(),
        api.getWhatsAppKnowledge(),
      ]);
      setStatus(connection);
      setConversations(conversationData.conversations || []);
      setTools(toolData.tools || []);
      setKnowledge(knowledgeData.entries || []);
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
