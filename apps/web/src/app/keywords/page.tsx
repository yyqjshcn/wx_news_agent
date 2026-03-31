"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Plus, Trash2, Edit2, Upload } from "lucide-react";

export default function KeywordsPage() {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [bulkText, setBulkText] = useState("");
  const [showBulk, setShowBulk] = useState(false);
  const queryClient = useQueryClient();

  const { data: keywords } = useQuery({
    queryKey: ["keywords"],
    queryFn: () => api.get("/api/keywords"),
  });

  const [form, setForm] = useState({
    keyword: "",
    keyword_type: "industry",
    weight: 1,
    enabled: true,
    notes: "",
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/api/keywords", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
      setShowForm(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/keywords/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
      setEditingId(null);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/keywords/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
    },
  });

  const importMutation = useMutation({
    mutationFn: (kwList: any[]) => api.post("/api/keywords/import", { keywords: kwList }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
      setShowBulk(false);
      setBulkText("");
    },
  });

  const resetForm = () =>
    setForm({
      keyword: "",
      keyword_type: "industry",
      weight: 1,
      enabled: true,
      notes: "",
    });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: form });
    } else {
      createMutation.mutate(form);
    }
  };

  const startEdit = (k: any) => {
    setEditingId(k.id);
    setForm({
      keyword: k.keyword,
      keyword_type: k.keyword_type,
      weight: k.weight,
      enabled: k.enabled,
      notes: k.notes || "",
    });
    setShowForm(true);
  };

  const handleBulkImport = () => {
    const lines = bulkText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const kwList = lines.map((line) => ({
      keyword: line,
      keyword_type: form.keyword_type,
      weight: form.weight,
      enabled: true,
      notes: "",
    }));
    importMutation.mutate(kwList);
  };

  const typeColors: Record<string, string> = {
    industry: "bg-blue-100 text-blue-700",
    company: "bg-purple-100 text-purple-700",
    event: "bg-amber-100 text-amber-700",
    exclude: "bg-red-100 text-red-700",
  };

  const grouped = (keywords || []).reduce((acc: any, k: any) => {
    if (!acc[k.keyword_type]) acc[k.keyword_type] = [];
    acc[k.keyword_type].push(k);
    return acc;
  }, {});

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Keywords</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowBulk(!showBulk)}
            className="flex items-center gap-2 px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
          >
            <Upload size={16} />
            Bulk Import
          </button>
          <button
            onClick={() => {
              resetForm();
              setEditingId(null);
              setShowForm(!showForm);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
          >
            <Plus size={16} />
            {showForm ? "Cancel" : "Add Keyword"}
          </button>
        </div>
      </div>

      {showBulk && (
        <div className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
          <h3 className="font-medium mb-3">Bulk Import</h3>
          <div className="flex gap-3 mb-3">
            <select
              value={form.keyword_type}
              onChange={(e) => setForm({ ...form, keyword_type: e.target.value })}
              className="px-3 py-2 border rounded-md text-sm"
            >
              <option value="industry">Industry</option>
              <option value="company">Company</option>
              <option value="event">Event</option>
              <option value="exclude">Exclude</option>
            </select>
            <input
              type="number"
              value={form.weight}
              onChange={(e) => setForm({ ...form, weight: parseInt(e.target.value) })}
              className="w-20 px-3 py-2 border rounded-md text-sm"
              min={1}
              max={10}
            />
          </div>
          <textarea
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            className="w-full px-3 py-2 border rounded-md text-sm"
            rows={6}
            placeholder="One keyword per line..."
          />
          <button
            onClick={handleBulkImport}
            disabled={importMutation.isPending || !bulkText.trim()}
            className="mt-3 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            Import
          </button>
        </div>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-lg border p-6 mb-6 shadow-sm"
        >
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-1">Keyword *</label>
              <input
                type="text"
                required
                value={form.keyword}
                onChange={(e) => setForm({ ...form, keyword: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <select
                value={form.keyword_type}
                onChange={(e) =>
                  setForm({ ...form, keyword_type: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
              >
                <option value="industry">Industry</option>
                <option value="company">Company</option>
                <option value="event">Event</option>
                <option value="exclude">Exclude</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Weight</label>
              <input
                type="number"
                min={1}
                max={10}
                value={form.weight}
                onChange={(e) =>
                  setForm({ ...form, weight: parseInt(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm mb-4">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Enabled
          </label>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            {editingId ? "Update" : "Create"}
          </button>
        </form>
      )}

      {Object.entries(grouped).map(([type, kws]: [string, any]) => (
        <div key={type} className="mb-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {type}
          </h3>
          <div className="flex flex-wrap gap-2">
            {kws.map((k: any) => (
              <div
                key={k.id}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border ${
                  k.enabled ? "bg-white" : "bg-gray-50 opacity-60"
                }`}
              >
                <span className={typeColors[k.keyword_type] || "bg-gray-100"}>
                  {k.keyword}
                </span>
                <span className="text-gray-400 text-xs">w:{k.weight}</span>
                <button
                  onClick={() => startEdit(k)}
                  className="text-gray-400 hover:text-gray-700"
                >
                  <Edit2 size={12} />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(k.id)}
                  className="text-gray-400 hover:text-red-600"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}

      {keywords?.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No keywords configured. Add some to improve article classification.
        </div>
      )}
    </div>
  );
}
