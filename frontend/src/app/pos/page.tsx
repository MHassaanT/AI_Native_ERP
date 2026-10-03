"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Barcode,
  CheckCircle2,
  CreditCard,
  DollarSign,
  Plus,
  Printer,
  RefreshCw,
  Search,
  ShoppingCart,
  Store,
  Trash2,
  UserCheck,
  X,
  XCircle,
  Clock,
  ArrowRight,
  Pause,
  Play,
  RotateCcw,
  UserPlus,
  Layers,
  Receipt,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { getUser } from "@/lib/auth";

interface POSProfile {
  profile_id: string;
  profile_name: string;
  warehouse_id: string;
  currency: string;
}

interface POSShift {
  has_open_shift: boolean;
  opening_id?: string;
  profile_id?: string;
  opening_float_cash?: number;
  period_start_date?: string;
}

interface CartItem {
  item_id: string;
  item_code: string;
  item_name: string;
  unit_price: number;
  quantity: number;
  discount_pct: number;
}

const formatMoney = (val: any) => {
  const num = Number(val);
  return isNaN(num) ? "0.00" : num.toFixed(2);
};

export default function POSPage() {
  const [profiles, setProfiles] = useState<POSProfile[]>([]);
  const [shift, setShift] = useState<POSShift | null>(null);
  const [items, setItems] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<string>("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [barcodeInput, setBarcodeInput] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"CASH" | "CARD">("CASH");
  const [paidAmount, setPaidAmount] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Phase 1 Parity States
  const [isSplitPayment, setIsSplitPayment] = useState(false);
  const [splitCash, setSplitCash] = useState<string>("");
  const [splitCard, setSplitCard] = useState<string>("");
  const [parkedCarts, setParkedCarts] = useState<any[]>([]);
  const [showParkedModal, setShowParkedModal] = useState(false);
  const [holdNote, setHoldNote] = useState("");
  const [isParking, setIsParking] = useState(false);
  const [isReturnMode, setIsReturnMode] = useState(false);
  const [returnAgainst, setReturnAgainst] = useState("");
  const [showNewCustomerModal, setShowNewCustomerModal] = useState(false);
  const [newCustName, setNewCustName] = useState("");
  const [newCustEmail, setNewCustEmail] = useState("");
  const [newCustPhone, setNewCustPhone] = useState("");
  const [isConsolidatingShift, setIsConsolidatingShift] = useState(false);
  const [isLoadingReceipt, setIsLoadingReceipt] = useState(false);
  const [showRecentInvoicesModal, setShowRecentInvoicesModal] = useState(false);
  const [recentInvoices, setRecentInvoices] = useState<any[]>([]);

  // Modals
  const [showOpenShiftModal, setShowOpenShiftModal] = useState(false);
  const [showCloseShiftModal, setShowCloseShiftModal] = useState(false);
  const [openingFloat, setOpeningFloat] = useState(100);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [countedCash, setCountedCash] = useState(100);
  const [lastInvoice, setLastInvoice] = useState<any | null>(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);

  const user = getUser();
  const userId = user?.user_id || "00000000-0000-0000-0000-000000000001";

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [profilesData, shiftData, itemsData, custsData, parkedData] = await Promise.all([
        api.getPOSProfiles().catch(() => []),
        api.getCurrentPOSShift(userId).catch(() => ({ has_open_shift: false })),
        api.getItems().catch(() => []),
        api.getCustomers().catch(() => []),
        api.getParkedPOSCarts().catch(() => []),
      ]);
      setProfiles(profilesData || []);
      setShift(shiftData);
      setItems(itemsData || []);
      setCustomers(custsData || []);
      setParkedCarts(parkedData || []);
      if (custsData && custsData.length > 0 && !selectedCustomer) {
        setSelectedCustomer(custsData[0].customer_id);
      }
      if (profilesData && profilesData.length > 0 && !selectedProfileId) {
        setSelectedProfileId(profilesData[0].profile_id);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load POS terminal data");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenShift = async () => {
    try {
      setError(null);
      await api.openPOSShift({
        profile_id: selectedProfileId,
        user_id: userId,
        opening_float_cash: Number(openingFloat),
      });
      setShowOpenShiftModal(false);
      setSuccessMsg("Cashier shift opened successfully. Terminal active.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to open shift");
    }
  };

  const handleCloseShift = async () => {
    if (!shift?.opening_id) return;
    try {
      setError(null);
      const res = await api.closePOSShift({
        opening_id: shift.opening_id,
        actual_counted_cash: Number(countedCash),
      });
      setShowCloseShiftModal(false);
      setSuccessMsg(
        `Shift closed. Shift Sales: $${formatMoney(res.total_sales)}, Cash Variance: $${formatMoney(res.cash_variance)}`
      );
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to close shift");
    }
  };

  const addToCart = (item: any) => {
    const rawRate = Number(item.standard_rate);
    const unitPrice = isNaN(rawRate) || rawRate <= 0 ? 50.0 : rawRate;

    const existing = cart.find((c) => c.item_id === item.item_id);
    if (existing) {
      setCart(
        cart.map((c) =>
          c.item_id === item.item_id ? { ...c, quantity: c.quantity + 1 } : c
        )
      );
    } else {
      setCart([
        ...cart,
        {
          item_id: item.item_id,
          item_code: item.item_code,
          item_name: item.item_name,
          unit_price: unitPrice,
          quantity: 1,
          discount_pct: 0,
        },
      ]);
    }
  };

  const updateQuantity = (itemId: string, delta: number) => {
    setCart(
      cart
        .map((c) => {
          if (c.item_id === itemId) {
            const newQty = c.quantity + delta;
            return newQty > 0 ? { ...c, quantity: newQty } : null;
          }
          return c;
        })
        .filter(Boolean) as CartItem[]
    );
  };

  const handleBarcodeScan = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && barcodeInput.trim()) {
      const match = items.find(
        (i) =>
          i.item_code?.toLowerCase() === barcodeInput.trim().toLowerCase() ||
          i.item_name?.toLowerCase().includes(barcodeInput.trim().toLowerCase())
      );
      if (match) {
        addToCart(match);
        setBarcodeInput("");
      } else {
        setError(`Barcode / SKU '${barcodeInput}' not found in catalog.`);
      }
    }
  };

  // Safe Calculations
  const rawSubtotal = cart.reduce(
    (acc, it) => acc + it.quantity * it.unit_price * (1 - it.discount_pct / 100),
    0
  );
  const subtotal = isReturnMode ? -Math.abs(rawSubtotal) : rawSubtotal;
  const tax = isReturnMode ? -Math.abs(subtotal * 0.05) : subtotal * 0.05;
  const grandTotal = subtotal + tax;

  const splitCashNum = Number(splitCash) || 0;
  const splitCardNum = Number(splitCard) || 0;
  const splitTotal = splitCashNum + splitCardNum;
  const splitRemaining = Math.max(0, grandTotal - splitTotal);

  const numericPaid = isSplitPayment
    ? splitTotal
    : paidAmount
    ? Number(paidAmount)
    : grandTotal;
  const change = Math.max(0, numericPaid - grandTotal);

  const handleParkCart = async () => {
    if (cart.length === 0) {
      setError("Cannot park an empty cart.");
      return;
    }
    const profileId = shift?.profile_id || selectedProfileId;
    if (!profileId) {
      setError("Active POS profile is required to park cart.");
      return;
    }
    setIsParking(true);
    try {
      setError(null);
      await api.parkPOSCart({
        profile_id: profileId,
        user_id: userId,
        cart_data: { items: cart },
        customer_id: selectedCustomer || undefined,
        hold_note: holdNote || `Held at ${new Date().toLocaleTimeString()}`,
      });
      setCart([]);
      setHoldNote("");
      setSuccessMsg("Order held in Parked Queue successfully.");
      const updatedParked = await api.getParkedPOSCarts(profileId);
      setParkedCarts(updatedParked || []);
    } catch (err: any) {
      setError(err?.message || "Failed to hold cart");
    } finally {
      setIsParking(false);
    }
  };

  const handleRestoreParkedCart = async (parkedId: string) => {
    try {
      setError(null);
      const res = await api.restoreParkedPOSCart(parkedId);
      if (res?.cart_data) {
        const raw = res.cart_data;
        const items = Array.isArray(raw) ? raw : (Array.isArray(raw?.items) ? raw.items : []);
        if (items.length > 0) {
          setCart(items);
        }
      }
      setShowParkedModal(false);
      setSuccessMsg("Held order restored into register cart.");
      const updatedParked = await api.getParkedPOSCarts(shift?.profile_id || selectedProfileId);
      setParkedCarts(updatedParked || []);
    } catch (err: any) {
      setError(err?.message || "Failed to restore held cart");
    }
  };

  const handleDeleteParkedCart = async (parkedId: string) => {
    try {
      setError(null);
      await api.deleteParkedPOSCart(parkedId);
      const updatedParked = await api.getParkedPOSCarts(shift?.profile_id || selectedProfileId);
      setParkedCarts(updatedParked || []);
      setSuccessMsg("Held order discarded.");
    } catch (err: any) {
      setError(err?.message || "Failed to discard parked cart");
    }
  };

  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCustName.trim()) return;
    try {
      setError(null);
      const res = await api.createCustomer({
        customer_name: newCustName.trim(),
        email: newCustEmail.trim() || undefined,
        phone: newCustPhone.trim() || undefined,
        customer_type: "Individual",
      });
      setShowNewCustomerModal(false);
      setNewCustName("");
      setNewCustEmail("");
      setNewCustPhone("");
      setSuccessMsg(`Customer ${res.customer_name} created successfully.`);
      const updatedCusts = await api.getCustomers();
      setCustomers(updatedCusts || []);
      setSelectedCustomer(res.customer_id);
    } catch (err: any) {
      setError(err?.message || "Failed to create quick customer");
    }
  };

  const handleConsolidateShift = async () => {
    if (!shift?.opening_id) {
      setError("Active or recent shift required to consolidate invoices.");
      return;
    }
    setIsConsolidatingShift(true);
    try {
      setError(null);
      const res = await api.consolidateShiftInvoices(shift.opening_id);
      setSuccessMsg(
        `Shift Consolidated! Merged ${res.total_invoices_merged} invoices into master Sales Invoice ($${formatMoney(res.total_grand_total)}).`
      );
    } catch (err: any) {
      setError(err?.message || "Failed to consolidate shift invoices");
    } finally {
      setIsConsolidatingShift(false);
    }
  };

  const handleLookupReturnReceipt = async (receiptRef?: string) => {
    const refToSearch = (receiptRef || returnAgainst).trim();
    if (!refToSearch) {
      setError("Please enter a receipt number (e.g. POS-20260930-XXXX) or Invoice ID.");
      return;
    }
    setIsLoadingReceipt(true);
    try {
      setError(null);
      const inv = await api.lookupPOSInvoice(refToSearch);
      if (!inv) {
        setError(`Receipt "${refToSearch}" could not be found.`);
        return;
      }
      if (inv.is_return) {
        setError(`Invoice ${inv.pos_invoice_number} is already a Return invoice and cannot be returned again.`);
        return;
      }
      setReturnAgainst(inv.pos_invoice_number);
      if (inv.customer_id) {
        setSelectedCustomer(inv.customer_id);
      }
      if (inv.items && inv.items.length > 0) {
        const returnCartItems = inv.items.map((it: any) => ({
          item_id: it.item_id,
          item_code: it.item_code,
          item_name: it.item_name,
          unit_price: Number(it.unit_price) || 0,
          quantity: Math.abs(Number(it.quantity) || 1),
          discount_pct: Number(it.discount_pct) || 0,
        }));
        setCart(returnCartItems);
      }
      setIsReturnMode(true);
      setShowRecentInvoicesModal(false);
      setSuccessMsg(
        `Original receipt ${inv.pos_invoice_number} loaded (${inv.items?.length || 0} item${inv.items?.length === 1 ? "" : "s"}). Verify quantities to refund and proceed to checkout.`
      );
    } catch (err: any) {
      setError(err?.message || `Receipt "${refToSearch}" not found.`);
    } finally {
      setIsLoadingReceipt(false);
    }
  };

  const handleOpenRecentInvoicesModal = async () => {
    try {
      setError(null);
      const invs = await api.getPOSInvoices(shift?.opening_id);
      const refundable = (invs || []).filter((i: any) => !i.is_return && i.status === "PAID");
      setRecentInvoices(refundable);
      setShowRecentInvoicesModal(true);
    } catch (err: any) {
      setError(err?.message || "Failed to load recent shift invoices");
    }
  };

  const handleCheckout = async () => {
    if (!shift?.opening_id) {
      setError("Please open a shift before checking out.");
      return;
    }
    if (cart.length === 0) {
      setError("Cart is empty.");
      return;
    }
    if (isSplitPayment) {
      if (splitTotal < grandTotal && !isReturnMode) {
        setError(`Split tender ($${formatMoney(splitTotal)}) is less than Grand Total ($${formatMoney(grandTotal)}).`);
        return;
      }
    }
    setIsCheckingOut(true);
    try {
      setError(null);

      const paymentsPayload = isSplitPayment
        ? [
            { payment_method: "CASH", amount: splitCashNum },
            { payment_method: "CARD", amount: splitCardNum },
          ].filter((p) => p.amount > 0)
        : undefined;

      const res = await api.createPOSInvoice({
        opening_id: shift.opening_id,
        customer_id: selectedCustomer || undefined,
        items: cart.map((c) => ({
          item_id: c.item_id,
          quantity: isReturnMode ? -Math.abs(c.quantity) : c.quantity,
          unit_price: c.unit_price,
          discount_pct: c.discount_pct,
        })),
        payment_method: isSplitPayment ? "SPLIT" : paymentMethod,
        paid_amount: numericPaid,
        payments: paymentsPayload,
        is_return: isReturnMode,
        return_against: isReturnMode ? returnAgainst.trim() || undefined : undefined,
      });

      setLastInvoice(res);
      setCart([]);
      setPaidAmount("");
      setSplitCash("");
      setSplitCard("");
      setIsSplitPayment(false);
      if (isReturnMode) {
        setIsReturnMode(false);
        setReturnAgainst("");
        setSuccessMsg(`Return Receipt ${res.pos_invoice_number} processed. Refunded $${formatMoney(Math.abs(res.grand_total))}.`);
      } else {
        setSuccessMsg(`Receipt ${res.pos_invoice_number} paid ($${formatMoney(res.grand_total)}).`);
      }
    } catch (err: any) {
      setError(err?.message || "Checkout failed");
    } finally {
      setIsCheckingOut(false);
    }
  };

  const filteredItems = items.filter(
    (i) =>
      i.item_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      i.item_code?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900 flex items-center gap-2">
            <Store className="h-5 w-5 text-cream-800" />
            <span>Point of Sale &bull; Retail Register</span>
            <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[11px] font-mono font-medium text-cream-800">
              Zero-Sum GL
            </span>
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Fast counter checkout, inventory deduction, and automated double-entry GL journal posting.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setShowParkedModal(true)}
            className="relative flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <Pause className="h-3.5 w-3.5 text-amber-700" />
            <span>Parked Orders</span>
            {parkedCarts.length > 0 && (
              <span className="rounded-full bg-amber-600 text-white text-[10px] px-1.5 py-0.2 font-bold ml-1">
                {parkedCarts.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setIsReturnMode(!isReturnMode)}
            className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
              isReturnMode
                ? "border-terracotta-500 bg-terracotta-100 text-terracotta-900"
                : "border-cream-300 bg-cream-100 text-cream-800 hover:bg-cream-200"
            }`}
          >
            <RotateCcw className={`h-3.5 w-3.5 ${isReturnMode ? "text-terracotta-700" : "text-cream-600"}`} />
            <span>{isReturnMode ? "Return Active" : "Return / Refund"}</span>
          </button>

          <button
            onClick={loadData}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>

          {shift?.has_open_shift ? (
            <div className="flex items-center gap-2 rounded-md border border-sage-400 bg-sage-50 px-3 py-1.5 text-xs text-sage-900">
              <UserCheck className="h-3.5 w-3.5 text-sage-700" />
              <span>
                Shift Active (Float: <strong>${formatMoney(shift.opening_float_cash)}</strong>)
              </span>
              <button
                onClick={handleConsolidateShift}
                disabled={isConsolidatingShift}
                className="ml-1 rounded border border-cream-300 bg-white px-2 py-0.5 text-[11px] font-medium text-cream-800 hover:bg-cream-100 transition-colors flex items-center gap-1"
                title="Consolidate shift sales into master invoice"
              >
                <Layers className="h-3 w-3 text-cream-600" />
                <span>{isConsolidatingShift ? "Merging..." : "Consolidate"}</span>
              </button>
              <button
                onClick={() => {
                  setCountedCash(Number(shift.opening_float_cash || 100));
                  setShowCloseShiftModal(true);
                }}
                className="ml-1 rounded border border-terracotta-400 bg-terracotta-50 px-2 py-0.5 text-[11px] font-semibold text-terracotta-800 hover:bg-terracotta-100 transition-colors"
              >
                Close Shift
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowOpenShiftModal(true)}
              className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Open Cashier Shift</span>
            </button>
          )}
        </div>
      </div>

      {/* Return Mode Alert Banner */}
      {isReturnMode && (
        <div className="rounded-lg border border-terracotta-400 bg-terracotta-50 p-3.5 text-xs text-terracotta-950 flex flex-col lg:flex-row lg:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2">
            <RotateCcw className="h-4 w-4 text-terracotta-700 flex-shrink-0" />
            <div>
              <span className="font-bold">Customer Return / Refund Mode Active:</span>
              <span className="ml-1 text-terracotta-900">
                Items ringed up will be automatically restocked into warehouse inventory and refund will be credited.
              </span>
            </div>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleLookupReturnReceipt();
            }}
            className="flex flex-wrap items-center gap-2"
          >
            <div className="relative">
              <input
                type="text"
                placeholder="Enter Receipt # & press Enter..."
                value={returnAgainst}
                onChange={(e) => setReturnAgainst(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleLookupReturnReceipt();
                  }
                }}
                className="w-56 sm:w-64 rounded border border-terracotta-300 bg-white px-2.5 py-1 text-xs text-terracotta-950 placeholder:text-terracotta-400 focus:outline-none focus:ring-1 focus:ring-terracotta-500 font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={isLoadingReceipt}
              className="rounded bg-terracotta-700 hover:bg-terracotta-800 disabled:opacity-50 text-white px-3 py-1 font-semibold text-xs flex items-center gap-1.5 transition-colors shadow-xs"
            >
              {isLoadingReceipt ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Fetching...</span>
                </>
              ) : (
                <>
                  <Search className="h-3.5 w-3.5" />
                  <span>Fetch Receipt</span>
                </>
              )}
            </button>
            <button
              type="button"
              onClick={handleOpenRecentInvoicesModal}
              className="rounded border border-terracotta-300 bg-white hover:bg-terracotta-100 px-2.5 py-1 font-semibold text-terracotta-900 text-xs flex items-center gap-1 transition-colors"
            >
              <Receipt className="h-3.5 w-3.5 text-terracotta-700" />
              <span>Browse Receipts</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setIsReturnMode(false);
                setReturnAgainst("");
              }}
              className="rounded border border-terracotta-300 bg-terracotta-200 hover:bg-terracotta-300 px-2.5 py-1 font-medium text-terracotta-900 text-xs transition-colors"
            >
              Exit Return Mode
            </button>
          </form>
        </div>
      )}

      {/* Notifications */}
      {error && (
        <div className="rounded-lg border border-terracotta-300 bg-terracotta-50 p-3 text-xs text-terracotta-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-terracotta-700 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-terracotta-700 hover:text-terracotta-900">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {successMsg && (
        <div className="rounded-lg border border-sage-300 bg-sage-50 p-3 text-xs text-sage-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-sage-700 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-sage-700 hover:text-sage-900">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Shift Inactive Warning Banner */}
      {!shift?.has_open_shift && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-xs text-amber-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Clock className="h-5 w-5 text-amber-700 flex-shrink-0" />
            <div>
              <div className="font-semibold text-amber-900">No Active Cashier Shift</div>
              <div className="text-amber-800 text-[11px] mt-0.5">
                To process sales, record payments, and audit cash reconciliation, open a shift with an initial float.
              </div>
            </div>
          </div>
          <button
            onClick={() => setShowOpenShiftModal(true)}
            className="self-start sm:self-auto rounded-md border border-amber-500 bg-amber-100 px-3 py-1.5 font-semibold text-amber-950 hover:bg-amber-200 transition-colors"
          >
            Start Shift Now &rarr;
          </button>
        </div>
      )}

      {/* Main Terminal Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Product Catalog & Fast Search (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Search & Barcode Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="relative">
              <Barcode className="absolute left-3 top-2.5 h-4 w-4 text-cream-500" />
              <input
                type="text"
                placeholder="Scan barcode or SKU + Enter..."
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={handleBarcodeScan}
                className="w-full rounded-md border border-cream-300 bg-white pl-9 pr-3 py-2 text-xs text-cream-900 placeholder:text-cream-400 focus:outline-none focus:ring-1 focus:ring-cream-900"
              />
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-cream-500" />
              <input
                type="text"
                placeholder="Search catalog items..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-md border border-cream-300 bg-white pl-9 pr-3 py-2 text-xs text-cream-900 placeholder:text-cream-400 focus:outline-none focus:ring-1 focus:ring-cream-900"
              />
            </div>
          </div>

          {/* Product Items Grid */}
          <div className="rounded-xl border border-cream-300 bg-cream-50 p-4">
            <div className="flex items-center justify-between pb-3 border-b border-cream-200 text-xs text-cream-700">
              <span className="font-medium">Product Catalog ({filteredItems.length} items)</span>
              <span className="text-[11px] text-cream-600">Click item to add to register cart</span>
            </div>

            {filteredItems.length === 0 ? (
              <div className="py-12 text-center text-xs text-cream-600 space-y-2">
                <Store className="h-8 w-8 text-cream-400 mx-auto" />
                <p>No inventory items found matching &quot;{searchQuery}&quot;.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-3 max-h-[520px] overflow-y-auto pr-1">
                {filteredItems.map((item) => {
                  const price = formatMoney(item.standard_rate || 50.0);
                  return (
                    <div
                      key={item.item_id}
                      onClick={() => addToCart(item)}
                      className="group flex flex-col justify-between rounded-lg border border-cream-300 bg-cream-100/70 p-3.5 hover:border-cream-500 hover:bg-cream-100 transition-all cursor-pointer shadow-2xs select-none"
                    >
                      <div>
                        <div className="font-mono text-[10px] text-cream-600 uppercase tracking-wider">
                          {item.item_code}
                        </div>
                        <div className="text-xs font-semibold text-cream-900 mt-1 line-clamp-2 leading-snug">
                          {item.item_name}
                        </div>
                      </div>

                      <div className="mt-3 flex items-center justify-between pt-2 border-t border-cream-200/60">
                        <span className="font-mono text-sm font-bold text-cream-900">
                          ${price}
                        </span>
                        <span className="rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[10px] font-medium text-cream-800 group-hover:bg-cream-900 group-hover:text-cream-50 transition-colors">
                          + Add
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Active Cart & Checkout (5 cols) */}
        <div className="lg:col-span-5 rounded-xl border border-cream-300 bg-cream-50 p-5 space-y-4 shadow-2xs">
          <div className="flex items-center justify-between border-b border-cream-300 pb-3">
            <div className="flex items-center gap-2">
              <ShoppingCart className="h-4 w-4 text-cream-800" />
              <h2 className="text-sm font-semibold text-cream-900">Register Cart</h2>
              <span className="rounded bg-cream-200 px-2 py-0.5 text-[10px] font-mono font-medium text-cream-800">
                {cart.reduce((sum, it) => sum + it.quantity, 0)} items
              </span>
            </div>
            {cart.length > 0 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={handleParkCart}
                  disabled={isParking}
                  className="text-[11px] text-amber-800 hover:text-amber-950 flex items-center gap-1 bg-amber-100 hover:bg-amber-200 px-2 py-0.5 rounded border border-amber-300 transition-colors"
                  title="Hold order and save in parked queue"
                >
                  <Pause className="h-3 w-3" />
                  <span>{isParking ? "Parking..." : "Hold Cart"}</span>
                </button>
                <button
                  onClick={() => setCart([])}
                  className="text-[11px] text-terracotta-700 hover:text-terracotta-900 flex items-center gap-1"
                >
                  <Trash2 className="h-3 w-3" />
                  <span>Clear</span>
                </button>
              </div>
            )}
          </div>

          {/* Customer Selection */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-medium text-cream-800">
                Customer / Account
              </label>
              <button
                type="button"
                onClick={() => setShowNewCustomerModal(true)}
                className="text-[10px] text-cream-700 hover:text-cream-950 font-medium flex items-center gap-0.5"
              >
                <UserPlus className="h-3 w-3" />
                <span>+ New Customer</span>
              </button>
            </div>
            <select
              value={selectedCustomer}
              onChange={(e) => setSelectedCustomer(e.target.value)}
              className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
            >
              <option value="">Walk-In Retail Customer (Cash Sale)</option>
              {customers.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>
                  {c.customer_name} ({c.customer_code})
                </option>
              ))}
            </select>
          </div>

          {/* Cart Items List */}
          <div className="max-h-[260px] overflow-y-auto space-y-2 pr-1">
            {cart.length === 0 ? (
              <div className="py-8 text-center text-xs text-cream-600">
                Cart is currently empty.
                <div className="text-[11px] text-cream-500 mt-1">
                  Select products from the catalog to begin checkout.
                </div>
              </div>
            ) : (
              cart.map((item) => (
                <div
                  key={item.item_id}
                  className="rounded-lg border border-cream-200 bg-cream-100 p-2.5 flex items-center justify-between text-xs"
                >
                  <div className="flex-1 min-w-0 pr-2">
                    <div className="font-semibold text-cream-900 truncate">{item.item_name}</div>
                    <div className="font-mono text-[11px] text-cream-600">
                      ${formatMoney(item.unit_price)} each
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="flex items-center rounded border border-cream-300 bg-white">
                      <button
                        onClick={() => updateQuantity(item.item_id, -1)}
                        className="px-2 py-0.5 text-xs text-cream-800 hover:bg-cream-100 font-bold"
                      >
                        -
                      </button>
                      <span className="px-2 text-xs font-mono font-bold text-cream-900">
                        {item.quantity}
                      </span>
                      <button
                        onClick={() => updateQuantity(item.item_id, 1)}
                        className="px-2 py-0.5 text-xs text-cream-800 hover:bg-cream-100 font-bold"
                      >
                        +
                      </button>
                    </div>

                    <div className="font-mono font-bold text-cream-900 min-w-[60px] text-right">
                      ${formatMoney(item.quantity * item.unit_price)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Cart Totals Summary */}
          <div className="rounded-lg border border-cream-300 bg-cream-100/80 p-3.5 space-y-2 text-xs">
            <div className="flex justify-between text-cream-700">
              <span>Subtotal:</span>
              <span className="font-mono font-semibold">${formatMoney(subtotal)}</span>
            </div>
            <div className="flex justify-between text-cream-700">
              <span>Sales Tax (5%):</span>
              <span className="font-mono font-semibold">${formatMoney(tax)}</span>
            </div>
            <div className="flex justify-between border-t border-cream-300 pt-2 text-sm font-bold text-cream-900">
              <span>Grand Total:</span>
              <span className="font-mono text-base text-cream-900">${formatMoney(grandTotal)}</span>
            </div>
          </div>

          {/* Payment Method & Tender */}
          <div className="space-y-3 pt-1">
            {/* Split Tender Checkbox */}
            <div className="flex items-center justify-between border-b border-cream-200 pb-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-cream-800 font-medium">
                <input
                  type="checkbox"
                  checked={isSplitPayment}
                  onChange={(e) => {
                    setIsSplitPayment(e.target.checked);
                    if (e.target.checked) {
                      const half = Math.round((grandTotal / 2) * 100) / 100;
                      setSplitCash(String(half.toFixed(2)));
                      setSplitCard(String((grandTotal - half).toFixed(2)));
                    }
                  }}
                  className="rounded border-cream-300 text-cream-900 focus:ring-cream-900"
                />
                <span>Split Multi-Tender Payment (Cash + Card)</span>
              </label>
              {isSplitPayment && (
                <span className="text-[11px] font-mono">
                  {splitRemaining > 0 ? (
                    <span className="text-amber-700 font-semibold">Remaining: ${formatMoney(splitRemaining)}</span>
                  ) : (
                    <span className="text-sage-700 font-semibold">100% Covered</span>
                  )}
                </span>
              )}
            </div>

            {isSplitPayment ? (
              <div className="space-y-2 rounded-lg border border-cream-300 bg-cream-100/60 p-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] text-cream-700 block mb-1">Cash Tender</label>
                    <div className="relative">
                      <span className="absolute left-2.5 top-1.5 font-mono text-cream-500">$</span>
                      <input
                        type="number"
                        value={splitCash}
                        onChange={(e) => setSplitCash(e.target.value)}
                        placeholder="0.00"
                        className="w-full rounded border border-cream-300 bg-white pl-6 pr-2 py-1.5 text-xs font-mono text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-[11px] text-cream-700 block mb-1">Card Tender</label>
                    <div className="relative">
                      <span className="absolute left-2.5 top-1.5 font-mono text-cream-500">$</span>
                      <input
                        type="number"
                        value={splitCard}
                        onChange={(e) => setSplitCard(e.target.value)}
                        placeholder="0.00"
                        className="w-full rounded border border-cream-300 bg-white pl-6 pr-2 py-1.5 text-xs font-mono text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                      />
                    </div>
                  </div>
                </div>
                <div className="flex justify-between items-center text-[11px] pt-1 text-cream-800">
                  <span>Total Tendered:</span>
                  <span className="font-mono font-bold">${formatMoney(splitTotal)}</span>
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setPaymentMethod("CASH")}
                    className={`flex items-center justify-center gap-1.5 rounded-md border py-2 text-xs font-semibold transition-colors ${
                      paymentMethod === "CASH"
                        ? "border-cream-900 bg-cream-900 text-cream-50"
                        : "border-cream-300 bg-white text-cream-800 hover:bg-cream-100"
                    }`}
                  >
                    <DollarSign className="h-3.5 w-3.5" />
                    <span>Cash Payment</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setPaymentMethod("CARD")}
                    className={`flex items-center justify-center gap-1.5 rounded-md border py-2 text-xs font-semibold transition-colors ${
                      paymentMethod === "CARD"
                        ? "border-cream-900 bg-cream-900 text-cream-50"
                        : "border-cream-300 bg-white text-cream-800 hover:bg-cream-100"
                    }`}
                  >
                    <CreditCard className="h-3.5 w-3.5" />
                    <span>Card Payment</span>
                  </button>
                </div>

                {paymentMethod === "CASH" && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1">
                        <span className="absolute left-3 top-2 text-xs text-cream-500 font-mono">$</span>
                        <input
                          type="number"
                          placeholder={`Tender (e.g. ${formatMoney(grandTotal)})`}
                          value={paidAmount}
                          onChange={(e) => setPaidAmount(e.target.value)}
                          className="w-full rounded-md border border-cream-300 bg-white pl-7 pr-3 py-1.5 text-xs font-mono text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => setPaidAmount(String(grandTotal.toFixed(2)))}
                        className="rounded border border-cream-300 bg-cream-100 px-2.5 py-1.5 text-[11px] font-medium text-cream-800 hover:bg-cream-200"
                      >
                        Exact
                      </button>
                    </div>

                    {numericPaid > grandTotal && (
                      <div className="flex justify-between items-center px-2 py-1 bg-sage-50 border border-sage-300 rounded text-xs text-sage-900 font-mono">
                        <span>Change Due:</span>
                        <span className="font-bold">${formatMoney(change)}</span>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            <button
              onClick={handleCheckout}
              disabled={isCheckingOut || cart.length === 0 || !shift?.has_open_shift}
              className="w-full flex items-center justify-center gap-2 rounded-md border border-sage-500 bg-sage-50 hover:bg-sage-100 py-2.5 text-xs font-bold text-sage-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs"
            >
              <CheckCircle2 className="h-4 w-4 text-sage-700" />
              <span>
                {isCheckingOut
                  ? "Processing Sale..."
                  : `Charge $${formatMoney(grandTotal)} & Print Receipt`}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* MODAL 1: Open Shift */}
      {showOpenShiftModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Open Cashier Shift</h3>
              <button
                onClick={() => setShowOpenShiftModal(false)}
                className="text-cream-600 hover:text-cream-900"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">POS Profile</label>
                <select
                  value={selectedProfileId}
                  onChange={(e) => setSelectedProfileId(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                >
                  {profiles.map((p) => (
                    <option key={p.profile_id} value={p.profile_id}>
                      {p.profile_name} ({p.currency})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">
                  Opening Float Cash (Drawer Starting Balance)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2 font-mono text-cream-500">$</span>
                  <input
                    type="number"
                    value={openingFloat}
                    onChange={(e) => setOpeningFloat(Number(e.target.value))}
                    className="w-full rounded-md border border-cream-300 bg-white pl-7 pr-3 py-2 text-xs font-mono text-cream-900"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
              <button
                type="button"
                onClick={() => setShowOpenShiftModal(false)}
                className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleOpenShift}
                className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
              >
                Confirm &amp; Start Shift
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Close Shift & Cash Reconciliation */}
      {showCloseShiftModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Close Cashier Shift &amp; Reconcile</h3>
              <button
                onClick={() => setShowCloseShiftModal(false)}
                className="text-cream-600 hover:text-cream-900"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="rounded-lg border border-cream-300 bg-cream-100 p-3 space-y-1">
                <div className="text-cream-600">Opening Float:</div>
                <div className="font-mono font-bold text-cream-900">
                  ${formatMoney(shift?.opening_float_cash)}
                </div>
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">
                  Actual Physical Cash Counted in Drawer
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2 font-mono text-cream-500">$</span>
                  <input
                    type="number"
                    value={countedCash}
                    onChange={(e) => setCountedCash(Number(e.target.value))}
                    className="w-full rounded-md border border-cream-300 bg-white pl-7 pr-3 py-2 text-xs font-mono text-cream-900"
                  />
                </div>
                <p className="text-[11px] text-cream-600 mt-1">
                  System will compute discrepancy between expected cash drawer sales and physical count.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
              <button
                type="button"
                onClick={() => setShowCloseShiftModal(false)}
                className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCloseShift}
                className="rounded-md border border-terracotta-400 bg-terracotta-50 px-4 py-1.5 text-xs font-medium text-terracotta-900 hover:bg-terracotta-100"
              >
                Submit Reconciliation &amp; Close Shift
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Parked Orders Queue */}
      {showParkedModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <div className="flex items-center gap-2">
                <Pause className="h-4 w-4 text-amber-700" />
                <h3 className="text-sm font-bold text-cream-900">Held / Parked Orders Queue</h3>
              </div>
              <button
                onClick={() => setShowParkedModal(false)}
                className="text-cream-600 hover:text-cream-900"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[340px] overflow-y-auto space-y-2.5 pr-1">
              {parkedCarts.length === 0 ? (
                <div className="py-10 text-center text-xs text-cream-600 space-y-1">
                  <Pause className="h-6 w-6 text-cream-400 mx-auto" />
                  <p>No held carts currently in queue.</p>
                </div>
              ) : (
                parkedCarts.map((pc) => {
                  const itemsList = Array.isArray(pc.cart_data)
                    ? pc.cart_data
                    : (Array.isArray(pc.cart_data?.items) ? pc.cart_data.items : []);
                  const itemCount = itemsList.reduce((sum: number, it: any) => sum + (Number(it.quantity) || 1), 0);
                  const totalEst = itemsList.reduce((sum: number, it: any) => sum + (Number(it.quantity) || 1) * (Number(it.unit_price) || 0), 0);

                  return (
                    <div
                      key={pc.parked_id}
                      className="rounded-lg border border-cream-300 bg-cream-100 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                    >
                      <div className="space-y-1">
                        <div className="font-semibold text-cream-950 flex items-center gap-2">
                          <span>{pc.customer_name || "Walk-In Customer"}</span>
                          <span className="font-mono text-[10px] text-cream-600 bg-cream-200 px-1.5 py-0.5 rounded">
                            {itemCount} items &bull; ${formatMoney(totalEst)}
                          </span>
                        </div>
                        <div className="text-[11px] text-cream-700 italic">
                          &quot;{pc.hold_note || "Held Order"}&quot;
                        </div>
                        <div className="text-[10px] text-cream-500 font-mono">
                          {new Date(pc.created_at).toLocaleTimeString()} &bull; {new Date(pc.created_at).toLocaleDateString()}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-auto">
                        <button
                          onClick={() => handleRestoreParkedCart(pc.parked_id)}
                          className="rounded-md border border-sage-400 bg-sage-50 px-2.5 py-1 text-[11px] font-semibold text-sage-900 hover:bg-sage-100 transition-colors flex items-center gap-1"
                        >
                          <Play className="h-3 w-3 text-sage-700" />
                          <span>Resume</span>
                        </button>
                        <button
                          onClick={() => handleDeleteParkedCart(pc.parked_id)}
                          className="rounded-md border border-terracotta-300 bg-terracotta-50 px-2 py-1 text-[11px] font-medium text-terracotta-800 hover:bg-terracotta-100 transition-colors"
                          title="Discard held order"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="flex justify-end border-t border-cream-300 pt-3">
              <button
                type="button"
                onClick={() => setShowParkedModal(false)}
                className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
              >
                Close Queue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Select Original Receipt for Return */}
      {showRecentInvoicesModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <div className="flex items-center gap-2">
                <Receipt className="h-4 w-4 text-terracotta-700" />
                <h3 className="text-sm font-bold text-cream-900">Select Original Receipt to Refund</h3>
              </div>
              <button
                onClick={() => setShowRecentInvoicesModal(false)}
                className="text-cream-600 hover:text-cream-900"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[340px] overflow-y-auto space-y-2.5 pr-1">
              {recentInvoices.length === 0 ? (
                <div className="py-10 text-center text-xs text-cream-600 space-y-1">
                  <Receipt className="h-6 w-6 text-cream-400 mx-auto" />
                  <p>No completed sales receipts found in current shift.</p>
                  <p className="text-[11px] text-cream-500">You can also type any receipt # directly into the input bar.</p>
                </div>
              ) : (
                recentInvoices.map((inv) => (
                  <div
                    key={inv.pos_invoice_id}
                    className="rounded-lg border border-cream-300 bg-cream-100 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs hover:border-terracotta-400 transition-colors"
                  >
                    <div className="space-y-1">
                      <div className="font-semibold text-cream-950 flex items-center gap-2 font-mono">
                        <span>{inv.pos_invoice_number}</span>
                        <span className="font-sans text-[10px] text-cream-700 bg-cream-200 px-1.5 py-0.5 rounded font-normal">
                          ${formatMoney(inv.grand_total)} &bull; {inv.payment_method}
                        </span>
                      </div>
                      <div className="text-[10px] text-cream-500 font-mono">
                        {inv.posting_date}
                      </div>
                    </div>

                    <button
                      onClick={() => handleLookupReturnReceipt(inv.pos_invoice_number)}
                      disabled={isLoadingReceipt}
                      className="rounded-md border border-terracotta-400 bg-terracotta-50 px-3 py-1.5 text-xs font-semibold text-terracotta-900 hover:bg-terracotta-100 transition-colors flex items-center justify-center gap-1.5"
                    >
                      <RotateCcw className="h-3 w-3 text-terracotta-700" />
                      <span>Load for Refund</span>
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end border-t border-cream-300 pt-3">
              <button
                type="button"
                onClick={() => setShowRecentInvoicesModal(false)}
                className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Quick New Customer */}
      {showNewCustomerModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleCreateCustomer}
            className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-sm p-6 space-y-4 text-xs"
          >
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Add New Retail Customer</h3>
              <button
                type="button"
                onClick={() => setShowNewCustomerModal(false)}
                className="text-cream-600 hover:text-cream-900"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Customer Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Jane Doe"
                  value={newCustName}
                  onChange={(e) => setNewCustName(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                />
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">Phone Number</label>
                <input
                  type="text"
                  placeholder="+1 555-0199"
                  value={newCustPhone}
                  onChange={(e) => setNewCustPhone(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                />
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">Email Address</label>
                <input
                  type="email"
                  placeholder="jane.doe@example.com"
                  value={newCustEmail}
                  onChange={(e) => setNewCustEmail(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
              <button
                type="button"
                onClick={() => setShowNewCustomerModal(false)}
                className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
              >
                Save &amp; Select
              </button>
            </div>
          </form>
        </div>
      )}

      {/* MODAL 3: Comprehensive POS Receipt / Tax Invoice */}
      {lastInvoice && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div
            id="pos-printable-receipt"
            className="bg-[#FCFAF6] text-cream-950 border border-cream-300 rounded-xl shadow-2xl w-full max-w-md p-6 font-mono text-xs relative max-h-[92vh] overflow-y-auto"
          >
            {/* Modal Close Icon (Non-printable) */}
            <button
              type="button"
              onClick={() => setLastInvoice(null)}
              className="no-print absolute top-3 right-3 text-cream-400 hover:text-cream-700 p-1 rounded-md transition-colors"
              title="Close Receipt"
            >
              <X className="h-4 w-4" />
            </button>

            {/* Receipt Header */}
            <div className="text-center border-b border-dashed border-cream-300 pb-3">
              <div className="font-bold text-base tracking-wider uppercase text-cream-950">
                {user?.company_name || "Zirrah Pvt Ltd"}
              </div>
              <div className="text-[11px] font-semibold text-cream-700 tracking-wide mt-0.5 uppercase">
                {lastInvoice.profile_name || "Main POS Terminal Store"}
              </div>
              <div className="text-[10px] text-cream-500 uppercase tracking-widest mt-1">
                Official Retail Tax Invoice
              </div>
              <div className="mt-2 inline-block px-2 py-0.5 rounded bg-cream-200 text-cream-900 font-bold text-[11px]">
                {lastInvoice.pos_invoice_number}
              </div>
            </div>

            {/* Transaction Metadata */}
            <div className="grid grid-cols-2 gap-2 text-[11px] border-b border-dashed border-cream-300 py-3 text-cream-800">
              <div>
                <span className="text-cream-500 block text-[9px] uppercase tracking-wider">Date & Time</span>
                <span className="font-medium">
                  {lastInvoice.posting_date}
                  {lastInvoice.posting_time ? ` ${String(lastInvoice.posting_time).substring(0, 5)}` : ""}
                </span>
              </div>
              <div className="text-right">
                <span className="text-cream-500 block text-[9px] uppercase tracking-wider">Customer</span>
                <span className="font-medium truncate block" title={lastInvoice.customer_name}>
                  {lastInvoice.customer_name || "Walk-In Customer"}
                </span>
                {lastInvoice.customer_code && (
                  <span className="text-[9px] text-cream-500">[{lastInvoice.customer_code}]</span>
                )}
              </div>
              <div>
                <span className="text-cream-500 block text-[9px] uppercase tracking-wider">Cashier / Staff</span>
                <span className="font-medium">{user?.full_name || user?.email || "Terminal Operator"}</span>
              </div>
              <div className="text-right">
                <span className="text-cream-500 block text-[9px] uppercase tracking-wider">Payment Status</span>
                <span className="inline-flex items-center gap-1 font-semibold text-emerald-800">
                  <CheckCircle2 className="h-3 w-3 inline" /> PAID ({lastInvoice.payment_method || "CASH"})
                </span>
              </div>
            </div>

            {/* Line Items Table */}
            <div className="py-3 border-b border-dashed border-cream-300">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-cream-200 text-[10px] text-cream-600 uppercase tracking-wider">
                    <th className="pb-1.5 font-semibold text-left">Item Description</th>
                    <th className="pb-1.5 font-semibold text-center w-12">Qty</th>
                    <th className="pb-1.5 font-semibold text-right w-16">Price</th>
                    <th className="pb-1.5 font-semibold text-right w-16">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-100">
                  {lastInvoice.items && lastInvoice.items.length > 0 ? (
                    lastInvoice.items.map((it: any, idx: number) => (
                      <tr key={idx} className="align-top">
                        <td className="py-2 pr-1">
                          <div className="font-semibold text-cream-950 leading-tight">
                            {it.item_name || it.item_code}
                          </div>
                          <div className="text-[10px] text-cream-500 font-mono">
                            {it.item_code}
                            {it.discount_pct > 0 && (
                              <span className="ml-1 text-terracotta-700">({it.discount_pct}% off)</span>
                            )}
                          </div>
                        </td>
                        <td className="py-2 text-center text-cream-800 font-medium whitespace-nowrap">
                          {it.quantity}
                        </td>
                        <td className="py-2 text-right text-cream-800 whitespace-nowrap">
                          ${formatMoney(it.unit_price)}
                        </td>
                        <td className="py-2 text-right font-bold text-cream-950 whitespace-nowrap">
                          ${formatMoney(it.amount)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-3 text-center text-cream-500 italic">
                        Standard POS Sale Items
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Totals Breakdown */}
            <div className="space-y-1.5 py-3 border-b border-dashed border-cream-300 text-xs">
              <div className="flex justify-between text-cream-700">
                <span>Total Items / Quantity:</span>
                <span className="font-semibold">
                  {lastInvoice.items?.reduce((sum: number, it: any) => sum + (Number(it.quantity) || 0), 0) ||
                    lastInvoice.items?.length ||
                    1}
                </span>
              </div>
              <div className="flex justify-between text-cream-700">
                <span>Net Subtotal:</span>
                <span>${formatMoney(lastInvoice.subtotal)}</span>
              </div>
              {Number(lastInvoice.discount_amount) > 0 && (
                <div className="flex justify-between text-terracotta-700">
                  <span>Order Discount:</span>
                  <span>-${formatMoney(lastInvoice.discount_amount)}</span>
                </div>
              )}
              <div className="flex justify-between text-cream-700">
                <span>Sales Tax (5%):</span>
                <span>${formatMoney(lastInvoice.tax_amount)}</span>
              </div>
              <div className="flex justify-between font-bold text-base text-cream-950 pt-2 border-t border-cream-300">
                <span>GRAND TOTAL:</span>
                <span>${formatMoney(lastInvoice.grand_total)}</span>
              </div>
            </div>

            {/* Payment & Change Tendered */}
            <div className="space-y-1 py-2 border-b border-dashed border-cream-300 text-[11px] text-cream-800">
              <div className="flex justify-between">
                <span>Amount Tendered ({lastInvoice.payment_method}):</span>
                <span className="font-semibold">
                  ${formatMoney(lastInvoice.paid_amount || lastInvoice.grand_total)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Change Returned:</span>
                <span className="font-semibold text-emerald-800">
                  ${formatMoney(lastInvoice.change_amount || 0)}
                </span>
              </div>
            </div>

            {/* Barcode / Footer */}
            <div className="pt-3 text-center space-y-2">
              <div className="flex justify-center items-center gap-1 opacity-70">
                <Barcode className="h-6 w-32" />
              </div>
              <div className="text-[10px] text-cream-600 font-mono tracking-widest">
                *{lastInvoice.pos_invoice_number}*
              </div>
              <div className="text-[10px] text-cream-500 leading-tight">
                Thank you for your business!
                <br />
                Goods may be exchanged within 14 days with original receipt.
              </div>
              <div className="text-[9px] text-cream-400 uppercase tracking-wider pt-1">
                AI-Native Autonomous ERP &bull; Verified POS Record
              </div>
            </div>

            {/* Modal Actions (Hidden from Print) */}
            <div className="no-print flex justify-end gap-2 border-t border-cream-300 pt-4 font-sans mt-4">
              <button
                type="button"
                onClick={() => window.print()}
                className="rounded-md border border-cream-300 bg-cream-100 px-3.5 py-1.5 text-xs font-semibold text-cream-900 hover:bg-cream-200 flex items-center gap-1.5 shadow-xs cursor-pointer transition-colors"
              >
                <Printer className="h-3.5 w-3.5 text-cream-700" />
                <span>Print Receipt</span>
              </button>
              <button
                type="button"
                onClick={() => setLastInvoice(null)}
                className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-semibold text-cream-50 hover:bg-cream-800 shadow-xs cursor-pointer transition-colors"
              >
                New Sale / Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
