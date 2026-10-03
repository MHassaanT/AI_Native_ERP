"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Award,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileCheck,
  FileText,
  Filter,
  Headset,
  Kanban,
  Layers,
  LifeBuoy,
  Mail,
  Megaphone,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  Tag,
  TrendingUp,
  UserCheck,
  Users,
  Wrench,
  X,
  ChevronRight,
  ArrowRight,
  Flame,
  Building2,
  LayoutGrid,
  List,
  Info,
  DollarSign,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "leads" | "pipeline" | "campaigns" | "tickets" | "slas" | "warranty";

const STAGES = [
  { id: "PROSPECTING", label: "Prospecting", prob: 10, color: "bg-stone-100 text-stone-700 border-stone-300" },
  { id: "QUALIFICATION", label: "Qualification", prob: 25, color: "bg-blue-50 text-blue-700 border-blue-200" },
  { id: "PROPOSAL", label: "Proposal", prob: 50, color: "bg-purple-50 text-purple-700 border-purple-200" },
  { id: "NEGOTIATION", label: "Negotiation", prob: 75, color: "bg-amber-50 text-amber-700 border-amber-200" },
  { id: "CLOSED_WON", label: "Closed Won", prob: 100, color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { id: "CLOSED_LOST", label: "Closed Lost", prob: 0, color: "bg-rose-50 text-rose-700 border-rose-200" },
];

export default function CRMSupportPage() {
  const [activeTab, setActiveTab] = useState<TabType>("leads");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Reference Catalogs
  const [customers, setCustomers] = useState<any[]>([]);
  const [catalogItems, setCatalogItems] = useState<any[]>([]);

  // Tab 1: Leads
  const [leads, setLeads] = useState<any[]>([]);
  const [leadSearch, setLeadSearch] = useState("");
  const [leadStatusFilter, setLeadStatusFilter] = useState("");
  const [showLeadModal, setShowLeadModal] = useState(false);
  const [leadName, setLeadName] = useState("");
  const [leadCompany, setLeadCompany] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadRevenue, setLeadRevenue] = useState("100000");
  const [leadEmployees, setLeadEmployees] = useState("25");
  const [leadIndustry, setLeadIndustry] = useState("Manufacturing");
  const [leadMarketSegment, setLeadMarketSegment] = useState("Commercial");
  const [leadTerritory, setLeadTerritory] = useState("Global");
  const [leadSource, setLeadSource] = useState("CAMPAIGN");
  const [leadNotes, setLeadNotes] = useState("");
  const [breakdownLead, setBreakdownLead] = useState<any | null>(null);

  // Tab 2: Opportunities & Pipeline
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [pipelineSummary, setPipelineSummary] = useState<any | null>(null);
  const [oppSearch, setOppSearch] = useState("");
  const [oppViewMode, setOppViewMode] = useState<"kanban" | "table">("kanban");
  const [showOppModal, setShowOppModal] = useState(false);
  const [oppTitle, setOppTitle] = useState("");
  const [oppPartyType, setOppPartyType] = useState<"CUSTOMER" | "LEAD">("CUSTOMER");
  const [oppPartyId, setOppPartyId] = useState("");
  const [oppPartyName, setOppPartyName] = useState("");
  const [oppAmount, setOppAmount] = useState("50000");
  const [oppStage, setOppStage] = useState("PROSPECTING");
  const [oppNotes, setOppNotes] = useState("");

  // Convert Lead Modal
  const [convertTargetLead, setConvertTargetLead] = useState<any | null>(null);
  const [convertOppTitle, setConvertOppTitle] = useState("");
  const [convertOppAmount, setConvertOppAmount] = useState("25000");

  // Tab 3: Campaigns & Contracts
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [contracts, setContracts] = useState<any[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [showCampaignModal, setShowCampaignModal] = useState(false);
  const [campName, setCampName] = useState("");
  const [campType, setCampType] = useState("EMAIL");
  const [campBudget, setCampBudget] = useState("5000");
  const [showDripModal, setShowDripModal] = useState(false);
  const [dripSubject, setDripSubject] = useState("");
  const [dripDelay, setDripDelay] = useState("3");
  const [dripBody, setDripBody] = useState("");
  const [showContractModal, setShowContractModal] = useState(false);
  const [contractSubject, setContractSubject] = useState("");
  const [contractCustomerId, setContractCustomerId] = useState("");
  const [contractValue, setContractValue] = useState("12000");
  const [contractStartDate, setContractStartDate] = useState(new Date().toISOString().split("T")[0]);
  const [contractEndDate, setContractEndDate] = useState(
    new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString().split("T")[0]
  );

  // Tab 4: Tickets / Helpdesk
  const [issues, setIssues] = useState<any[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<any | null>(null);
  const [issueSearch, setIssueSearch] = useState("");
  const [issuePriorityFilter, setIssuePriorityFilter] = useState("");
  const [showIssueModal, setShowIssueModal] = useState(false);
  const [issueSubject, setIssueSubject] = useState("");
  const [issueCustomerId, setIssueCustomerId] = useState("");
  const [issueRaisedName, setIssueRaisedName] = useState("");
  const [issueRaisedEmail, setIssueRaisedEmail] = useState("");
  const [issuePriority, setIssuePriority] = useState("MEDIUM");
  const [issueType, setIssueType] = useState("TECHNICAL");
  const [issueDescription, setIssueDescription] = useState("");
  const [replyMessage, setReplyMessage] = useState("");
  const [isInternalNote, setIsInternalNote] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);
  const [resolutionDetails, setResolutionDetails] = useState("");

  // Tab 5: SLAs
  const [slas, setSlas] = useState<any[]>([]);
  const [showSlaModal, setShowSlaModal] = useState(false);
  const [slaName, setSlaName] = useState("");
  const [slaDefault, setSlaDefault] = useState(false);
  const [slaUrgentHours, setSlaUrgentHours] = useState("1.0");
  const [slaUrgentResHours, setSlaUrgentResHours] = useState("6.0");
  const [slaHighHours, setSlaHighHours] = useState("2.0");
  const [slaHighResHours, setSlaHighResHours] = useState("12.0");
  const [slaMedHours, setSlaMedHours] = useState("4.0");
  const [slaMedResHours, setSlaMedResHours] = useState("24.0");

  // Tab 6: Warranty & RMA
  const [verifySerialInput, setVerifySerialInput] = useState("");
  const [verificationResult, setVerificationResult] = useState<any | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [claims, setClaims] = useState<any[]>([]);
  const [showClaimModal, setShowClaimModal] = useState(false);
  const [claimSerial, setClaimSerial] = useState("");
  const [claimCustomerId, setClaimCustomerId] = useState("");
  const [claimComplaint, setClaimComplaint] = useState("");
  const [claimResolutionType, setClaimResolutionType] = useState("REPLACE_FREE");

  // Load Data
  const loadData = async () => {
    setLoading(true);
    try {
      const [
        leadData,
        oppData,
        pipeSumm,
        campData,
        contractData,
        issueData,
        slaData,
        claimData,
        custData,
        itemData,
      ] = await Promise.all([
        api.getLeads({ search: leadSearch || undefined, status: leadStatusFilter || undefined }).catch(() => []),
        api.getOpportunities({ search: oppSearch || undefined }).catch(() => []),
        api.getPipelineSummary().catch(() => null),
        api.getCampaigns().catch(() => []),
        api.getContracts().catch(() => []),
        api.getIssues({ search: issueSearch || undefined, priority: issuePriorityFilter || undefined }).catch(() => []),
        api.getSlas().catch(() => []),
        api.getWarrantyClaims().catch(() => []),
        api.getCustomers().catch(() => []),
        api.getItems().catch(() => []),
      ]);

      setLeads(leadData);
      setOpportunities(oppData);
      setPipelineSummary(pipeSumm);
      setCampaigns(campData);
      setContracts(contractData);
      setIssues(issueData);
      setSlas(slaData);
      setClaims(claimData);
      setCustomers(custData);
      setCatalogItems(itemData);

      if (selectedIssue) {
        const found = issueData.find((i: any) => i.issue_id === selectedIssue.issue_id);
        if (found) {
          const fresh = await api.getIssue(found.issue_id).catch(() => found);
          setSelectedIssue(fresh);
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load CRM data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [leadSearch, leadStatusFilter, oppSearch, issueSearch, issuePriorityFilter]);

  // Lead Actions
  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createLead({
        lead_name: leadName.trim(),
        company_name: leadCompany.trim() || undefined,
        email_id: leadEmail.trim() || undefined,
        mobile_no: leadPhone.trim() || undefined,
        annual_revenue: parseFloat(leadRevenue) || 0,
        no_of_employees: parseInt(leadEmployees) || 1,
        industry: leadIndustry,
        market_segment: leadMarketSegment,
        territory: leadTerritory,
        source: leadSource,
        notes: leadNotes.trim() || undefined,
      });
      setShowLeadModal(false);
      setLeadName("");
      setLeadCompany("");
      setLeadEmail("");
      setLeadPhone("");
      setSuccess("New lead registered with automatic AI qualification score!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to register lead.");
    }
  };

  const handleConvertLeadOpportunity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!convertTargetLead) return;
    setError(null);
    setSuccess(null);
    try {
      await api.convertLeadToOpportunity(convertTargetLead.lead_id, {
        title: convertOppTitle.trim() || `Deal for ${convertTargetLead.lead_name}`,
        opportunity_amount: parseFloat(convertOppAmount) || 0,
        sales_stage: "PROSPECTING",
      });
      setConvertTargetLead(null);
      setSuccess("Lead successfully converted to an Opportunity in the sales pipeline!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to convert lead to opportunity.");
    }
  };

  const handleConvertLeadCustomer = async (leadId: string) => {
    setError(null);
    setSuccess(null);
    try {
      const cust = await api.convertLeadToCustomer(leadId);
      setSuccess(`Lead promoted to official Customer profile: ${cust.customer_name} (${cust.customer_code})`);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to convert lead to customer.");
    }
  };

  // Opportunity Actions
  const handleCreateOpportunity = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const oppNum = `OPP-${Math.floor(1000 + Math.random() * 9000)}`;
      await api.createOpportunity({
        opportunity_number: oppNum,
        party_id: oppPartyId,
        party_name: oppPartyName.trim(),
        title: oppTitle.trim(),
        opportunity_from: oppPartyType,
        opportunity_amount: parseFloat(oppAmount) || 0,
        sales_stage: oppStage,
        notes: oppNotes.trim() || undefined,
      });
      setShowOppModal(false);
      setOppTitle("");
      setOppPartyName("");
      setSuccess("Opportunity registered in the sales pipeline!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create opportunity.");
    }
  };

  const handleUpdateStage = async (oppId: string, newStage: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.updateOpportunityStage(oppId, { new_stage: newStage });
      setSuccess(`Opportunity transitioned to stage: ${newStage}`);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to update stage.");
    }
  };

  const handleConvertToQuotation = async (oppId: string) => {
    setError(null);
    setSuccess(null);
    try {
      const res = await api.convertOpportunityToQuotation(oppId, { valid_days: 30 });
      setSuccess(`Sales Quotation ${res.quotation_number} generated from Opportunity!`);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to convert to quotation.");
    }
  };

  // Campaign Actions
  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createCampaign({
        campaign_name: campName.trim(),
        campaign_type: campType,
        budget: parseFloat(campBudget) || 0,
      });
      setShowCampaignModal(false);
      setCampName("");
      setSuccess("Marketing Campaign launched!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create campaign.");
    }
  };

  const handleAddDripStep = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCampaignId) return;
    setError(null);
    setSuccess(null);
    try {
      const camp = campaigns.find((c) => c.campaign_id === selectedCampaignId);
      const stepNum = (camp?.email_steps?.length || 0) + 1;
      await api.addDripStep(selectedCampaignId, {
        sequence_step: stepNum,
        delay_days: parseInt(dripDelay) || 3,
        subject: dripSubject.trim(),
        template_body: dripBody.trim(),
      });
      setShowDripModal(false);
      setDripSubject("");
      setDripBody("");
      setSuccess(`Automated Drip Step #${stepNum} scheduled for campaign!`);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to schedule drip step.");
    }
  };

  const handleCreateContract = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const cust = customers.find((c) => c.customer_id === contractCustomerId);
      const cNum = `CTR-${Math.floor(1000 + Math.random() * 9000)}`;
      await api.createContract({
        contract_number: cNum,
        party_type: "CUSTOMER",
        party_id: contractCustomerId,
        party_name: cust ? cust.customer_name : "Enterprise Client",
        contract_subject: contractSubject.trim(),
        contract_value: parseFloat(contractValue) || 0,
        start_date: contractStartDate,
        end_date: contractEndDate,
      });
      setShowContractModal(false);
      setContractSubject("");
      setSuccess("Service Contract registered and activated!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create contract.");
    }
  };

  // Ticket / Support Actions
  const handleCreateIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createIssue({
        subject: issueSubject.trim(),
        customer_id: issueCustomerId || undefined,
        raised_by_name: issueRaisedName.trim() || "Customer Contact",
        raised_by_email: issueRaisedEmail.trim() || undefined,
        priority: issuePriority,
        issue_type: issueType,
        description: issueDescription.trim(),
      });
      setShowIssueModal(false);
      setIssueSubject("");
      setIssueDescription("");
      setSuccess("Support ticket created with automated SLA deadline tracking!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create ticket.");
    }
  };

  const handleAddCommunication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIssue || !replyMessage.trim()) return;
    setError(null);
    setSuccess(null);
    try {
      await api.addIssueCommunication(selectedIssue.issue_id, {
        sender_type: "AGENT",
        sender_name: "Customer Support Agent",
        message: replyMessage.trim(),
        is_internal_note: isInternalNote,
      });
      setReplyMessage("");
      setIsInternalNote(false);
      setSuccess(isInternalNote ? "Internal staff note recorded." : "Official reply sent to customer!");
      const fresh = await api.getIssue(selectedIssue.issue_id);
      setSelectedIssue(fresh);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to post message.");
    }
  };

  const handleResolveIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIssue) return;
    setError(null);
    setSuccess(null);
    try {
      await api.resolveIssue(selectedIssue.issue_id, {
        resolution_details: resolutionDetails.trim(),
        status: "RESOLVED",
      });
      setShowResolveModal(false);
      setResolutionDetails("");
      setSuccess("Support ticket marked as RESOLVED and SLA closed!");
      const fresh = await api.getIssue(selectedIssue.issue_id);
      setSelectedIssue(fresh);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to resolve ticket.");
    }
  };

  // SLA Actions
  const handleCreateSla = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createSla({
        sla_name: slaName.trim(),
        is_default: slaDefault,
        entity_type: "ALL",
        priorities: [
          { priority: "URGENT", response_time_hours: parseFloat(slaUrgentHours), resolution_time_hours: parseFloat(slaUrgentResHours) },
          { priority: "HIGH", response_time_hours: parseFloat(slaHighHours), resolution_time_hours: parseFloat(slaHighResHours) },
          { priority: "MEDIUM", response_time_hours: parseFloat(slaMedHours), resolution_time_hours: parseFloat(slaMedResHours) },
        ],
      });
      setShowSlaModal(false);
      setSlaName("");
      setSuccess("Service Level Agreement (SLA) policy published!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create SLA.");
    }
  };

  // Warranty Actions
  const handleVerifyWarranty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verifySerialInput.trim()) return;
    setVerifying(true);
    setError(null);
    try {
      const res = await api.verifyWarranty(verifySerialInput.trim());
      setVerificationResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to verify warranty.");
    } finally {
      setVerifying(false);
    }
  };

  const handleCreateWarrantyClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const cNum = `RMA-${Math.floor(1000 + Math.random() * 9000)}`;
      await api.createWarrantyClaim({
        claim_number: cNum,
        serial_number: claimSerial.trim().toUpperCase(),
        customer_id: claimCustomerId || undefined,
        complaint_description: claimComplaint.trim(),
        resolution_type: claimResolutionType,
      });
      setShowClaimModal(false);
      setClaimSerial("");
      setClaimComplaint("");
      setSuccess("Warranty RMA Claim registered and validated against Serial Registry!");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to file warranty claim.");
    }
  };

  const handleResolveClaim = async (claimId: string, resType: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.resolveWarrantyClaim(claimId, {
        resolution_type: resType,
        resolution_notes: "Inspected and processed via RMA Warranty Desk.",
      });
      setSuccess(`Claim marked resolved with disposition: ${resType}`);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to resolve claim.");
    }
  };

  // Helper formatting
  const formatSlaStatus = (status: string) => {
    switch (status) {
      case "WITHIN_SLA":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-emerald-100 text-emerald-800">Within SLA</span>;
      case "RESPONSE_BREACHED":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-rose-100 text-rose-800">Response Breached</span>;
      case "RESOLUTION_BREACHED":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-rose-100 text-rose-800">Resolution Breached</span>;
      case "FULFILLED":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-blue-100 text-blue-800">SLA Fulfilled</span>;
      default:
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-stone-100 text-stone-700">{status}</span>;
    }
  };

  const calculateLeadBreakdown = (lead: any) => {
    if (!lead) return null;
    const annualRev = parseFloat(lead.annual_revenue || 0);
    const empCount = parseInt(lead.no_of_employees || 1);
    const hasEmail = Boolean(lead.email_id && String(lead.email_id).trim().length > 0);
    const hasPhone = Boolean(
      (lead.mobile_no && String(lead.mobile_no).trim().length > 0) ||
      (lead.phone && String(lead.phone).trim().length > 0)
    );
    const industry = lead.industry ? String(lead.industry).trim() : "";
    const source = lead.source ? String(lead.source).trim().toUpperCase() : "WEBSITE";

    // 1. Revenue dimension (max 40 pts)
    let revPts = 0;
    let revTier = "Tier 4: $0 (0 / 40 pts)";
    if (annualRev >= 1000000) {
      revPts = 40;
      revTier = "Tier 1: Enterprise (≥ $1,000,000) → +40.00 pts";
    } else if (annualRev >= 250000) {
      revPts = 25;
      revTier = "Tier 2: Mid-Market (≥ $250,000) → +25.00 pts";
    } else if (annualRev >= 50000) {
      revPts = 15;
      revTier = "Tier 3: Growth SME (≥ $50,000) → +15.00 pts";
    } else if (annualRev > 0) {
      revPts = 5;
      revTier = "Tier 4: Seed / Startup (> $0) → +5.00 pts";
    }

    // 2. Size / Headcount dimension (max 25 pts)
    let sizePts = 0;
    let sizeTier = "Solo / 1 Employee (+5.00 pts)";
    if (empCount >= 50) {
      sizePts = 25;
      sizeTier = "Large Organization (≥ 50 employees) → +25.00 pts";
    } else if (empCount >= 10) {
      sizePts = 15;
      sizeTier = "Medium Team (10–49 employees) → +15.00 pts";
    } else if (empCount >= 2) {
      sizePts = 10;
      sizeTier = "Small Team (2–9 employees) → +10.00 pts";
    } else {
      sizePts = 5;
      sizeTier = "Solo / Seed (1 employee) → +5.00 pts";
    }

    // 3. Contact completeness (max 25 pts)
    const emailPts = hasEmail ? 15 : 0;
    const phonePts = hasPhone ? 10 : 0;
    const contactPts = emailPts + phonePts;

    // 4. Industry & Source intent (max 10 pts)
    const indPts = industry ? 5 : 0;
    const isHighIntent = ["REFERRAL", "CAMPAIGN", "WALK_IN"].includes(source);
    const srcPts = isHighIntent ? 5 : 0;
    const intentPts = indPts + srcPts;

    const totalCalculated = Math.min(100, Math.max(0, revPts + sizePts + contactPts + intentPts));
    const finalScore = parseFloat(lead.qualification_score ?? totalCalculated);
    const qualStatus =
      lead.qualification_status ||
      (finalScore >= 60 ? "QUALIFIED" : finalScore >= 30 ? "IN_PROCESS" : "UNQUALIFIED");

    return {
      annualRev,
      empCount,
      hasEmail,
      hasPhone,
      industry,
      source,
      revPts,
      revTier,
      sizePts,
      sizeTier,
      emailPts,
      phonePts,
      contactPts,
      indPts,
      srcPts,
      intentPts,
      totalCalculated,
      finalScore,
      qualStatus,
    };
  };

  const formatLeadScoreBadge = (score: number, status: string, leadObj?: any) => {
    let color = "bg-stone-100 text-stone-700 border-stone-200 hover:border-stone-300";
    if (status === "QUALIFIED") color = "bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100/70 hover:border-emerald-300";
    else if (status === "IN_REVIEW" || status === "IN_PROCESS") color = "bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100/70 hover:border-amber-300";
    else if (status === "UNQUALIFIED") color = "bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-100/70 hover:border-rose-300";

    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (leadObj) setBreakdownLead(leadObj);
        }}
        title="Click to view full AI qualification factor breakdown"
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-semibold rounded border transition cursor-pointer ${color}`}
      >
        <Sparkles className="w-3 h-3 text-emerald-600" />
        <span>{(score || 0).toFixed(0)}/100</span>
        <span className="text-[10px] font-medium opacity-80">({status})</span>
        <Info className="w-3 h-3 opacity-60 ml-0.5" />
      </button>
    );
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Top Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-stone-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase bg-blue-100 text-blue-800 rounded">
              Phase 6
            </span>
            <h1 className="text-xl font-bold tracking-tight text-stone-900">
              CRM & Support Helpdesk Suite
            </h1>
          </div>
          <p className="text-xs text-stone-500 mt-1">
            ERPNext Parity: Lead Scoring, 1-Click Conversions, Kanban Pipeline, Drip Campaigns, Omnichannel Support, SLAs & Serial RMA
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Alert Banners */}
      {error && (
        <div className="p-3 text-xs bg-red-50 text-red-700 border border-red-200 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs font-bold px-1.5 hover:bg-red-100 rounded">
            ×
          </button>
        </div>
      )}
      {success && (
        <div className="p-3 text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess(null)} className="text-xs font-bold px-1.5 hover:bg-emerald-100 rounded">
            ×
          </button>
        </div>
      )}

      {/* 6-Tab Navigation */}
      <div className="flex overflow-x-auto gap-2 border-b border-stone-200 pb-2 scrollbar-none">
        {[
          { id: "leads", label: "Leads & Qualification", icon: Users, count: leads.length },
          { id: "pipeline", label: "Opportunity Pipeline", icon: Kanban, count: opportunities.length },
          { id: "campaigns", label: "Campaigns & Contracts", icon: Megaphone, count: campaigns.length },
          { id: "tickets", label: "Support Tickets", icon: Headset, count: issues.filter((i) => i.status !== "RESOLVED" && i.status !== "CLOSED").length },
          { id: "slas", label: "SLA Matrices", icon: Sliders, count: slas.length },
          { id: "warranty", label: "Warranty Claims & RMA", icon: Award, count: claims.length },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`inline-flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg transition whitespace-nowrap ${
                active
                  ? "bg-stone-900 text-white shadow-sm"
                  : "bg-white hover:bg-stone-100 text-stone-600 border border-stone-200"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    active ? "bg-stone-700 text-stone-200" : "bg-stone-100 text-stone-600"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* TAB 1: LEADS & AI QUALIFICATION */}
      {activeTab === "leads" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-stone-200 shadow-sm">
            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-72">
                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-stone-400" />
                <input
                  type="text"
                  placeholder="Search leads by name, company, email..."
                  value={leadSearch}
                  onChange={(e) => setLeadSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400"
                />
              </div>
              <select
                value={leadStatusFilter}
                onChange={(e) => setLeadStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-lg text-stone-700"
              >
                <option value="">All Statuses</option>
                <option value="LEAD">Open Lead</option>
                <option value="CONVERTED">Converted</option>
                <option value="LOST">Lost</option>
              </select>
            </div>

            <button
              onClick={() => setShowLeadModal(true)}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm transition"
            >
              <Plus className="w-3.5 h-3.5" />
              New Lead
            </button>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-stone-50 border-b border-stone-200 text-stone-500 font-medium">
                  <th className="py-2.5 px-4">Lead Name / Org</th>
                  <th className="py-2.5 px-4">Contact Info</th>
                  <th className="py-2.5 px-4">Industry & Scale</th>
                  <th className="py-2.5 px-4">AI Score</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 text-right">1-Click Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 text-stone-800">
                {leads.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-stone-400">
                      No leads found. Register a new lead to evaluate AI qualification.
                    </td>
                  </tr>
                ) : (
                  leads.map((l) => (
                    <tr key={l.lead_id} className="hover:bg-stone-50/70 transition">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-stone-900">{l.lead_name}</div>
                        {l.company_name && <div className="text-[11px] text-stone-500">{l.company_name}</div>}
                      </td>
                      <td className="py-3 px-4">
                        <div>{l.email_id || "No email"}</div>
                        <div className="text-[11px] text-stone-500">{l.mobile_no || "No phone"}</div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-medium">{l.industry || "General"}</div>
                        <div className="text-[11px] text-stone-500">
                          {l.no_of_employees || 0} emp · ${(l.annual_revenue || 0).toLocaleString()} rev
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        {formatLeadScoreBadge(l.qualification_score, l.qualification_status, l)}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 text-[11px] font-semibold rounded ${
                            l.status === "CONVERTED"
                              ? "bg-purple-100 text-purple-800"
                              : l.status === "LOST"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-emerald-100 text-emerald-800"
                          }`}
                        >
                          {l.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                        {l.status !== "CONVERTED" && (
                          <>
                            <button
                              onClick={() => {
                                setConvertTargetLead(l);
                                setConvertOppTitle(`Deal: ${l.lead_name}`);
                              }}
                              className="px-2.5 py-1 text-[11px] font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded transition"
                            >
                              → Deal
                            </button>
                            <button
                              onClick={() => handleConvertLeadCustomer(l.lead_id)}
                              className="px-2.5 py-1 text-[11px] font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded transition"
                            >
                              → Customer
                            </button>
                          </>
                        )}
                        {l.status === "CONVERTED" && (
                          <span className="text-[11px] text-stone-400 italic">Converted</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: OPPORTUNITIES & KANBAN PIPELINE */}
      {activeTab === "pipeline" && (
        <div className="space-y-5">
          {pipelineSummary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3.5 bg-white border border-stone-200 rounded-xl shadow-sm">
                <div className="text-[11px] font-medium text-stone-500 uppercase tracking-wider">Active Deals</div>
                <div className="text-xl font-bold text-stone-900 mt-1">{pipelineSummary.total_deals}</div>
              </div>
              <div className="p-3.5 bg-white border border-stone-200 rounded-xl shadow-sm">
                <div className="text-[11px] font-medium text-stone-500 uppercase tracking-wider">Total Pipeline Value</div>
                <div className="text-xl font-bold text-stone-900 mt-1">
                  ${pipelineSummary.total_pipeline_value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>
              </div>
              <div className="p-3.5 bg-white border border-emerald-200 bg-emerald-50/30 rounded-xl shadow-sm">
                <div className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider flex items-center gap-1">
                  <TrendingUp className="w-3.5 h-3.5" /> Weighted Forecast
                </div>
                <div className="text-xl font-bold text-emerald-800 mt-1">
                  ${pipelineSummary.weighted_forecast_value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>
              </div>
              <div className="p-3.5 bg-white border border-stone-200 rounded-xl shadow-sm">
                <div className="text-[11px] font-medium text-stone-500 uppercase tracking-wider">Win Rate</div>
                <div className="text-xl font-bold text-purple-700 mt-1">
                  {pipelineSummary.win_rate_percentage}%
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-stone-200 shadow-sm">
            <div className="relative w-full sm:w-80">
              <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-stone-400" />
              <input
                type="text"
                placeholder="Search deals by title or account..."
                value={oppSearch}
                onChange={(e) => setOppSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400"
              />
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto justify-between sm:justify-end">
              <div className="inline-flex items-center p-0.5 bg-stone-100 border border-stone-200 rounded-lg">
                <button
                  type="button"
                  onClick={() => setOppViewMode("kanban")}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition ${
                    oppViewMode === "kanban"
                      ? "bg-white text-stone-900 shadow-2xs font-semibold"
                      : "text-stone-500 hover:text-stone-800"
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  Kanban Board
                </button>
                <button
                  type="button"
                  onClick={() => setOppViewMode("table")}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition ${
                    oppViewMode === "table"
                      ? "bg-white text-stone-900 shadow-2xs font-semibold"
                      : "text-stone-500 hover:text-stone-800"
                  }`}
                >
                  <List className="w-3.5 h-3.5" />
                  Table View
                </button>
              </div>

              <button
                onClick={() => setShowOppModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition shrink-0"
              >
                <Plus className="w-3.5 h-3.5" />
                New Opportunity
              </button>
            </div>
          </div>

          {oppViewMode === "kanban" ? (
            <div className="flex gap-4 overflow-x-auto pb-6 pt-1 scrollbar-thin">
              {STAGES.map((st) => {
                const stageOpps = opportunities.filter((o) => o.sales_stage === st.id);
                const colValue = stageOpps.reduce(
                  (sum, o) => sum + parseFloat(o.total_amount || o.opportunity_amount || 0),
                  0
                );

                return (
                  <div
                    key={st.id}
                    className="w-80 shrink-0 bg-stone-100/70 border border-stone-200 rounded-xl p-3.5 flex flex-col shadow-2xs"
                  >
                    <div className="flex items-center justify-between border-b border-stone-200 pb-2.5 mb-3">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-xs text-stone-900">{st.label}</span>
                          <span className={`text-[10px] font-semibold px-1.5 py-0.2 rounded border ${st.color}`}>
                            {st.prob}%
                          </span>
                        </div>
                        <div className="text-[11px] text-stone-600 font-mono mt-0.5">
                          ${colValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </div>
                      </div>
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-white border border-stone-200 text-stone-700 shadow-2xs">
                        {stageOpps.length}
                      </span>
                    </div>

                    <div className="space-y-3 flex-1 overflow-y-auto max-h-[calc(100vh-320px)] pr-0.5">
                      {stageOpps.map((opp) => (
                        <div
                          key={opp.opportunity_id}
                          className="bg-white border border-stone-200 hover:border-stone-400 hover:shadow-md transition-all rounded-xl p-3.5 space-y-2.5"
                        >
                          <div className="flex items-start justify-between gap-1">
                            <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-stone-100 text-stone-700">
                              {opp.opportunity_number}
                            </span>
                            <span className="text-[10px] font-semibold text-stone-400 uppercase tracking-wider">
                              {opp.opportunity_from || "ACCOUNT"}
                            </span>
                          </div>

                          <div>
                            <h4 className="font-semibold text-xs text-stone-900 leading-snug line-clamp-2">
                              {opp.title}
                            </h4>
                            <div className="flex items-center gap-1.5 text-[11px] text-stone-500 mt-1">
                              <Building2 className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                              <span className="truncate font-medium">{opp.party_name}</span>
                            </div>
                          </div>

                          <div className="flex items-baseline justify-between pt-1 border-t border-stone-100">
                            <div>
                              <div className="text-[9px] uppercase font-bold text-stone-400 tracking-wider">
                                Deal Value
                              </div>
                              <div className="font-bold text-sm text-stone-900">
                                ${parseFloat(opp.total_amount || opp.opportunity_amount || 0).toLocaleString(
                                  undefined,
                                  { minimumFractionDigits: 2 }
                                )}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-[9px] uppercase font-bold text-stone-400 tracking-wider">
                                Weighted
                              </div>
                              <div className="font-medium text-xs text-emerald-700 font-mono">
                                ${(
                                  parseFloat(opp.total_amount || opp.opportunity_amount || 0) *
                                  (st.prob / 100)
                                ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                              </div>
                            </div>
                          </div>

                          <div className="pt-2 border-t border-stone-100 space-y-2">
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] font-semibold text-stone-500 shrink-0">Stage:</span>
                              <select
                                value={opp.sales_stage}
                                onChange={(e) => handleUpdateStage(opp.opportunity_id, e.target.value)}
                                className="w-full text-[11px] bg-stone-50 hover:bg-stone-100 border border-stone-200 rounded-md px-2 py-1 text-stone-800 font-medium transition cursor-pointer focus:outline-none"
                              >
                                {STAGES.map((s) => (
                                  <option key={s.id} value={s.id}>
                                    {s.label} ({s.prob}%)
                                  </option>
                                ))}
                              </select>
                            </div>

                            {opp.sales_stage !== "CLOSED_LOST" && (
                              <button
                                onClick={() => handleConvertToQuotation(opp.opportunity_id)}
                                className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-2xs transition cursor-pointer"
                              >
                                <FileText className="w-3.5 h-3.5" />
                                <span>Generate Sales Quotation →</span>
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                      {stageOpps.length === 0 && (
                        <div className="h-28 flex flex-col items-center justify-center text-xs text-stone-400 border border-dashed border-stone-200 rounded-xl bg-white/40">
                          <span>No deals in this stage</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden shadow-sm">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200 text-stone-500 font-medium">
                    <th className="py-2.5 px-4">Deal ID</th>
                    <th className="py-2.5 px-4">Opportunity Title</th>
                    <th className="py-2.5 px-4">Account / Customer</th>
                    <th className="py-2.5 px-4">Deal Amount</th>
                    <th className="py-2.5 px-4">Stage</th>
                    <th className="py-2.5 px-4">Win Prob & Forecast</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 text-stone-800">
                  {opportunities.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-stone-400">
                        No opportunities found. Click "New Opportunity" or convert a lead to create a deal.
                      </td>
                    </tr>
                  ) : (
                    opportunities.map((opp) => {
                      const st = STAGES.find((s) => s.id === opp.sales_stage) || STAGES[0];
                      const val = parseFloat(opp.total_amount || opp.opportunity_amount || 0);
                      const weighted = val * (st.prob / 100);

                      return (
                        <tr key={opp.opportunity_id} className="hover:bg-stone-50/70 transition">
                          <td className="py-3 px-4 font-mono font-semibold text-stone-900">
                            {opp.opportunity_number}
                          </td>
                          <td className="py-3 px-4">
                            <div className="font-semibold text-stone-900">{opp.title}</div>
                            {opp.notes && <div className="text-[11px] text-stone-400 truncate max-w-xs">{opp.notes}</div>}
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-1.5 font-medium">
                              <Building2 className="w-3.5 h-3.5 text-stone-400" />
                              <span>{opp.party_name}</span>
                            </div>
                            <span className="text-[10px] text-stone-400">{opp.opportunity_from || "ACCOUNT"}</span>
                          </td>
                          <td className="py-3 px-4 font-bold text-stone-900">
                            ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-4">
                            <select
                              value={opp.sales_stage}
                              onChange={(e) => handleUpdateStage(opp.opportunity_id, e.target.value)}
                              className="text-xs bg-stone-50 border border-stone-200 rounded-md px-2 py-1 text-stone-800 font-medium cursor-pointer"
                            >
                              {STAGES.map((s) => (
                                <option key={s.id} value={s.id}>
                                  {s.label} ({s.prob}%)
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-1.5">
                              <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded border ${st.color}`}>
                                {st.prob}%
                              </span>
                              <span className="font-mono text-emerald-700 font-medium text-[11px]">
                                ${weighted.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right">
                            {opp.sales_stage !== "CLOSED_LOST" ? (
                              <button
                                onClick={() => handleConvertToQuotation(opp.opportunity_id)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-md transition cursor-pointer"
                              >
                                <FileText className="w-3.5 h-3.5" />
                                Quote →
                              </button>
                            ) : (
                              <span className="text-[11px] text-rose-500 font-medium">Closed Lost</span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: MARKETING CAMPAIGNS & DRIP SEQUENCES */}
      {activeTab === "campaigns" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between bg-white p-3 rounded-xl border border-stone-200 shadow-sm">
            <div>
              <h2 className="text-sm font-bold text-stone-900">Marketing Campaigns & Automated Drip Sequences</h2>
              <p className="text-xs text-stone-500">Automate customer outreach and manage commercial service contracts.</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowCampaignModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition"
              >
                <Plus className="w-3.5 h-3.5" />
                New Campaign
              </button>
              <button
                onClick={() => setShowContractModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm transition"
              >
                <Plus className="w-3.5 h-3.5" />
                New Service Contract
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-stone-100 pb-2">
                <span className="font-bold text-xs uppercase tracking-wider text-stone-700">Active Campaigns</span>
                <span className="text-xs text-stone-400">{campaigns.length} Total</span>
              </div>
              <div className="space-y-2">
                {campaigns.map((c) => (
                  <div
                    key={c.campaign_id}
                    onClick={() => setSelectedCampaignId(c.campaign_id)}
                    className={`p-3 rounded-lg border cursor-pointer transition ${
                      selectedCampaignId === c.campaign_id
                        ? "border-stone-900 bg-stone-50"
                        : "border-stone-200 hover:bg-stone-50/50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-xs text-stone-900">{c.campaign_name}</div>
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-blue-50 text-blue-700">
                        {c.campaign_type}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-stone-500 mt-2">
                      <span>Budget: ${(c.budget || 0).toLocaleString()}</span>
                      <span className="text-stone-700 font-medium">
                        {c.email_steps?.length || 0} Drip Steps Scheduled
                      </span>
                    </div>
                  </div>
                ))}
                {campaigns.length === 0 && (
                  <div className="py-6 text-center text-xs text-stone-400">No campaigns launched yet.</div>
                )}
              </div>
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-stone-100 pb-2">
                <span className="font-bold text-xs uppercase tracking-wider text-stone-700">
                  Drip Workflow Steps
                </span>
                {selectedCampaignId && (
                  <button
                    onClick={() => setShowDripModal(true)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-stone-900 hover:underline"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Step
                  </button>
                )}
              </div>

              {selectedCampaignId ? (
                (() => {
                  const camp = campaigns.find((c) => c.campaign_id === selectedCampaignId);
                  const steps = camp?.email_steps || [];
                  return (
                    <div className="space-y-3">
                      <div className="text-xs font-medium text-stone-800">
                        Campaign: <span className="font-bold">{camp?.campaign_name}</span>
                      </div>
                      {steps.length === 0 ? (
                        <div className="py-6 text-center text-xs text-stone-400 border border-dashed border-stone-200 rounded-lg">
                          No drip steps configured. Click Add Step to build an automated sequence.
                        </div>
                      ) : (
                        steps
                          .sort((a: any, b: any) => a.sequence_step - b.sequence_step)
                          .map((st: any) => (
                            <div key={st.email_campaign_id} className="p-2.5 bg-stone-50 border border-stone-200 rounded-lg text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-stone-900">Step #{st.sequence_step}</span>
                                <span className="text-[10px] bg-stone-200 text-stone-700 px-1.5 py-0.5 rounded font-mono">
                                  +{st.delay_days} days delay
                                </span>
                              </div>
                              <div className="font-medium text-stone-800">{st.subject}</div>
                              <div className="text-[11px] text-stone-500 line-clamp-2">{st.template_body}</div>
                            </div>
                          ))
                      )}
                    </div>
                  );
                })()
              ) : (
                <div className="py-8 text-center text-xs text-stone-400">
                  Select a campaign on the left to inspect or configure its automated drip sequence.
                </div>
              )}
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <span className="font-bold text-xs uppercase tracking-wider text-stone-700">Service Contracts Master</span>
              <span className="text-xs text-stone-400">{contracts.length} Active Contracts</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200 text-stone-500 font-medium">
                    <th className="py-2 px-3">Contract #</th>
                    <th className="py-2 px-3">Party / Client</th>
                    <th className="py-2 px-3">Subject</th>
                    <th className="py-2 px-3">Contract Value</th>
                    <th className="py-2 px-3">Validity Period</th>
                    <th className="py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 text-stone-800">
                  {contracts.map((ctr) => (
                    <tr key={ctr.contract_id} className="hover:bg-stone-50/50">
                      <td className="py-2.5 px-3 font-mono font-semibold">{ctr.contract_number}</td>
                      <td className="py-2.5 px-3 font-medium">{ctr.party_name}</td>
                      <td className="py-2.5 px-3">{ctr.contract_subject}</td>
                      <td className="py-2.5 px-3 font-bold">${(ctr.contract_value || 0).toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-stone-500 text-[11px]">
                        {ctr.start_date} → {ctr.end_date || "Ongoing"}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800">
                          {ctr.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {contracts.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-stone-400">
                        No service contracts recorded.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: SUPPORT HELPDESK & TICKET CONSOLE */}
      {activeTab === "tickets" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-xl border border-stone-200 shadow-sm">
            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-72">
                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-stone-400" />
                <input
                  type="text"
                  placeholder="Search tickets by subject, requester, ID..."
                  value={issueSearch}
                  onChange={(e) => setIssueSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400"
                />
              </div>
              <select
                value={issuePriorityFilter}
                onChange={(e) => setIssuePriorityFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-lg text-stone-700"
              >
                <option value="">All Priorities</option>
                <option value="URGENT">Urgent</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            <button
              onClick={() => setShowIssueModal(true)}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition"
            >
              <Plus className="w-3.5 h-3.5" />
              New Ticket
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-7 bg-white border border-stone-200 rounded-xl overflow-hidden shadow-sm">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200 text-stone-500 font-medium">
                    <th className="py-2.5 px-3">Ticket #</th>
                    <th className="py-2.5 px-3">Subject & Requester</th>
                    <th className="py-2.5 px-3">Priority</th>
                    <th className="py-2.5 px-3">SLA Status</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 text-stone-800">
                  {issues.map((iss) => {
                    const isSelected = selectedIssue?.issue_id === iss.issue_id;
                    return (
                      <tr
                        key={iss.issue_id}
                        onClick={async () => {
                          const detailed = await api.getIssue(iss.issue_id);
                          setSelectedIssue(detailed);
                        }}
                        className={`cursor-pointer transition ${
                          isSelected ? "bg-stone-100 font-medium" : "hover:bg-stone-50/60"
                        }`}
                      >
                        <td className="py-2.5 px-3 font-mono font-bold text-stone-900">{iss.issue_number}</td>
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-stone-900 line-clamp-1">{iss.subject}</div>
                          <div className="text-[11px] text-stone-500">{iss.raised_by_name}</div>
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${
                              iss.priority === "URGENT"
                                ? "bg-rose-100 text-rose-800"
                                : iss.priority === "HIGH"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-stone-100 text-stone-700"
                            }`}
                          >
                            {iss.priority}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">{formatSlaStatus(iss.sla_status)}</td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-stone-200 text-stone-800">
                            {iss.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                  {issues.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-stone-400">
                        No support tickets found. Create a ticket to test omnichannel routing.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="lg:col-span-5 bg-white border border-stone-200 rounded-xl p-4 shadow-sm flex flex-col justify-between min-h-[480px]">
              {selectedIssue ? (
                <div className="flex flex-col h-full justify-between space-y-3">
                  <div className="border-b border-stone-200 pb-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-stone-500">{selectedIssue.issue_number}</span>
                      <div className="flex items-center gap-1.5">
                        {formatSlaStatus(selectedIssue.sla_status)}
                        {selectedIssue.status !== "RESOLVED" && selectedIssue.status !== "CLOSED" && (
                          <button
                            onClick={() => setShowResolveModal(true)}
                            className="px-2 py-0.5 text-[11px] font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded transition"
                          >
                            Resolve Ticket
                          </button>
                        )}
                      </div>
                    </div>
                    <h3 className="font-bold text-sm text-stone-900 mt-1">{selectedIssue.subject}</h3>
                    <div className="text-xs text-stone-500 mt-1 flex flex-wrap gap-2">
                      <span>By: {selectedIssue.raised_by_name}</span>
                      {selectedIssue.customer && <span>· Org: {selectedIssue.customer.customer_name}</span>}
                    </div>

                    <div className="mt-2.5 p-2 bg-stone-50 border border-stone-200 rounded-lg text-[11px] grid grid-cols-2 gap-2 text-stone-600">
                      <div>
                        <span className="font-medium text-stone-800">Response Deadline:</span>{" "}
                        {selectedIssue.response_by ? new Date(selectedIssue.response_by).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "N/A"}
                      </div>
                      <div>
                        <span className="font-medium text-stone-800">Resolution Deadline:</span>{" "}
                        {selectedIssue.resolution_by ? new Date(selectedIssue.resolution_by).toLocaleDateString() : "N/A"}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2.5 overflow-y-auto max-h-[260px] pr-1 scrollbar-none flex-1">
                    {selectedIssue.communications?.map((comm: any) => {
                      const isInternal = comm.is_internal_note;
                      const isCustomer = comm.sender_type === "CUSTOMER";
                      return (
                        <div
                          key={comm.communication_id}
                          className={`p-2.5 rounded-lg text-xs space-y-1 ${
                            isInternal
                              ? "bg-amber-50/80 border border-amber-200"
                              : isCustomer
                              ? "bg-stone-50 border border-stone-200"
                              : "bg-blue-50/70 border border-blue-200 ml-4"
                          }`}
                        >
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-bold text-stone-800">
                              {comm.sender_name}{" "}
                              {isInternal && (
                                <span className="text-[10px] text-amber-800 font-semibold bg-amber-100 px-1 rounded">
                                  Internal Note
                                </span>
                              )}
                            </span>
                            <span className="text-stone-400 text-[10px]">
                              {comm.created_at ? new Date(comm.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ""}
                            </span>
                          </div>
                          <div className="text-stone-700 text-xs whitespace-pre-wrap">{comm.message}</div>
                        </div>
                      );
                    })}
                  </div>

                  <form onSubmit={handleAddCommunication} className="border-t border-stone-200 pt-3 space-y-2">
                    <textarea
                      placeholder="Write an official customer reply or private staff note..."
                      rows={2}
                      value={replyMessage}
                      onChange={(e) => setReplyMessage(e.target.value)}
                      className="w-full text-xs p-2 bg-stone-50 border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400"
                    />
                    <div className="flex items-center justify-between">
                      <label className="flex items-center gap-1.5 text-xs text-stone-600 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isInternalNote}
                          onChange={(e) => setIsInternalNote(e.target.checked)}
                          className="rounded text-amber-600"
                        />
                        <span>Private Staff Note (hidden from client)</span>
                      </label>
                      <button
                        type="submit"
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition"
                      >
                        <Send className="w-3 h-3" /> Send
                      </button>
                    </div>
                  </form>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center text-stone-400 text-xs py-16">
                  <MessageSquare className="w-8 h-8 mb-2 stroke-[1.5]" />
                  <span>Select any support ticket on the left to inspect its threaded communications.</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: SERVICE LEVEL AGREEMENTS (SLA) */}
      {activeTab === "slas" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between bg-white p-3 rounded-xl border border-stone-200 shadow-sm">
            <div>
              <h2 className="text-sm font-bold text-stone-900">Service Level Agreement (SLA) Matrix</h2>
              <p className="text-xs text-stone-500">Configure response and resolution thresholds per priority tier.</p>
            </div>
            <button
              onClick={() => setShowSlaModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition"
            >
              <Plus className="w-3.5 h-3.5" />
              New SLA Policy
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {slas.map((s) => (
              <div key={s.sla_id} className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-3">
                <div className="flex items-center justify-between border-b border-stone-100 pb-2">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    <span className="font-bold text-xs text-stone-900">{s.sla_name}</span>
                  </div>
                  {s.is_default && (
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800">
                      Global Default
                    </span>
                  )}
                </div>

                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="text-stone-400 font-medium text-[11px]">
                      <th className="pb-1.5">Priority</th>
                      <th className="pb-1.5">Max First Response</th>
                      <th className="pb-1.5">Max Resolution</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 text-stone-700">
                    {s.priorities?.map((pr: any) => (
                      <tr key={pr.priority_id}>
                        <td className="py-1.5 font-semibold">{pr.priority}</td>
                        <td className="py-1.5">{pr.response_time_hours} hrs</td>
                        <td className="py-1.5 font-medium">{pr.resolution_time_hours} hrs</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 6: WARRANTY CLAIMS & SERIAL RMA */}
      {activeTab === "warranty" && (
        <div className="space-y-6">
          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-3">
            <div>
              <h2 className="text-sm font-bold text-stone-900 flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-stone-700" />
                Live Serial Number Warranty Entitlement Validator
              </h2>
              <p className="text-xs text-stone-500">
                Direct cross-phase entitlement verification against Phase 3 Inventory Serial Registry.
              </p>
            </div>

            <form onSubmit={handleVerifyWarranty} className="flex gap-2 max-w-xl">
              <input
                type="text"
                placeholder="Enter Serial Number (e.g. SN-AERO-XXXXXX)..."
                value={verifySerialInput}
                onChange={(e) => setVerifySerialInput(e.target.value)}
                className="flex-1 px-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400 font-mono"
              />
              <button
                type="submit"
                disabled={verifying}
                className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition"
              >
                {verifying ? "Checking..." : "Verify Entitlement"}
              </button>
            </form>

            {verificationResult && (
              <div
                className={`p-3 rounded-lg border text-xs space-y-1 mt-2 ${
                  verificationResult.warranty_status === "IN_WARRANTY"
                    ? "bg-emerald-50/70 border-emerald-200 text-emerald-900"
                    : verificationResult.warranty_status === "OUT_OF_WARRANTY"
                    ? "bg-amber-50/70 border-amber-200 text-amber-900"
                    : "bg-stone-50 border-stone-200 text-stone-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold">
                    Status: {verificationResult.warranty_status}
                  </span>
                  <span className="font-mono text-[11px]">{verificationResult.serial_number}</span>
                </div>
                <div>{verificationResult.details}</div>
                {verificationResult.item_code && (
                  <div className="text-[11px] opacity-80">
                    Product: {verificationResult.item_name} ({verificationResult.item_code})
                  </div>
                )}
                {verificationResult.warranty_expiry_date && (
                  <div className="text-[11px] opacity-80">
                    Coverage Expiry Date: {verificationResult.warranty_expiry_date}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <span className="font-bold text-xs uppercase tracking-wider text-stone-700">RMA Warranty Claims</span>
                <p className="text-xs text-stone-400">{claims.length} Total Claims Filed</p>
              </div>
              <button
                onClick={() => setShowClaimModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition"
              >
                <Plus className="w-3.5 h-3.5" />
                File Warranty Claim
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200 text-stone-500 font-medium">
                    <th className="py-2.5 px-3">RMA #</th>
                    <th className="py-2.5 px-3">Serial No</th>
                    <th className="py-2.5 px-3">Customer</th>
                    <th className="py-2.5 px-3">Complaint</th>
                    <th className="py-2.5 px-3">Entitlement</th>
                    <th className="py-2.5 px-3">Disposition</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 text-stone-800">
                  {claims.map((cl) => (
                    <tr key={cl.claim_id} className="hover:bg-stone-50/50">
                      <td className="py-2.5 px-3 font-mono font-bold text-stone-900">{cl.claim_number}</td>
                      <td className="py-2.5 px-3 font-mono">{cl.serial_number}</td>
                      <td className="py-2.5 px-3 font-medium">{cl.customer?.customer_name || "N/A"}</td>
                      <td className="py-2.5 px-3 max-w-xs truncate">{cl.complaint_description}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${
                            cl.warranty_status === "IN_WARRANTY"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {cl.warranty_status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px]">{cl.resolution_type}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-stone-100 text-stone-700">
                          {cl.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        {cl.status === "OPEN" ? (
                          <button
                            onClick={() => handleResolveClaim(cl.claim_id, cl.resolution_type)}
                            className="px-2 py-1 text-[11px] font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded transition"
                          >
                            Close RMA
                          </button>
                        ) : (
                          <span className="text-[11px] text-stone-400 italic">Resolved</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {claims.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-stone-400">
                        No warranty claims filed. Click File Warranty Claim to test RMA processing.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* MODALS */}

      {/* Modal: AI Score Factor Breakdown Inspector */}
      {breakdownLead && (() => {
        const b = calculateLeadBreakdown(breakdownLead);
        if (!b) return null;

        return (
          <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl shadow-2xl border border-stone-200 max-w-xl w-full p-6 space-y-5 max-h-[90vh] overflow-y-auto">
              {/* Header */}
              <div className="flex items-start justify-between border-b border-stone-100 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 text-[11px] font-bold">
                      <Sparkles className="w-3.5 h-3.5 text-emerald-700" /> AI Qualification Engine
                    </span>
                    <span className="text-[11px] text-stone-400 font-mono">BANT / ICP Rubric</span>
                  </div>
                  <h3 className="text-lg font-bold text-stone-900 mt-1">
                    {breakdownLead.lead_name}
                  </h3>
                  <div className="flex items-center gap-2 text-xs text-stone-500 mt-0.5">
                    {breakdownLead.company_name && (
                      <span className="font-medium text-stone-700">{breakdownLead.company_name}</span>
                    )}
                    <span>·</span>
                    <span>{breakdownLead.industry || "General Industry"}</span>
                    <span>·</span>
                    <span>Source: {breakdownLead.source || "WEBSITE"}</span>
                  </div>
                </div>
                <button
                  onClick={() => setBreakdownLead(null)}
                  className="text-stone-400 hover:text-stone-600 p-1 rounded-lg hover:bg-stone-100 transition cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Score Hero */}
              <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="text-[11px] font-bold text-stone-500 uppercase tracking-wider">
                    Total Qualification Score
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-extrabold text-stone-900">
                      {b.finalScore.toFixed(0)}
                    </span>
                    <span className="text-stone-400 font-semibold text-base">/ 100</span>
                    <span
                      className={`ml-2 px-2.5 py-0.5 text-xs font-bold rounded-full ${
                        b.qualStatus === "QUALIFIED"
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                          : b.qualStatus === "IN_PROCESS"
                          ? "bg-amber-100 text-amber-800 border border-amber-300"
                          : "bg-rose-100 text-rose-800 border border-rose-300"
                      }`}
                    >
                      {b.qualStatus}
                    </span>
                  </div>
                  <p className="text-xs text-stone-500">
                    Threshold: ≥ 60.00 pts is QUALIFIED, 30–59 is IN PROCESS, &lt; 30 is UNQUALIFIED.
                  </p>
                </div>

                <div className="sm:text-right space-y-1 bg-white sm:bg-transparent p-3 sm:p-0 rounded-lg border sm:border-0 border-stone-200">
                  <div className="text-[11px] text-stone-500">Scoring Engine</div>
                  <div className="text-xs font-bold text-emerald-700 flex items-center sm:justify-end gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Deterministic ICP Fit
                  </div>
                  <div className="text-[11px] text-stone-400">Python Domain Service (BANT)</div>
                </div>
              </div>

              {/* 4 Factor Dimensions */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
                  4-Factor Evaluation Breakdown
                </h4>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Factor 1: Revenue */}
                  <div className="bg-white border border-stone-200 rounded-xl p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-stone-800">1. Economic Scale</span>
                      <span className="font-bold text-xs text-stone-900">
                        +{b.revPts} / 40 pts
                      </span>
                    </div>
                    <div className="w-full bg-stone-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-emerald-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${(b.revPts / 40) * 100}%` }}
                      />
                    </div>
                    <div className="text-[11px] text-stone-600">
                      Declared: <span className="font-medium text-stone-900">${b.annualRev.toLocaleString()}</span>
                    </div>
                    <div className="text-[10px] text-stone-400">{b.revTier}</div>
                  </div>

                  {/* Factor 2: Size */}
                  <div className="bg-white border border-stone-200 rounded-xl p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-stone-800">2. Headcount & Size</span>
                      <span className="font-bold text-xs text-stone-900">
                        +{b.sizePts} / 25 pts
                      </span>
                    </div>
                    <div className="w-full bg-stone-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-emerald-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${(b.sizePts / 25) * 100}%` }}
                      />
                    </div>
                    <div className="text-[11px] text-stone-600">
                      Team: <span className="font-medium text-stone-900">{b.empCount} employees</span>
                    </div>
                    <div className="text-[10px] text-stone-400">{b.sizeTier}</div>
                  </div>

                  {/* Factor 3: Contact */}
                  <div className="bg-white border border-stone-200 rounded-xl p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-stone-800">3. Direct Reachability</span>
                      <span className="font-bold text-xs text-stone-900">
                        +{b.contactPts} / 25 pts
                      </span>
                    </div>
                    <div className="w-full bg-stone-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-emerald-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${(b.contactPts / 25) * 100}%` }}
                      />
                    </div>
                    <div className="space-y-0.5 text-[11px]">
                      <div className="flex items-center justify-between text-stone-600">
                        <span>Email ({breakdownLead.email_id || "None"}):</span>
                        <span className="font-semibold text-stone-900">+{b.emailPts} pts</span>
                      </div>
                      <div className="flex items-center justify-between text-stone-600">
                        <span>Phone ({breakdownLead.mobile_no || breakdownLead.phone || "None"}):</span>
                        <span className="font-semibold text-stone-900">+{b.phonePts} pts</span>
                      </div>
                    </div>
                  </div>

                  {/* Factor 4: Industry & Source */}
                  <div className="bg-white border border-stone-200 rounded-xl p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-stone-800">4. Sector & Inbound Channel</span>
                      <span className="font-bold text-xs text-stone-900">
                        +{b.intentPts} / 10 pts
                      </span>
                    </div>
                    <div className="w-full bg-stone-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-emerald-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${(b.intentPts / 10) * 100}%` }}
                      />
                    </div>
                    <div className="space-y-0.5 text-[11px]">
                      <div className="flex items-center justify-between text-stone-600">
                        <span>Industry ({b.industry || "General"}):</span>
                        <span className="font-semibold text-stone-900">+{b.indPts} pts</span>
                      </div>
                      <div className="flex items-center justify-between text-stone-600">
                        <span>Channel ({b.source}):</span>
                        <span className="font-semibold text-stone-900">+{b.srcPts} pts</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Formula & Calculation Box */}
              <div className="bg-stone-50 border border-stone-200 rounded-xl p-3.5 text-xs text-stone-700 space-y-1.5">
                <div className="font-semibold text-stone-900 flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5 text-blue-600" />
                  Exact Point Derivation Formula:
                </div>
                <div className="font-mono text-xs bg-white p-2 rounded border border-stone-200 text-stone-800 overflow-x-auto">
                  {b.revPts} (Revenue) + {b.sizePts} (Size) + {b.emailPts} (Email) + {b.phonePts} (Phone) + {b.indPts} (Industry) + {b.srcPts} (Source) = {b.totalCalculated} / 100 pts
                </div>
                <p className="text-[11px] text-stone-500">
                  Calculated deterministically in <code>LeadService.calculate_qualification_score</code> at lead creation.
                </p>
              </div>

              {/* AI Recommendation */}
              <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-2.5 text-xs text-emerald-900">
                <Sparkles className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">AI Advisory Action: </span>
                  {b.qualStatus === "QUALIFIED"
                    ? "High ICP compatibility confirmed. Profile completeness is high and economic scale is sufficient for immediate conversion to Opportunity Deal."
                    : b.qualStatus === "IN_PROCESS"
                    ? "Moderate ICP fit. Recommend initiating an automated email drip sequence or scheduling a qualification discovery call."
                    : "Low ICP fit. Additional firmographic details or direct contact points required before engaging sales reps."}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-between pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setBreakdownLead(null)}
                  className="px-3.5 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-100 rounded-lg transition cursor-pointer"
                >
                  Close
                </button>
                <div className="flex items-center gap-2">
                  {breakdownLead.status !== "CONVERTED" && (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          const l = breakdownLead;
                          setBreakdownLead(null);
                          setConvertTargetLead(l);
                          setConvertOppTitle(`Deal: ${l.lead_name}`);
                        }}
                        className="px-3.5 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition cursor-pointer"
                      >
                        Convert to Opportunity Deal →
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const lid = breakdownLead.lead_id;
                          setBreakdownLead(null);
                          handleConvertLeadCustomer(lid);
                        }}
                        className="px-3.5 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm transition cursor-pointer"
                      >
                        Promote to Customer
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Modal: New Lead */}
      {showLeadModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-lg w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">Register New Lead</h3>
              <button onClick={() => setShowLeadModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-lg text-emerald-900 flex items-start gap-2.5 text-xs leading-relaxed">
              <Sparkles className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-emerald-950">Dynamic AI Lead Qualification:</span> Evaluates Annual Revenue (max 40 pts), Team Size (max 25 pts), Contact Reachability (max 25 pts), and Source/Industry Fit (max 10 pts). Scores ≥ 60 auto-qualify for sales pipeline.
              </div>
            </div>
            <form onSubmit={handleCreateLead} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Lead Full Name *</label>
                  <input
                    type="text"
                    required
                    value={leadName}
                    onChange={(e) => setLeadName(e.target.value)}
                    placeholder="e.g. John Doe"
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Company Name</label>
                  <input
                    type="text"
                    value={leadCompany}
                    onChange={(e) => setLeadCompany(e.target.value)}
                    placeholder="e.g. Acme Corp"
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Email Address</label>
                  <input
                    type="email"
                    value={leadEmail}
                    onChange={(e) => setLeadEmail(e.target.value)}
                    placeholder="john@acme.example"
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Phone Number</label>
                  <input
                    type="text"
                    value={leadPhone}
                    onChange={(e) => setLeadPhone(e.target.value)}
                    placeholder="+1-555-0192"
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Annual Revenue ($)</label>
                  <input
                    type="number"
                    value={leadRevenue}
                    onChange={(e) => setLeadRevenue(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Employees</label>
                  <input
                    type="number"
                    value={leadEmployees}
                    onChange={(e) => setLeadEmployees(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Industry</label>
                  <select
                    value={leadIndustry}
                    onChange={(e) => setLeadIndustry(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    <option value="Manufacturing">Manufacturing</option>
                    <option value="Aerospace">Aerospace</option>
                    <option value="Energy">Energy</option>
                    <option value="Technology">Technology</option>
                    <option value="Retail">Retail</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-stone-600 mb-1 font-medium">Lead Notes / Requirements</label>
                <textarea
                  rows={2}
                  value={leadNotes}
                  onChange={(e) => setLeadNotes(e.target.value)}
                  placeholder="Key purchasing intentions or timeline notes..."
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowLeadModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm"
                >
                  Create & Qualify Lead
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Convert Lead to Opportunity */}
      {convertTargetLead && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">1-Click Opportunity Conversion</h3>
              <button onClick={() => setConvertTargetLead(null)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleConvertLeadOpportunity} className="space-y-3 text-xs">
              <p className="text-stone-500">
                Converting lead <span className="font-bold text-stone-800">{convertTargetLead.lead_name}</span> into a
                pipeline deal.
              </p>
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Deal Title *</label>
                <input
                  type="text"
                  required
                  value={convertOppTitle}
                  onChange={(e) => setConvertOppTitle(e.target.value)}
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Estimated Deal Value ($) *</label>
                <input
                  type="number"
                  required
                  value={convertOppAmount}
                  onChange={(e) => setConvertOppAmount(e.target.value)}
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setConvertTargetLead(null)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  Confirm Conversion
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Opportunity */}
      {showOppModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-lg w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">Create Pipeline Deal</h3>
              <button onClick={() => setShowOppModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateOpportunity} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Deal Title *</label>
                <input
                  type="text"
                  required
                  value={oppTitle}
                  onChange={(e) => setOppTitle(e.target.value)}
                  placeholder="e.g. Q4 Supply Framework Contract"
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Customer / Account *</label>
                  <select
                    required
                    value={oppPartyId}
                    onChange={(e) => {
                      setOppPartyId(e.target.value);
                      const c = customers.find((x) => x.customer_id === e.target.value);
                      if (c) setOppPartyName(c.customer_name);
                    }}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    <option value="">Select Customer...</option>
                    {customers.map((c) => (
                      <option key={c.customer_id} value={c.customer_id}>
                        {c.customer_name} ({c.customer_code})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Initial Sales Stage</label>
                  <select
                    value={oppStage}
                    onChange={(e) => setOppStage(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    {STAGES.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label} ({s.prob}%)
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-stone-600 mb-1 font-medium">Total Amount ($) *</label>
                <input
                  type="number"
                  required
                  value={oppAmount}
                  onChange={(e) => setOppAmount(e.target.value)}
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-stone-600 mb-1 font-medium">Deal Notes</label>
                <textarea
                  rows={2}
                  value={oppNotes}
                  onChange={(e) => setOppNotes(e.target.value)}
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowOppModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  Save Opportunity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Campaign */}
      {showCampaignModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">Launch Marketing Campaign</h3>
              <button onClick={() => setShowCampaignModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateCampaign} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Campaign Name *</label>
                <input
                  type="text"
                  required
                  value={campName}
                  onChange={(e) => setCampName(e.target.value)}
                  placeholder="e.g. Q4 Precision Aerospace Outreach"
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Campaign Type</label>
                  <select
                    value={campType}
                    onChange={(e) => setCampType(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    <option value="EMAIL">Email Drip</option>
                    <option value="WEBINAR">Webinar</option>
                    <option value="CONFERENCE">Industry Conference</option>
                    <option value="DIRECT">Direct Mail</option>
                  </select>
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Budget ($)</label>
                  <input
                    type="number"
                    value={campBudget}
                    onChange={(e) => setCampBudget(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowCampaignModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  Launch Campaign
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add Drip Step */}
      {showDripModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">Add Automated Drip Sequence Step</h3>
              <button onClick={() => setShowDripModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleAddDripStep} className="space-y-3 text-xs">
              <div className="grid grid-cols-3 gap-2.5">
                <div className="col-span-2">
                  <label className="block text-stone-600 mb-1 font-medium">Email Subject Line *</label>
                  <input
                    type="text"
                    required
                    value={dripSubject}
                    onChange={(e) => setDripSubject(e.target.value)}
                    placeholder="e.g. Introducing next-gen CNC alloy..."
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Delay (Days) *</label>
                  <input
                    type="number"
                    required
                    value={dripDelay}
                    onChange={(e) => setDripDelay(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
              </div>
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Template Body *</label>
                <textarea
                  rows={4}
                  required
                  value={dripBody}
                  onChange={(e) => setDripBody(e.target.value)}
                  placeholder="Hello {{first_name}}, following up on your engineering query..."
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowDripModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  Add Sequence Step
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Contract */}
      {showContractModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">New Commercial Service Contract</h3>
              <button onClick={() => setShowContractModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateContract} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Contract Subject *</label>
                <input
                  type="text"
                  required
                  value={contractSubject}
                  onChange={(e) => setContractSubject(e.target.value)}
                  placeholder="e.g. Annual Machinery Maintenance & QC SLA"
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Client / Customer *</label>
                  <select
                    required
                    value={contractCustomerId}
                    onChange={(e) => setContractCustomerId(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    <option value="">Select Client...</option>
                    {customers.map((c) => (
                      <option key={c.customer_id} value={c.customer_id}>
                        {c.customer_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Contract Value ($)</label>
                  <input
                    type="number"
                    value={contractValue}
                    onChange={(e) => setContractValue(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Start Date</label>
                  <input
                    type="date"
                    value={contractStartDate}
                    onChange={(e) => setContractStartDate(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">End Date</label>
                  <input
                    type="date"
                    value={contractEndDate}
                    onChange={(e) => setContractEndDate(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowContractModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm"
                >
                  Activate Contract
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Support Ticket */}
      {showIssueModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-lg w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">Create Support Ticket</h3>
              <button onClick={() => setShowIssueModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateIssue} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Subject / Incident Summary *</label>
                <input
                  type="text"
                  required
                  value={issueSubject}
                  onChange={(e) => setIssueSubject(e.target.value)}
                  placeholder="e.g. Hydraulic actuator seal leak during startup"
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Associated Customer</label>
                  <select
                    value={issueCustomerId}
                    onChange={(e) => setIssueCustomerId(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    <option value="">Guest / General Client</option>
                    {customers.map((c) => (
                      <option key={c.customer_id} value={c.customer_id}>
                        {c.customer_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Requester Name *</label>
                  <input
                    type="text"
                    required
                    value={issueRaisedName}
                    onChange={(e) => setIssueRaisedName(e.target.value)}
                    placeholder="e.g. Chief Engineer Mike"
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Requester Email</label>
                  <input
                    type="email"
                    value={issueRaisedEmail}
                    onChange={(e) => setIssueRaisedEmail(e.target.value)}
                    placeholder="mike@client.example"
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Priority *</label>
                  <select
                    value={issuePriority}
                    onChange={(e) => setIssuePriority(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg font-semibold"
                  >
                    <option value="URGENT">URGENT (1h response)</option>
                    <option value="HIGH">HIGH (2h response)</option>
                    <option value="MEDIUM">MEDIUM (4h response)</option>
                    <option value="LOW">LOW (8h response)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Category</label>
                  <select
                    value={issueType}
                    onChange={(e) => setIssueType(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    <option value="TECHNICAL">Technical</option>
                    <option value="HARDWARE">Hardware Failure</option>
                    <option value="COMMERCIAL">Commercial / Billing</option>
                    <option value="WARRANTY">Warranty Claim</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-stone-600 mb-1 font-medium">Initial Description *</label>
                <textarea
                  rows={3}
                  required
                  value={issueDescription}
                  onChange={(e) => setIssueDescription(e.target.value)}
                  placeholder="Provide precise symptoms or error codes observed..."
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowIssueModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  Dispatch Ticket
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Resolve Ticket */}
      {showResolveModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">Resolve Support Ticket</h3>
              <button onClick={() => setShowResolveModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleResolveIssue} className="space-y-3 text-xs">
              <p className="text-stone-500">
                Resolving ticket <span className="font-bold text-stone-800">{selectedIssue?.issue_number}</span>. This
                will stop the SLA resolution timer.
              </p>
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Resolution Details & Actions Taken *</label>
                <textarea
                  rows={4}
                  required
                  value={resolutionDetails}
                  onChange={(e) => setResolutionDetails(e.target.value)}
                  placeholder="Document corrective actions, root causes, or customer confirmations..."
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowResolveModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm"
                >
                  Confirm Resolution
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New SLA Policy */}
      {showSlaModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">Configure Service Level Agreement</h3>
              <button onClick={() => setShowSlaModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateSla} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 mb-1 font-medium">SLA Policy Name *</label>
                <input
                  type="text"
                  required
                  value={slaName}
                  onChange={(e) => setSlaName(e.target.value)}
                  placeholder="e.g. Platinum Enterprise SLA"
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>
              <label className="flex items-center gap-1.5 text-xs text-stone-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={slaDefault}
                  onChange={(e) => setSlaDefault(e.target.checked)}
                  className="rounded text-emerald-600"
                />
                <span>Set as Global Default SLA for all tickets</span>
              </label>

              <div className="border border-stone-200 rounded-lg p-3 bg-stone-50/50 space-y-2.5">
                <span className="font-bold text-stone-800 text-[11px] uppercase tracking-wide">
                  Priority Response Thresholds (Hours)
                </span>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-stone-500 text-[10px]">Urgent Resp</label>
                    <input
                      type="number"
                      step="0.5"
                      value={slaUrgentHours}
                      onChange={(e) => setSlaUrgentHours(e.target.value)}
                      className="w-full p-1.5 bg-white border border-stone-200 rounded"
                    />
                  </div>
                  <div>
                    <label className="block text-stone-500 text-[10px]">High Resp</label>
                    <input
                      type="number"
                      step="0.5"
                      value={slaHighHours}
                      onChange={(e) => setSlaHighHours(e.target.value)}
                      className="w-full p-1.5 bg-white border border-stone-200 rounded"
                    />
                  </div>
                  <div>
                    <label className="block text-stone-500 text-[10px]">Med Resp</label>
                    <input
                      type="number"
                      step="0.5"
                      value={slaMedHours}
                      onChange={(e) => setSlaMedHours(e.target.value)}
                      className="w-full p-1.5 bg-white border border-stone-200 rounded"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-1 border-t border-stone-200">
                  <div>
                    <label className="block text-stone-500 text-[10px]">Urgent Resol</label>
                    <input
                      type="number"
                      step="1"
                      value={slaUrgentResHours}
                      onChange={(e) => setSlaUrgentResHours(e.target.value)}
                      className="w-full p-1.5 bg-white border border-stone-200 rounded"
                    />
                  </div>
                  <div>
                    <label className="block text-stone-500 text-[10px]">High Resol</label>
                    <input
                      type="number"
                      step="1"
                      value={slaHighResHours}
                      onChange={(e) => setSlaHighResHours(e.target.value)}
                      className="w-full p-1.5 bg-white border border-stone-200 rounded"
                    />
                  </div>
                  <div>
                    <label className="block text-stone-500 text-[10px]">Med Resol</label>
                    <input
                      type="number"
                      step="1"
                      value={slaMedResHours}
                      onChange={(e) => setSlaMedResHours(e.target.value)}
                      className="w-full p-1.5 bg-white border border-stone-200 rounded"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowSlaModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  Save Policy
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: File Warranty Claim */}
      {showClaimModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-stone-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="font-bold text-sm text-stone-900">File RMA Warranty Claim</h3>
              <button onClick={() => setShowClaimModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateWarrantyClaim} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 mb-1 font-medium">Serial Number *</label>
                <input
                  type="text"
                  required
                  value={claimSerial}
                  onChange={(e) => setClaimSerial(e.target.value)}
                  placeholder="e.g. SN-AERO-0192"
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg font-mono uppercase"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Customer</label>
                  <select
                    value={claimCustomerId}
                    onChange={(e) => setClaimCustomerId(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                  >
                    <option value="">Select Customer...</option>
                    {customers.map((c) => (
                      <option key={c.customer_id} value={c.customer_id}>
                        {c.customer_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-stone-600 mb-1 font-medium">Desired Disposition</label>
                  <select
                    value={claimResolutionType}
                    onChange={(e) => setClaimResolutionType(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg font-semibold"
                  >
                    <option value="REPLACE_FREE">Free Replacement</option>
                    <option value="REPAIR_FREE">Free Warranty Repair</option>
                    <option value="PAID_SERVICE">Paid Service</option>
                    <option value="REJECTED">Reject Claim</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-stone-600 mb-1 font-medium">Complaint / Failure Description *</label>
                <textarea
                  rows={3}
                  required
                  value={claimComplaint}
                  onChange={(e) => setClaimComplaint(e.target.value)}
                  placeholder="Describe failure symptom or physical damage..."
                  className="w-full p-2 bg-stone-50 border border-stone-200 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setShowClaimModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  File & Validate Claim
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
