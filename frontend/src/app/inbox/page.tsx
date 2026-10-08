"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Copy,
  ExternalLink,
  FileText,
  Globe,
  Inbox,
  Key,
  Layers,
  Lock,
  Mail,
  Paperclip,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { api } from "@/lib/api";

const GMAIL_STATUS_CACHE_KEY = "ai_erp_gmail_status";

export default function InboxPage() {
  const [gmailStatus, setGmailStatus] = useState<{
    is_connected: boolean;
    connected_email: string | null;
    last_synced_at: string | null;
    synced_messages_count: number;
    is_configured?: boolean;
    client_id?: string;
  }>(() => {
    if (typeof window !== "undefined") {
      try {
        const cached = localStorage.getItem(GMAIL_STATUS_CACHE_KEY);
        if (cached) {
          const parsed = JSON.parse(cached);
          return {
            is_connected: parsed.is_connected || false,
            connected_email: parsed.connected_email || null,
            last_synced_at: parsed.last_synced_at || null,
            synced_messages_count: parsed.synced_messages_count || 0,
            is_configured: parsed.is_configured ?? false,
            client_id: parsed.client_id || "",
          };
        }
      } catch {
        // Fallback to default
      }
    }
    return {
      is_connected: false,
      connected_email: null,
      last_synced_at: null,
      synced_messages_count: 0,
      is_configured: false,
    };
  });

  const [inboxEmails, setInboxEmails] = useState<any[]>([]);
  const [sentEmails, setSentEmails] = useState<any[]>([]);
  const [salesCustomers, setSalesCustomers] = useState<any[]>([]);
  const [salesItems, setSalesItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [activeTab, setActiveTab] = useState<"inbox" | "sent">("inbox");
  const [selectedEmail, setSelectedEmail] = useState<any | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewingEmail, setReviewingEmail] = useState(false);
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [confirmingOrder, setConfirmingOrder] = useState(false);
  const [draftCustomerId, setDraftCustomerId] = useState("");
  const [draftOrderNumber, setDraftOrderNumber] = useState("");
  const [draftDeliveryDate, setDraftDeliveryDate] = useState("");
  const [draftLines, setDraftLines] = useState([{ item_id: "", quantity: "1", unit_price: "" }]);

  // Official Google OAuth Connection Modal State
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [credStatus, setCredStatus] = useState<{
    is_configured: boolean;
    client_id: string;
    has_client_secret: boolean;
  } | null>(null);
  const [clientIdInput, setClientIdInput] = useState("");
  const [clientSecretInput, setClientSecretInput] = useState("");
  const [savingCreds, setSavingCreds] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [oauthSuccess, setOauthSuccess] = useState<string | null>(null);
  const [exchangingCode, setExchangingCode] = useState(false);
  const [copiedRedirect, setCopiedRedirect] = useState(false);

  // Guard against React Strict Mode double-executing the single-use OAuth code
  const codeExchangedRef = useRef<string | null>(null);

  const redirectUri = typeof window !== "undefined" ? `${window.location.origin}/inbox` : "http://localhost:3000/inbox";

  const loadData = async () => {
    setLoading(true);
    try {
      const [statusRes, inboxRes, sentRes, customersRes, itemsRes] = await Promise.allSettled([
        api.getGmailStatus(),
        api.getEmailInbox(),
        api.getEmailSent(),
        api.getCustomers(),
        api.getItems(),
      ]);

      if (statusRes.status === "fulfilled" && statusRes.value) {
        setGmailStatus(statusRes.value);
        if (typeof window !== "undefined") {
          localStorage.setItem(GMAIL_STATUS_CACHE_KEY, JSON.stringify(statusRes.value));
        }
      }
      if (inboxRes.status === "fulfilled" && Array.isArray(inboxRes.value)) {
        setInboxEmails(inboxRes.value);
      }
      if (sentRes.status === "fulfilled" && Array.isArray(sentRes.value)) {
        setSentEmails(sentRes.value);
      }
      if (customersRes.status === "fulfilled" && Array.isArray(customersRes.value)) {
        setSalesCustomers(customersRes.value.filter((customer: any) => customer.is_active));
      }
      if (itemsRes.status === "fulfilled" && Array.isArray(itemsRes.value)) {
        setSalesItems(itemsRes.value.filter((item: any) => item.is_active && item.is_sales_item));
      }
    } catch {
      // Handled
    } finally {
      setLoading(false);
    }
  };

  const handleReviewInboundEmail = async (decision: "ACCEPT_FOR_MANUAL_PROCESSING" | "REJECT") => {
    if (!selectedEmail) return;
    const notes = reviewNotes.trim();
    if (notes.length < 3) {
      setOauthError("Add a review note with at least three characters.");
      return;
    }
    setReviewingEmail(true);
    setOauthError(null);
    try {
      const result = await api.reviewInboundEmail(selectedEmail.message_id, { decision, notes });
      const updatedEmail = { ...selectedEmail, ...result };
      setSelectedEmail(updatedEmail);
      setInboxEmails((items) => items.map((item) => item.message_id === result.message_id ? { ...item, ...result } : item));
      setReviewNotes("");
    } catch (err: any) {
      setOauthError(err?.message || "Could not record the inbound message review.");
    } finally {
      setReviewingEmail(false);
    }
  };

  const handleCreateOrderDraft = async () => {
    if (!selectedEmail) return;
    if (!draftCustomerId || !draftOrderNumber.trim() || !draftDeliveryDate || draftLines.some((line) => !line.item_id || Number(line.quantity) <= 0 || Number(line.unit_price) <= 0)) {
      setOauthError("Choose a customer, order number, delivery date, and valid item quantities and prices.");
      return;
    }
    setCreatingOrder(true);
    setOauthError(null);
    try {
      const result = await api.createSalesOrderFromEmail(selectedEmail.message_id, {
        customer_id: draftCustomerId,
        order_number: draftOrderNumber.trim(),
        delivery_date: draftDeliveryDate,
        items: draftLines.map((line) => ({ item_id: line.item_id, quantity: line.quantity, unit_price: line.unit_price })),
      });
      const updatedEmail = { ...selectedEmail, status: "SALES_ORDER_DRAFT_CREATED", sales_order_id: result.sales_order_id };
      setSelectedEmail(updatedEmail);
      setInboxEmails((messages) => messages.map((message) => message.message_id === result.message_id ? { ...message, ...updatedEmail } : message));
    } catch (err: any) {
      setOauthError(err?.message || "Could not create the pending sales-order draft.");
    } finally {
      setCreatingOrder(false);
    }
  };

  const handleConfirmOrderDraft = async () => {
    if (!selectedEmail?.sales_order_id) return;
    setConfirmingOrder(true);
    setOauthError(null);
    try {
      const result = await api.confirmSalesOrder(selectedEmail.sales_order_id);
      const updatedEmail = { ...selectedEmail, sales_order_status: result.status, fulfillment_warehouse_id: result.warehouse_id };
      setSelectedEmail(updatedEmail);
      setInboxEmails((messages) => messages.map((message) => message.message_id === selectedEmail.message_id ? { ...message, ...updatedEmail } : message));
    } catch (err: any) {
      setOauthError(err?.message || "Could not confirm the order or reserve stock.");
    } finally {
      setConfirmingOrder(false);
    }
  };

  // Handle OAuth code redirect from Google (e.g. /inbox?code=4/0AbCd...)
  useEffect(() => {
    loadData();

    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get("code");
      const err = urlParams.get("error");

      if (err) {
        setOauthError(`Google OAuth error: ${err}`);
        window.history.replaceState({}, "", window.location.pathname);
      } else if (code) {
        // Guard against duplicate execution in React Strict Mode or fast reloads
        if (codeExchangedRef.current !== code) {
          codeExchangedRef.current = code;
          // Immediately sanitize URL so browser reload (F5) will reload clean /inbox without replaying code
          window.history.replaceState({}, "", window.location.pathname);
          handleOAuthCallback(code);
        }
      }
    }
  }, []);

  const handleOAuthCallback = async (code: string) => {
    setExchangingCode(true);
    setOauthError(null);
    try {
      const res = await api.connectGmailCallback({
        code,
        redirect_uri: window.location.origin + "/inbox",
      });
      window.history.replaceState({}, "", window.location.pathname);
      setOauthSuccess(`Successfully authenticated Google Workspace account: ${res.connected_email}`);
      await loadData();
    } catch (err: any) {
      window.history.replaceState({}, "", window.location.pathname);
      setOauthError(`Google OAuth token exchange failed: ${err.message}`);
    } finally {
      setExchangingCode(false);
    }
  };

  const handleOpenConnectModal = async () => {
    setOauthError(null);
    setOauthSuccess(null);
    setShowConnectModal(true);
    try {
      const creds = await api.getGmailCredentials();
      setCredStatus(creds);
      if (creds.client_id) {
        setClientIdInput(creds.client_id);
      }
    } catch {
      setCredStatus({ is_configured: false, client_id: "", has_client_secret: false });
    }
  };

  const handleSaveCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingCreds(true);
    setOauthError(null);
    try {
      const res = await api.saveGmailCredentials({
        client_id: clientIdInput.trim(),
        client_secret: clientSecretInput.trim(),
      });
      setCredStatus({
        is_configured: true,
        client_id: res.client_id,
        has_client_secret: true,
      });
      setOauthSuccess("Credentials successfully saved to environment and .env configuration!");
      await loadData();
    } catch (err: any) {
      setOauthError(`Failed to save credentials: ${err.message}`);
    } finally {
      setSavingCreds(false);
    }
  };

  const handleLaunchGoogleConsent = async () => {
    setOauthError(null);
    try {
      const authRes = await api.getGmailAuthUrl(window.location.origin + "/inbox");
      if (!authRes.is_configured || !authRes.authorization_url) {
        setOauthError(
          authRes.error || "Google Client ID & Client Secret are not configured in environment variables."
        );
        return;
      }
      // Redirect to the official Google OAuth consent screen
      window.location.href = authRes.authorization_url;
    } catch (err: any) {
      setOauthError(`Failed to generate Google consent URL: ${err.message}`);
    }
  };

  const handleDisconnectGmail = async () => {
    try {
      await api.disconnectGmail();
      const updated = {
        is_connected: false,
        connected_email: null,
        last_synced_at: null,
        synced_messages_count: 0,
        is_configured: gmailStatus.is_configured,
      };
      setGmailStatus(updated);
      if (typeof window !== "undefined") {
        localStorage.removeItem(GMAIL_STATUS_CACHE_KEY);
      }
      await loadData();
    } catch {
      // Handled
    }
  };

  const handleSyncGmail = async () => {
    setSyncing(true);
    setOauthError(null);
    try {
      await api.syncGmailInbox();
      await loadData();
    } catch (err: any) {
      setOauthError(`Gmail sync error: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const copyRedirectUri = () => {
    navigator.clipboard.writeText(redirectUri);
    setCopiedRedirect(true);
    setTimeout(() => setCopiedRedirect(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-cream-300 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-cream-900">
              Communication & Inbound Email Hub
            </h1>
            <span className="rounded bg-cream-200 px-2 py-0.5 text-[11px] font-mono text-cream-700">
              RFC 822 / SMTP / Gmail OAuth 2.0
            </span>
          </div>
          <p className="text-xs text-cream-700 mt-0.5">
            Autonomous ingestion of customer RFQ emails, multimodal BAML extraction, and 300-second quotation delivery.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Code Exchange Loading Banner */}
      {exchangingCode && (
        <div className="p-4 rounded-xl border border-primary/30 bg-primary/10 flex items-center gap-3 text-xs text-foreground">
          <RefreshCw className="h-4 w-4 animate-spin text-primary shrink-0" />
          <span>Exchanging official Google OAuth 2.0 authorization code with Google servers...</span>
        </div>
      )}

      {/* OAuth Error / Success Alerts */}
      {oauthError && (
        <div className="p-3.5 rounded-xl border border-terracotta-500/30 bg-terracotta-50 flex items-start justify-between gap-3 text-xs text-terracotta-700">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{oauthError}</span>
          </div>
          <button onClick={() => setOauthError(null)} className="text-terracotta-500 hover:text-terracotta-700">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {oauthSuccess && (
        <div className="p-3.5 rounded-xl border border-sage-500/30 bg-sage-50 flex items-start justify-between gap-3 text-xs text-sage-800">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{oauthSuccess}</span>
          </div>
          <button onClick={() => setOauthSuccess(null)} className="text-sage-600 hover:text-sage-800">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Connection Card */}
      <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-cream-300 pb-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-cream-200 p-2.5 text-cream-800 border border-cream-300">
              <Mail className="h-5 w-5 text-amberGold-600" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-cream-900">
                  Google Workspace & Gmail OAuth 2.0 Connection
                </h2>
                {gmailStatus.is_connected ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-sage-50 px-2 py-0.5 text-[10px] font-medium text-sage-700 border border-sage-200">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>Active Sync</span>
                  </span>
                ) : (
                  <span className="rounded-full bg-cream-200 px-2 py-0.5 text-[10px] font-mono text-cream-700">
                    Not Connected
                  </span>
                )}
              </div>
              <p className="text-xs text-cream-700 mt-1">
                Authorizes the Revenue Agent to monitor corporate sales inboxes, parse RFQs, and dispatch formal quotation PDFs.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {gmailStatus.is_connected ? (
              <>
                <button
                  onClick={handleSyncGmail}
                  disabled={syncing}
                  className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  <RefreshCw className={`h-3 w-3 ${syncing ? "animate-spin" : ""}`} />
                  <span>{syncing ? "Syncing..." : "Sync Gmail Inbox"}</span>
                </button>
                <button
                  onClick={handleDisconnectGmail}
                  className="rounded-md border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-terracotta-700 hover:bg-terracotta-50"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                onClick={handleOpenConnectModal}
                className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
              >
                <Lock className="h-3 w-3 text-amberGold-400" />
                <span>Connect Corporate Gmail</span>
              </button>
            )}
          </div>
        </div>

        {gmailStatus.is_connected && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
            <div className="rounded border border-cream-300 bg-cream-50 p-2.5">
              <span className="text-[10px] text-cream-600 block">AUTHENTICATED INBOX:</span>
              <span className="font-semibold text-cream-900">{gmailStatus.connected_email}</span>
            </div>
            <div className="rounded border border-cream-300 bg-cream-50 p-2.5">
              <span className="text-[10px] text-cream-600 block">INBOUND ORDER HANDLING:</span>
              <span className="font-semibold text-amberGold-700">Reviewer decision required</span>
            </div>
            <div className="rounded border border-cream-300 bg-cream-50 p-2.5">
              <span className="text-[10px] text-cream-600 block">SMTP INTAKE:</span>
              <span className="font-semibold text-cream-900">Disabled pending tenant routing</span>
            </div>
          </div>
        )}
      </div>

      {/* Tabs & Messages View */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-cream-300 pb-2">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setActiveTab("inbox")}
              className={`flex items-center gap-1.5 text-xs font-medium pb-2 border-b-2 transition-colors ${
                activeTab === "inbox"
                  ? "border-cream-900 text-cream-900"
                  : "border-transparent text-cream-600 hover:text-cream-900"
              }`}
            >
              <Inbox className="h-3.5 w-3.5" />
              <span>Inbound Messages ({inboxEmails.length})</span>
            </button>
            <button
              onClick={() => setActiveTab("sent")}
              className={`flex items-center gap-1.5 text-xs font-medium pb-2 border-b-2 transition-colors ${
                activeTab === "sent"
                  ? "border-cream-900 text-cream-900"
                  : "border-transparent text-cream-600 hover:text-cream-900"
              }`}
            >
              <Send className="h-3.5 w-3.5" />
              <span>Outbound Email Records ({sentEmails.length})</span>
            </button>
          </div>
        </div>

        {activeTab === "inbox" && (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-sm">
            {inboxEmails.length === 0 ? (
              <div className="py-16 text-center text-cream-600">
                <Mail className="h-10 w-10 mx-auto text-cream-400 mb-2" />
                <p className="text-sm font-medium text-cream-900">No inbound emails in enterprise queue</p>
                <p className="text-xs text-cream-600 mt-1 max-w-sm mx-auto">
                  Connect Gmail to sync messages into this tenant&apos;s review queue. SMTP intake is disabled until authenticated tenant routing is configured.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-cream-300 bg-cream-200/50 text-[11px] font-mono text-cream-700">
                      <th className="py-2.5 px-4">From</th>
                      <th className="py-2.5 px-4">Subject</th>
                      <th className="py-2.5 px-4">Event Type</th>
                      <th className="py-2.5 px-4">Status</th>
                      <th className="py-2.5 px-4">Linked DAG</th>
                      <th className="py-2.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200 font-mono">
                    {inboxEmails.map((msg) => (
                      <tr key={msg.message_id} className="hover:bg-cream-200/40 transition-colors">
                        <td className="py-3 px-4 font-medium text-cream-900 max-w-[200px] truncate">
                          {msg.sender}
                        </td>
                        <td className="py-3 px-4 max-w-[320px]">
                          <div className="truncate text-cream-900 font-medium">{msg.subject}</div>
                          <div className="text-[10px] text-cream-600 truncate">{msg.body_text}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="rounded bg-cream-200 px-1.5 py-0.5 text-[10px] text-cream-800">
                            {msg.event_type}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-[10px] font-semibold text-sage-700">
                            {msg.status}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          {msg.associated_dag_id ? (
                            <Link
                              href={`/agents?dag_id=${encodeURIComponent(msg.associated_dag_id)}`}
                              className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                            >
                              <span>{msg.associated_dag_id}</span>
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          ) : (
                            <span className="text-cream-400">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => {
                              setSelectedEmail(msg);
                              setReviewNotes("");
                              setDraftOrderNumber(`SO-EMAIL-${String(msg.message_id).slice(-10).toUpperCase()}`);
                              setDraftCustomerId("");
                              setDraftDeliveryDate("");
                              setDraftLines([{ item_id: "", quantity: "1", unit_price: "" }]);
                            }}
                            className="rounded border border-cream-300 bg-cream-50 px-2.5 py-1 text-[11px] text-cream-900 hover:bg-cream-200"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === "sent" && (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-sm">
            {sentEmails.length === 0 ? (
              <div className="py-16 text-center text-cream-600">
                <Send className="h-10 w-10 mx-auto text-cream-400 mb-2" />
                <p className="text-sm font-medium text-cream-900">No outbound quotations dispatched yet</p>
                <p className="text-xs text-cream-600 mt-1 max-w-sm mx-auto">
                  Outbound quotation PDFs sent to prospective customers will be tracked here with transmission SLA timestamps.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-cream-300 bg-cream-200/50 text-[11px] font-mono text-cream-700">
                      <th className="py-2.5 px-4">Recipient</th>
                      <th className="py-2.5 px-4">Subject</th>
                      <th className="py-2.5 px-4">Attachment</th>
                      <th className="py-2.5 px-4">Size</th>
                      <th className="py-2.5 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200 font-mono">
                    {sentEmails.map((msg) => (
                      <tr key={msg.dispatch_id} className="hover:bg-cream-200/40 transition-colors">
                        <td className="py-3 px-4 font-medium text-cream-900">{msg.recipient}</td>
                        <td className="py-3 px-4 text-cream-900">{msg.subject}</td>
                        <td className="py-3 px-4">
                          {msg.attachment_name ? (
                            <span className="inline-flex items-center gap-1 text-[11px] text-cream-800">
                              <Paperclip className="h-3 w-3" />
                              <span>{msg.attachment_name}</span>
                            </span>
                          ) : (
                            <span className="text-cream-400">None</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-cream-700">
                          {msg.attachment_size_bytes ? `${Math.round(msg.attachment_size_bytes / 1024)} KB` : "-"}
                        </td>
                        <td className="py-3 px-4">
                          <span className="rounded bg-sage-50 px-2 py-0.5 text-[10px] font-medium text-sage-700 border border-sage-200">
                            {msg.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Official Google OAuth 2.0 Setup Modal */}
      {showConnectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-xl rounded-2xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-5 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-cream-300 pb-4">
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-white p-2.5 shadow-sm border border-cream-200">
                  <svg className="h-6 w-6" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-base font-semibold text-cream-900">
                    Google Workspace & Gmail OAuth 2.0 Setup
                  </h3>
                  <p className="text-xs text-cream-700">Official enterprise email authorization modal</p>
                </div>
              </div>
              <button
                onClick={() => setShowConnectModal(false)}
                className="text-cream-500 hover:text-cream-900 rounded-lg p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Config Status Pill */}
            <div className="flex items-center justify-between text-xs p-3 rounded-lg border border-cream-300 bg-cream-50">
              <span className="text-cream-700 font-medium">Environment Variables Status:</span>
              {credStatus?.is_configured ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-sage-50 px-2.5 py-0.5 font-semibold text-sage-800 border border-sage-200">
                  <CheckCircle2 className="h-3.5 w-3.5 text-sage-600" />
                  Configured in Environment (.env)
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 font-semibold text-amber-800 border border-amber-200">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                  Not Present in Environment Yet
                </span>
              )}
            </div>

            {/* If NOT Configured: Instructions & Input Form */}
            {!credStatus?.is_configured ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3.5 text-xs text-amber-900 space-y-2">
                  <p className="font-semibold flex items-center gap-1.5">
                    <Key className="h-4 w-4 text-amber-700" />
                    Google Cloud Console Credentials Required
                  </p>
                  <p className="text-[11px] leading-relaxed">
                    To connect live corporate Gmail with zero fake data, the application requires your Google Cloud OAuth 2.0 Client ID and Secret.
                  </p>
                  <ol className="list-decimal list-inside space-y-1 text-[11px] pt-1">
                    <li>
                      Go to{" "}
                      <a
                        href="https://console.cloud.google.com/apis/credentials"
                        target="_blank"
                        rel="noreferrer"
                        className="font-semibold underline text-primary inline-flex items-center gap-0.5"
                      >
                        Google Cloud Console Credentials
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </li>
                    <li>Create an <strong>OAuth 2.0 Client ID</strong> (Application type: <em>Web application</em>).</li>
                    <li>
                      Add this Authorized Redirect URI:
                      <div className="mt-1 flex items-center gap-2 font-mono bg-white p-1.5 rounded border border-cream-300">
                        <span className="truncate text-[10px] text-cream-900 flex-1">{redirectUri}</span>
                        <button
                          type="button"
                          onClick={copyRedirectUri}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-cream-100 text-[10px] text-cream-700 hover:bg-cream-200"
                        >
                          <Copy className="h-3 w-3" />
                          <span>{copiedRedirect ? "Copied!" : "Copy URI"}</span>
                        </button>
                      </div>
                    </li>
                    <li>Paste your Client ID and Client Secret below to configure them in <code className="font-mono bg-white px-1 rounded">.env</code>.</li>
                  </ol>
                </div>

                <form onSubmit={handleSaveCredentials} className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-cream-900 mb-1">
                      GOOGLE_CLIENT_ID
                    </label>
                    <input
                      type="text"
                      required
                      value={clientIdInput}
                      onChange={(e) => setClientIdInput(e.target.value)}
                      placeholder="e.g. 1234567890-abcdef.apps.googleusercontent.com"
                      className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 placeholder-cream-400 focus:outline-none focus:ring-1 focus:ring-cream-800 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-cream-900 mb-1">
                      GOOGLE_CLIENT_SECRET
                    </label>
                    <input
                      type="password"
                      required
                      value={clientSecretInput}
                      onChange={(e) => setClientSecretInput(e.target.value)}
                      placeholder="e.g. GOCSPX-xxxxxxxxxxxxxxxxxxxx"
                      className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900 placeholder-cream-400 focus:outline-none focus:ring-1 focus:ring-cream-800 font-mono"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={savingCreds || !clientIdInput || !clientSecretInput}
                    className="w-full flex items-center justify-center gap-2 rounded-lg bg-cream-900 py-2 text-xs font-semibold text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                  >
                    <Key className="h-3.5 w-3.5" />
                    <span>{savingCreds ? "Saving to .env..." : "Save Credentials to .env"}</span>
                  </button>
                </form>
              </div>
            ) : (
              /* If Configured: Display Official Connect Action */
              <div className="space-y-4">
                <div className="rounded-lg border border-cream-300 bg-cream-50 p-3.5 space-y-2 text-xs font-mono">
                  <div className="flex justify-between items-center">
                    <span className="text-cream-600">CLIENT ID:</span>
                    <span className="font-semibold text-cream-900 truncate max-w-[280px]">
                      {credStatus.client_id}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-cream-600">REDIRECT URI:</span>
                    <span className="font-semibold text-cream-900 truncate max-w-[280px]">
                      {redirectUri}
                    </span>
                  </div>
                  <div className="pt-2 border-t border-cream-200">
                    <span className="text-[10px] text-cream-600 block mb-1">REQUESTED OAUTH SCOPES:</span>
                    <ul className="text-[10px] text-cream-800 space-y-0.5">
                      <li>• https://www.googleapis.com/auth/gmail.readonly (Ingest RFQs)</li>
                      <li>• https://www.googleapis.com/auth/gmail.send (Dispatch Quotation PDFs)</li>
                      <li>• https://www.googleapis.com/auth/userinfo.email (Identify Account)</li>
                    </ul>
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={handleLaunchGoogleConsent}
                    className="w-full flex items-center justify-center gap-3 rounded-xl bg-white border border-cream-300 py-3 text-xs font-semibold text-cream-900 hover:bg-cream-50 shadow-sm transition-colors"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24">
                      <path
                        fill="#4285F4"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                      />
                    </svg>
                    <span>Authorize with Official Google Account</span>
                  </button>
                  <p className="text-center text-[10px] text-cream-600 mt-2">
                    Opens accounts.google.com OAuth consent screen to grant live mailbox permissions.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Message Inspection Drawer */}
      {selectedEmail && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs">
          <div className="w-full max-w-xl bg-cream-50 h-full p-6 shadow-2xl border-l border-cream-300 overflow-y-auto space-y-5">
            <div className="flex items-center justify-between border-b border-cream-300 pb-4">
              <div>
                <span className="text-[10px] font-mono text-cream-600 uppercase">INSPECT INGESTED RFC 822 MESSAGE</span>
                <h3 className="text-base font-semibold text-cream-900">{selectedEmail.subject}</h3>
              </div>
              <button
                onClick={() => setSelectedEmail(null)}
                className="rounded-lg p-1.5 text-cream-600 hover:bg-cream-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div className="rounded border border-cream-300 bg-cream-100 p-3 space-y-1">
                <div><span className="text-cream-600">SENDER:</span> {selectedEmail.sender}</div>
                <div><span className="text-cream-600">RECIPIENT:</span> {selectedEmail.recipient}</div>
                <div><span className="text-cream-600">EVENT TYPE:</span> {selectedEmail.event_type}</div>
                <div><span className="text-cream-600">STATUS:</span> {selectedEmail.status}</div>
              </div>

              <div>
                <span className="text-[11px] font-semibold text-cream-900 block mb-1">Message Body:</span>
                <div className="rounded border border-cream-300 bg-cream-100 p-3 whitespace-pre-wrap text-[11px] text-cream-800 max-h-48 overflow-y-auto">
                  {selectedEmail.body_text}
                </div>
              </div>

              {selectedEmail.attachments && selectedEmail.attachments.length > 0 && (
                <div>
                  <span className="text-[11px] font-semibold text-cream-900 block mb-1">
                    Attachments ({selectedEmail.attachments.length}):
                  </span>
                  <div className="space-y-1.5">
                    {selectedEmail.attachments.map((att: any, idx: number) => (
                      <div
                        key={idx}
                        className="rounded border border-cream-300 bg-cream-100 p-2.5 flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-primary" />
                          <span className="text-[11px] font-medium text-cream-900">{att.filename}</span>
                        </div>
                        <span className="text-[10px] text-cream-600">
                          {att.size_bytes ? `${Math.round(att.size_bytes / 1024)} KB` : "Document"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedEmail.status === "HUMAN_REVIEW_REQUIRED" ? (
                <div className="rounded-lg border border-amberGold-300 bg-amberGold-50 p-4 space-y-3">
                  <div>
                    <h4 className="text-xs font-semibold text-cream-900">Reviewer decision</h4>
                    <p className="mt-1 text-[11px] text-cream-700">
                      Accepting records manual follow-up only. It does not create a sales order or run fulfillment.
                    </p>
                  </div>
                  <textarea
                    value={reviewNotes}
                    onChange={(event) => setReviewNotes(event.target.value)}
                    maxLength={1000}
                    rows={3}
                    placeholder="Add a short audit note (required)"
                    className="w-full rounded border border-cream-300 bg-white p-2 text-xs text-cream-900"
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => handleReviewInboundEmail("ACCEPT_FOR_MANUAL_PROCESSING")}
                      disabled={reviewingEmail}
                      className="rounded bg-sage-700 px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-50"
                    >
                      {reviewingEmail ? "Saving…" : "Accept for manual processing"}
                    </button>
                    <button
                      onClick={() => handleReviewInboundEmail("REJECT")}
                      disabled={reviewingEmail}
                      className="rounded border border-terracotta-300 bg-white px-3 py-2 text-[11px] font-semibold text-terracotta-800 disabled:opacity-50"
                    >
                      Reject message
                    </button>
                  </div>
                </div>
              ) : selectedEmail.review_notes ? (
                <div className="rounded border border-cream-300 bg-cream-100 p-3 text-[11px]">
                  <div className="font-semibold text-cream-900">Reviewer note</div>
                  <div className="mt-1 whitespace-pre-wrap text-cream-700">{selectedEmail.review_notes}</div>
                  <div className="mt-2 text-cream-600">This decision did not execute a workflow.</div>
                </div>
              ) : null}

              {selectedEmail.status === "ACCEPTED_FOR_MANUAL_PROCESSING" && selectedEmail.event_type === "erp.crm.inbound_customer_order" && (
                <div className="rounded-lg border border-cream-300 bg-cream-100 p-4 space-y-3">
                  <div>
                    <h4 className="text-xs font-semibold text-cream-900">Create a pending order draft</h4>
                    <p className="mt-1 text-[11px] text-cream-700">
                      This records the reviewed order with tenant-owned customer and catalog items. It does not reserve stock or start fulfillment.
                    </p>
                  </div>
                  <label className="block text-[11px] text-cream-700">
                    Customer
                    <select value={draftCustomerId} onChange={(event) => setDraftCustomerId(event.target.value)} className="mt-1 w-full rounded border border-cream-300 bg-white p-2 text-xs text-cream-900">
                      <option value="">Select active customer</option>
                      {salesCustomers.map((customer: any) => <option key={customer.customer_id} value={customer.customer_id}>{customer.customer_name} ({customer.customer_code})</option>)}
                    </select>
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <label className="text-[11px] text-cream-700">Order number<input value={draftOrderNumber} onChange={(event) => setDraftOrderNumber(event.target.value)} maxLength={64} className="mt-1 w-full rounded border border-cream-300 bg-white p-2 text-xs text-cream-900" /></label>
                    <label className="text-[11px] text-cream-700">Requested delivery date<input type="date" value={draftDeliveryDate} onChange={(event) => setDraftDeliveryDate(event.target.value)} className="mt-1 w-full rounded border border-cream-300 bg-white p-2 text-xs text-cream-900" /></label>
                  </div>
                  {draftLines.map((line, index) => (
                    <div key={index} className="grid grid-cols-1 sm:grid-cols-3 gap-2 rounded border border-cream-300 bg-white p-2">
                      <select value={line.item_id} onChange={(event) => {
                        const item = salesItems.find((candidate: any) => candidate.item_id === event.target.value);
                        setDraftLines((lines) => lines.map((entry, lineIndex) => lineIndex === index ? { ...entry, item_id: event.target.value, unit_price: item ? String(item.standard_rate) : "" } : entry));
                      }} className="rounded border border-cream-300 p-2 text-xs text-cream-900">
                        <option value="">Select sales item</option>
                        {salesItems.map((item: any) => <option key={item.item_id} value={item.item_id}>{item.item_code} — {item.item_name}</option>)}
                      </select>
                      <input type="number" min="0.0001" step="0.0001" value={line.quantity} onChange={(event) => setDraftLines((lines) => lines.map((entry, lineIndex) => lineIndex === index ? { ...entry, quantity: event.target.value } : entry))} aria-label="Quantity" placeholder="Quantity" className="rounded border border-cream-300 p-2 text-xs text-cream-900" />
                      <input type="number" min="0.0001" step="0.0001" value={line.unit_price} onChange={(event) => setDraftLines((lines) => lines.map((entry, lineIndex) => lineIndex === index ? { ...entry, unit_price: event.target.value } : entry))} aria-label="Unit price" placeholder="Unit price" className="rounded border border-cream-300 p-2 text-xs text-cream-900" />
                    </div>
                  ))}
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => setDraftLines((lines) => [...lines, { item_id: "", quantity: "1", unit_price: "" }])} disabled={draftLines.length >= 100} className="rounded border border-cream-300 bg-white px-3 py-2 text-[11px] text-cream-800 disabled:opacity-50">Add line</button>
                    <button onClick={handleCreateOrderDraft} disabled={creatingOrder} className="rounded bg-primary px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-50">{creatingOrder ? "Creating draft…" : "Create pending-confirmation draft"}</button>
                  </div>
                </div>
              )}

              {selectedEmail.sales_order_id && (
                <div className="rounded border border-cream-300 bg-cream-100 p-3 text-[11px] text-cream-800">
                  Sales order <span className="font-mono">{selectedEmail.sales_order_id}</span> — {selectedEmail.sales_order_status || "PENDING_CONFIRMATION"}.
                  {selectedEmail.sales_order_status === "PENDING_CONFIRMATION" || !selectedEmail.sales_order_status ? (
                    <div className="mt-2 space-y-2">
                      <p>Confirming reserves available stock in one warehouse. It does not ship or invoice the order.</p>
                      <button onClick={handleConfirmOrderDraft} disabled={confirmingOrder} className="rounded bg-sage-700 px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-50">
                        {confirmingOrder ? "Checking stock…" : "Confirm order and reserve stock"}
                      </button>
                    </div>
                  ) : (
                    <p className="mt-1">Reserved warehouse: {selectedEmail.fulfillment_warehouse_id || "not recorded"}. Fulfillment has not started.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
