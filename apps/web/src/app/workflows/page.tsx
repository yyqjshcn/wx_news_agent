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
    onError: (error: Error) => {
      alert(`创建失败: ${error.message}`);
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
    onError: (error: Error) => {
      alert(`更新失败: ${error.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/workflows/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
    onError: (error: Error) => {
      alert(`删除失败: ${error.message}`);
    },
  });

  const runMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/workflows/${id}/run`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      queryClient.invalidateQueries({ queryKey: ["workflow-runs"] });
    },
    onError: (error: Error) => {
      alert(`运行失败: ${error.message}`);
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
    { value: "daily_ingest", label: "每日采集" },
    { value: "midday_refresh", label: "午间刷新" },
    { value: "classify_pending_articles", label: "文章分类" },
    { value: "generate_daily_digest", label: "生成摘要" },
    { value: "retry_failed_jobs", label: "重试失败任务" },
    { value: "login_health_check", label: "登录检查" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">工作流</h1>
        <button
          onClick={() => {
            resetForm();
            setEditingId(null);
            setShowForm(!showForm);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
        >
          <Plus size={16} />
          {showForm ? "取消" : "添加工作流"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-lg border p-6 mb-6 shadow-sm"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">名称 *</label>
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
              <label className="block text-sm font-medium mb-1">类型 *</label>
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
                Cron 表达式 *
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
              <label className="block text-sm font-medium mb-1">时区</label>
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
            启用
          </label>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            {editingId ? "更新" : "创建"}
          </button>
        </form>
      )}

      {viewingRuns && (
        <div className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">最近运行</h3>
            <button
              onClick={() => setViewingRuns(null)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              关闭
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
                      : "等待中"}
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
                    {r.status === "success" ? "成功" : r.status === "failed" ? "失败" : r.status === "running" ? "运行中" : r.status}
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
              <p className="text-sm text-gray-400">暂无运行记录</p>
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
                    {w.enabled ? "已启用" : "已禁用"}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-1 text-sm text-gray-600">
                  <p>
                    <span className="text-gray-400">类型:</span>{" "}
                    {w.workflow_type}
                  </p>
                  <p>
                    <span className="text-gray-400">调度:</span>{" "}
                    <code className="bg-gray-100 px-1 rounded text-xs">
                      {w.cron_expression}
                    </code>
                  </p>
                  <p>
                    <span className="text-gray-400">时区:</span>{" "}
                    {w.timezone}
                  </p>
                </div>
                {w.last_run_at && (
                  <div className="mt-2 text-sm text-gray-500">
                    上次运行: {new Date(w.last_run_at).toLocaleString()} -{" "}
                    <span
                      className={
                        w.last_status === "success"
                          ? "text-green-600"
                          : "text-red-600"
                      }
                    >
                      {w.last_status === "success" ? "成功" : "失败"}
                    </span>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 ml-4">
                <button
                  onClick={() => runMutation.mutate(w.id)}
                  className="p-2 text-gray-500 hover:text-green-600"
                  title="立即运行"
                >
                  <Play size={16} />
                </button>
                <button
                  onClick={() => setViewingRuns(w.id)}
                  className="p-2 text-gray-500 hover:text-blue-600"
                  title="查看运行记录"
                >
                  <Clock size={16} />
                </button>
                <button
                  onClick={() => startEdit(w)}
                  className="p-2 text-gray-500 hover:text-gray-700"
                  title="编辑"
                >
                  <Edit2 size={16} />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(w.id)}
                  className="p-2 text-gray-500 hover:text-red-600"
                  title="删除"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          </div>
        ))}
        {workflows?.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            尚未配置任何工作流。添加工作流以自动化处理流程。
          </div>
        )}
      </div>
    </div>
  );
}
