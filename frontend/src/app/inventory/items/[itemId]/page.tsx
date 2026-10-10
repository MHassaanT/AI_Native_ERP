"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, Clock3, Package, Save, Settings2 } from "lucide-react";
import { api } from "@/lib/api";
import { useParams } from "next/navigation";

const currency = (value: string | number | undefined) =>
  `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function InventoryItemPage() {
  const params = useParams<{ itemId: string }>();
  const itemId = params.itemId;
  const [item, setItem] = useState<any | null>(null);
  const [overview, setOverview] = useState<any | null>(null);
  const [todos, setTodos] = useState<any[]>([]);
  const [days, setDays] = useState(30);
  const [draft, setDraft] = useState<any>({});
  const [todoTitle, setTodoTitle] = useState("");
  const [todoAssignee, setTodoAssignee] = useState("");
  const [todoDueDate, setTodoDueDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadItem = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [items, itemOverview, itemTodos] = await Promise.all([
        api.getItems(),
        api.getItemOverview(itemId, days),
        api.getItemTodos(itemId),
      ]);
      const found = items.find((entry: any) => entry.item_id === itemId);
      if (!found) throw new Error("Inventory item not found.");
      setItem(found);
      setDraft({
        item_name: found.item_name || "",
        description: found.description || "",
        barcode: found.barcode || "",
        brand: found.brand || "",
        category: found.category || "",
        package_quantity: found.package_quantity || "",
        image_url: found.image_url || "",
        stock_uom: found.stock_uom || "Nos",
        standard_rate: found.standard_rate || "0",
        reorder_level: found.reorder_level || "0",
        is_active: found.is_active,
      });
      setOverview(itemOverview);
      setTodos(itemTodos);
    } catch (err: any) {
      setError(err.message || "Could not load the inventory item.");
    } finally {
      setLoading(false);
    }
  }, [days, itemId]);

  useEffect(() => {
    void loadItem();
  }, [loadItem]);

  const chartPoints = useMemo(() => {
    const values = overview?.sales?.by_day || [];
    const width = 600;
    const height = 170;
    const maxValue = Math.max(1, ...values.map((value: any) => Number(value.revenue)));
    return values
      .map((value: any, index: number) => {
        const x = values.length < 2 ? width / 2 : (index / (values.length - 1)) * width;
        const y = height - (Number(value.revenue) / maxValue) * (height - 12) - 6;
        return `${x},${y}`;
      })
      .join(" ");
  }, [overview]);

  const saveSettings = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.updateItem(itemId, {
        ...draft,
        standard_rate: Number(draft.standard_rate || 0),
        reorder_level: Number(draft.reorder_level || 0),
      });
      setNotice("Product settings saved.");
      await loadItem();
    } catch (err: any) {
      setError(err.message || "Could not save product settings.");
    } finally {
      setSaving(false);
    }
  };

  const createTodo = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await api.createItemTodo(itemId, {
        title: todoTitle,
        assigned_to: todoAssignee || null,
        due_date: todoDueDate || null,
      });
      setTodoTitle("");
      setTodoAssignee("");
      setTodoDueDate("");
      setTodos(await api.getItemTodos(itemId));
    } catch (err: any) {
      setError(err.message || "Could not add the item task.");
    }
  };

  const updateTodoStatus = async (todoId: string, status: string) => {
    setError(null);
    try {
      await api.updateItemTodo(itemId, todoId, { status });
      setTodos(await api.getItemTodos(itemId));
    } catch (err: any) {
      setError(err.message || "Could not update the item task.");
    }
  };

  if (loading && !item) {
    return <div className="p-8 text-sm text-cream-600">Loading item...</div>;
  }
  if (!item) {
    return <div className="space-y-4 p-8 text-sm text-rose-700">{error || "Item not found."}<a className="block text-blue-700 underline" href="/inventory">Return to inventory</a></div>;
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <a href="/inventory" className="inline-flex items-center gap-2 text-xs font-medium text-cream-600 hover:text-cream-900">
        <ArrowLeft className="h-4 w-4" /> Inventory catalog
      </a>
      {error && <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">{error}</div>}
      {notice && <div className="flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-xs text-emerald-800"><Check className="h-4 w-4" />{notice}</div>}

      <header className="flex flex-col gap-4 border-b border-cream-300 pb-5 sm:flex-row sm:items-center">
        <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-cream-300 bg-cream-200">
          {item.image_url ? <img src={item.image_url} alt={item.item_name} className="h-full w-full object-cover" /> : <Package className="h-9 w-9 text-cream-500" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[11px] text-cream-500">{item.item_code} {item.barcode && `· ${item.barcode}`}</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-cream-950">{item.item_name}</h1>
          <p className="mt-1 text-xs text-cream-600">{[item.brand, item.category, item.package_quantity, item.stock_uom].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-right">
          <div className="rounded-lg border border-cream-300 bg-white px-4 py-3">
            <div className="text-[10px] uppercase tracking-wide text-cream-500">On hand</div>
            <div className="mt-1 font-mono text-lg font-semibold text-cream-900">{Number(item.current_qty || 0).toLocaleString()}</div>
          </div>
          <div className="rounded-lg border border-cream-300 bg-white px-4 py-3">
            <div className="text-[10px] uppercase tracking-wide text-cream-500">Available</div>
            <div className="mt-1 font-mono text-lg font-semibold text-emerald-700">{Number(item.available_qty || 0).toLocaleString()}</div>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-cream-300 bg-white p-4">
          <div className="text-xs text-cream-500">Revenue · selected period</div>
          <div className="mt-2 text-2xl font-semibold text-cream-950">{currency(overview?.sales?.revenue)}</div>
        </div>
        <div className="rounded-xl border border-cream-300 bg-white p-4">
          <div className="text-xs text-cream-500">Units sold · selected period</div>
          <div className="mt-2 text-2xl font-semibold text-cream-950">{Number(overview?.sales?.quantity || 0).toLocaleString()}</div>
        </div>
        <div className="rounded-xl border border-cream-300 bg-white p-4">
          <div className="text-xs text-cream-500">Open item tasks</div>
          <div className="mt-2 text-2xl font-semibold text-cream-950">{todos.filter((todo) => todo.status !== "DONE").length}</div>
        </div>
      </section>

      <section className="rounded-xl border border-cream-300 bg-white p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-cream-950">Sales performance</h2>
            <p className="mt-1 text-[11px] text-cream-500">Revenue recorded on sales orders for this item</p>
          </div>
          <div className="flex gap-1">
            {[7, 30, 90, 365].map((range) => (
              <button key={range} onClick={() => setDays(range)} className={`rounded-md px-3 py-1.5 text-[11px] font-medium ${days === range ? "bg-cream-900 text-white" : "bg-cream-100 text-cream-700 hover:bg-cream-200"}`}>
                {range === 365 ? "1 year" : `${range} days`}
              </button>
            ))}
          </div>
        </div>
        <div className="h-48 w-full overflow-hidden rounded-lg bg-cream-50 px-2 py-3">
          {chartPoints ? (
            <svg viewBox="0 0 600 180" preserveAspectRatio="none" className="h-full w-full" role="img" aria-label={`Daily sales revenue over ${days} days`}>
              <line x1="0" y1="169" x2="600" y2="169" stroke="#d6d0c4" strokeWidth="1" />
              <polyline points={chartPoints} fill="none" stroke="#167d68" strokeWidth="3" vectorEffect="non-scaling-stroke" />
            </svg>
          ) : <div className="flex h-full items-center justify-center text-xs text-cream-500">No sales recorded in this period.</div>}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.5fr_1fr]">
        <section className="rounded-xl border border-cream-300 bg-white p-5">
          <div className="mb-4 flex items-center gap-2"><Clock3 className="h-4 w-4 text-cream-600" /><h2 className="text-sm font-semibold text-cream-950">Recent item activity</h2></div>
          {overview?.activity?.length ? (
            <div className="divide-y divide-cream-200">
              {overview.activity.map((entry: any, index: number) => (
                <div key={`${entry.document_id}-${index}`} className="flex flex-wrap items-center justify-between gap-2 py-3 text-xs">
                  <div><div className="font-medium text-cream-900">{entry.source.replaceAll("_", " ")}</div><div className="mt-1 font-mono text-[10px] text-cream-500">{entry.document_id}</div></div>
                  <div className="text-right"><div className={`font-mono font-semibold ${Number(entry.quantity) >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{Number(entry.quantity) > 0 ? "+" : ""}{Number(entry.quantity).toLocaleString()}</div><div className="mt-1 text-[10px] text-cream-500">{new Date(entry.date).toLocaleString()}</div></div>
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-cream-500">No stock ledger activity has been recorded.</p>}

          <h3 className="mb-3 mt-6 text-xs font-semibold text-cream-900">Recent sales invoices</h3>
          {overview?.sales?.recent_invoices?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead><tr className="border-b border-cream-200 text-cream-500"><th className="py-2">Invoice</th><th>Date</th><th>Customer</th><th className="text-right">Qty</th><th className="text-right">Revenue</th></tr></thead>
                <tbody className="divide-y divide-cream-100">{overview.sales.recent_invoices.map((invoice: any, index: number) => <tr key={`${invoice.invoice_number}-${index}`}><td className="py-2 font-mono">{invoice.invoice_number}</td><td>{invoice.date}</td><td>{invoice.customer}</td><td className="text-right">{Number(invoice.quantity).toLocaleString()}</td><td className="text-right">{currency(invoice.revenue)}</td></tr>)}</tbody>
              </table>
            </div>
          ) : <p className="text-xs text-cream-500">No sales orders recorded for this item.</p>}
        </section>

        <div className="space-y-5">
          <section className="rounded-xl border border-cream-300 bg-white p-5">
            <div className="mb-4 flex items-center gap-2"><Settings2 className="h-4 w-4 text-cream-600" /><h2 className="text-sm font-semibold text-cream-950">Product settings</h2></div>
            <form onSubmit={saveSettings} className="space-y-3 text-xs">
              {[
                ["item_name", "Product name"],
                ["barcode", "Barcode"],
                ["brand", "Brand"],
                ["category", "Category"],
                ["package_quantity", "Pack size / contents"],
                ["image_url", "Image URL"],
                ["stock_uom", "Stock unit"],
                ["standard_rate", "Standard rate"],
                ["reorder_level", "Reorder level"],
              ].map(([field, label]) => (
                <label key={field} className="block text-cream-600">{label}
                  <input
                    type={field === "standard_rate" || field === "reorder_level" ? "number" : field === "image_url" ? "url" : "text"}
                    step={field === "standard_rate" || field === "reorder_level" ? "0.01" : undefined}
                    value={draft[field] ?? ""}
                    onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}
                    className="mt-1 w-full rounded-md border border-cream-300 bg-white px-2.5 py-2 text-xs text-cream-900"
                  />
                </label>
              ))}
              <label className="block text-cream-600">Description
                <textarea value={draft.description || ""} onChange={(event) => setDraft({ ...draft, description: event.target.value })} rows={3} className="mt-1 w-full rounded-md border border-cream-300 bg-white px-2.5 py-2 text-xs text-cream-900" />
              </label>
              <label className="flex items-center gap-2 text-cream-700"><input type="checkbox" checked={Boolean(draft.is_active)} onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })} /> Active item</label>
              <button type="submit" disabled={saving} className="flex w-full items-center justify-center gap-2 rounded-md bg-cream-900 px-3 py-2 font-medium text-white disabled:opacity-50"><Save className="h-3.5 w-3.5" />{saving ? "Saving..." : "Save settings"}</button>
            </form>
            <div className="mt-5 border-t border-cream-200 pt-4">
              <h3 className="text-xs font-semibold text-cream-900">Last purchase order</h3>
              {overview?.last_purchase ? (
                <div className="mt-2 space-y-1 text-xs text-cream-600">
                  <div className="flex justify-between"><span>{overview.last_purchase.order_number}</span><span>{overview.last_purchase.date}</span></div>
                  <div>{overview.last_purchase.supplier} · {Number(overview.last_purchase.quantity).toLocaleString()} units at {currency(overview.last_purchase.unit_price)}</div>
                  <div className="text-[10px] uppercase text-cream-500">{overview.last_purchase.status}</div>
                </div>
              ) : <p className="mt-2 text-xs text-cream-500">No completed purchase order for this item.</p>}
            </div>
          </section>

          <section className="rounded-xl border border-cream-300 bg-white p-5">
            <h2 className="text-sm font-semibold text-cream-950">Item tasks</h2>
            <form onSubmit={createTodo} className="mt-3 space-y-2">
              <input required minLength={2} value={todoTitle} onChange={(event) => setTodoTitle(event.target.value)} placeholder="Add a follow-up or TODO" className="w-full rounded-md border border-cream-300 px-2.5 py-2 text-xs" />
              <div className="grid grid-cols-2 gap-2">
                <input value={todoAssignee} onChange={(event) => setTodoAssignee(event.target.value)} placeholder="Assigned to" className="min-w-0 rounded-md border border-cream-300 px-2.5 py-2 text-xs" />
                <input type="date" value={todoDueDate} onChange={(event) => setTodoDueDate(event.target.value)} className="min-w-0 rounded-md border border-cream-300 px-2 py-2 text-xs" />
              </div>
              <button className="w-full rounded-md border border-cream-300 bg-cream-100 px-3 py-2 text-xs font-medium text-cream-800 hover:bg-cream-200">Add task</button>
            </form>
            <div className="mt-4 divide-y divide-cream-200">
              {todos.map((todo) => (
                <div key={todo.todo_id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className={`text-xs font-medium ${todo.status === "DONE" ? "text-cream-500 line-through" : "text-cream-900"}`}>{todo.title}</div>
                    <div className="mt-1 text-[10px] text-cream-500">{todo.assigned_to || "Unassigned"}{todo.due_date ? ` · Due ${todo.due_date}` : ""}</div>
                  </div>
                  <select value={todo.status} onChange={(event) => void updateTodoStatus(todo.todo_id, event.target.value)} aria-label={`Status for ${todo.title}`} className="rounded border border-cream-300 bg-white px-2 py-1 text-[10px]">
                    <option value="TODO">To do</option><option value="IN_PROGRESS">In progress</option><option value="DONE">Done</option>
                  </select>
                </div>
              ))}
              {!todos.length && <p className="py-3 text-xs text-cream-500">No tasks added for this product.</p>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
