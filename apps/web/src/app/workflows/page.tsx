"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Plus, Trash2, Edit2, Play, Clock } from "lucide-react";

export default function WorkflowsPage() {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [viewingRuns, setViewingRuns] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: workflows } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.get("/api/workflows"),
  });

  const { data: runs } = useQuery({
    queryKey: ["workflow-runs", viewingRuns],
    queryFn: () => api.get(`/api/workflows/${viewingRuns}/runs`),
    enabled: !!viewingRuns,
  });

  const [form, setForm] = useState({
    workflow_name: "",
    workflow_type: "daily_ingest",
    cron_expression: "0 8 * * *",
    timezone: "Asia/Shanghai",
    enabled: true,
    config_json: {},
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/api/workflows", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      setShowForm(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/workflows/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      setEditingId(null);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/workflows/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });

  const runMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/workflows/${id}/run`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });

  const resetForm = () =>
    setForm({
      workflow_name: "",
      workflow_type: "daily_ingest",
      cron_expression: "0 8 * * *",
      timezone: "Asia/Shanghai",
      enabled: true,
      config_json: {},
    });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: form });
    } else {
      createMutation.mutate(form);
    }
  };

  const startEdit = (w: any) => {
    setEditingId(w.id);
    setForm({
      workflow_name: w.workflow_name,
      workflow_type: w.workflow_type,
      cron_expression: w.cron_expression,
      timezone: w.timezone,
      enabled: w.enabled,
      config_json: w.config_json || {},
    });
    setShowForm(true);
  };

  const workflowTypes = [
    { value: "daily_ingest", label: "Daily Ingest" },
    { value: "midday_refresh", label: "Midday Refresh" },
    { value: "classify_pending_articles", label: "Classify Pending" },
    { value: "generate_daily_digest", label: "Generate Digest" },
    { value: "retry_failed_jobs", label: "Retry Failed" },
    { value: "login_health_check", label: "Login Health Check" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Workflows</h1>
        <button
          onClick={() => {
            resetForm();
            setEditingId(null);
            setShowForm(!showForm);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
        >
          <Plus size={16} />
          {showForm ? "Cancel" : "Add Workflow"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-lg border p-6 mb-6 shadow-sm"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name *</label>
              <input
                type="text"
                required
                value={form.workflow_name}
                onChange={(e) =>
                  setForm({ ...form, workflow_name: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Type *</label>
              <select
                value={form.workflow_type}
                onChange={(e) =>
                  setForm({ ...form, workflow_type: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
              >
                {workflowTypes.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Cron Expression *
              </label>
              <input
                type="text"
                required
                value={form.cron_expression}
                onChange={(e) =>
                  setForm({ ...form, cron_expression: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="0 8 * * *"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Timezone</label>
              <input
                type="text"
                value={form.timezone}
                onChange={(e) =>
                  setForm({ ...form, timezone: e.target.value })
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

      {viewingRuns && (
        <div className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Recent Runs</h3>
            <button
              onClick={() => setViewingRuns(null)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Close
            </button>
          </div>
          <div className="space-y-2">
            {runs?.map((r: any) => (
              <div
                key={r.id}
                className="flex items-center justify-between py-2 border-b last:border-0 text-sm"
              >
                <div className="flex items-center gap-3">
                  <Clock size={14} className="text-gray-400" />
                  <span>
                    {r.started_at
                      ? new Date(r.started_at).toLocaleString()
                      : "Pending"}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs ${
                      r.status === "success"
                        ? "bg-green-100 text-green-700"
                        : r.status === "failed"
                        ? "bg-red-100 text-red-700"
                        : r.status === "running"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {r.status}
                  </span>
                  <span className="text-gray-400">{r.trigger_type}</span>
                  {r.duration_ms && (
                    <span className="text-gray-400">
                      {(r.duration_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
              </div>
            ))}
            {runs?.length === 0 && (
              <p className="text-sm text-gray-400">No runs yet</p>
            )}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {workflows?.map((w: any) => (
          <div
            key={w.id}
            className="bg-white rounded-lg border p-5 shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold">{w.workflow_name}</h3>
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs ${
                      w.enabled
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {w.enabled ? "Active" : "Disabled"}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-1 text-sm text-gray-600">
                  <p>
                    <span className="text-gray-400">Type:</span>{" "}
                    {w.workflow_type}
                  </p>
                  <p>
                    <span className="text-gray-400">Schedule:</span>{" "}
                    <code className="bg-gray-100 px-1 rounded text-xs">
                      {w.cron_expression}
                    </code>
                  </p>
                  <p>
                    <span className="text-gray-400">Timezone:</span>{" "}
                    {w.timezone}
                  </p>
                </div>
                {w.last_run_at && (
                  <div className="mt-2 text-sm text-gray-500">
                    Last run: {new Date(w.last_run_at).toLocaleString()} -{" "}
                    <span
                      className={
                        w.last_status === "success"
                          ? "text-green-600"
                          : "text-red-600"
                      }
                    >
                      {w.last_status}
                    </span>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 ml-4">
                <button
                  onClick={() => runMutation.mutate(w.id)}
                  className="p-2 text-gray-500 hover:text-green-600"
                  title="Run now"
                >
                  <Play size={16} />
                </button>
                <button
                  onClick={() => setViewingRuns(w.id)}
                  className="p-2 text-gray-500 hover:text-blue-600"
                  title="View runs"
                >
                  <Clock size={16} />
                </button>
                <button
                  onClick={() => startEdit(w)}
                  className="p-2 text-gray-500 hover:text-gray-700"
                  title="Edit"
                >
                  <Edit2 size={16} />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(w.id)}
                  className="p-2 text-gray-500 hover:text-red-600"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          </div>
        ))}
        {workflows?.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            No workflows configured. Add one to automate your pipeline.
          </div>
        )}
      </div>
    </div>
  );
}
