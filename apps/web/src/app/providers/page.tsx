"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Plus, Trash2, Edit2, TestTube, Eye, EyeOff } from "lucide-react";

export default function ProvidersPage() {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, any>>({});
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({});
  const queryClient = useQueryClient();

  const { data: providers } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.get("/api/providers"),
  });

  const [form, setForm] = useState({
    name: "",
    base_url: "",
    api_key: "",
    default_model: "",
    enabled: true,
    request_timeout: 30,
    max_retries: 3,
    is_default_for_relevance: false,
    is_default_for_extraction: false,
    is_default_for_digest: false,
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/api/providers", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      setShowForm(false);
      resetForm();
    },
    onError: (error: Error) => {
      alert(`创建失败: ${error.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/providers/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      setEditingId(null);
      resetForm();
    },
    onError: (error: Error) => {
      alert(`更新失败: ${error.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/providers/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
    onError: (error: Error) => {
      alert(`删除失败: ${error.message}`);
    },
  });

  const testMutation = useMutation({
    mutationFn: ({ id, prompt }: { id: string; prompt: string }) =>
      api.post(`/api/providers/${id}/test`, { prompt }),
    onSuccess: (data, vars) => {
      setTestResult((prev) => ({ ...prev, [vars.id]: data }));
    },
    onError: (error: Error) => {
      alert(`测试失败: ${error.message}`);
    },
  });

  const resetForm = () =>
    setForm({
      name: "",
      base_url: "",
      api_key: "",
      default_model: "",
      enabled: true,
      request_timeout: 30,
      max_retries: 3,
      is_default_for_relevance: false,
      is_default_for_extraction: false,
      is_default_for_digest: false,
    });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: form });
    } else {
      createMutation.mutate(form);
    }
  };

  const startEdit = (p: any) => {
    setEditingId(p.id);
    setForm({
      name: p.name,
      base_url: p.base_url,
      api_key: "",
      default_model: p.default_model,
      enabled: p.enabled,
      request_timeout: p.request_timeout,
      max_retries: p.max_retries,
      is_default_for_relevance: p.is_default_for_relevance,
      is_default_for_extraction: p.is_default_for_extraction,
      is_default_for_digest: p.is_default_for_digest,
    });
    setShowForm(true);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">模型配置</h1>
        <button
          onClick={() => {
            resetForm();
            setEditingId(null);
            setShowForm(!showForm);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
        >
          <Plus size={16} />
          {showForm ? "取消" : "添加提供商"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-lg border p-6 mb-6 shadow-sm"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                提供商名称 *
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="例如: OpenAI, DeepSeek, SiliconFlow"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Base URL *
              </label>
              <input
                type="text"
                required
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                API Key *
              </label>
              <input
                type="text"
                required={!editingId}
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder={editingId ? "留空保持当前值" : "sk-..."}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                默认模型 *
              </label>
              <input
                type="text"
                required
                value={form.default_model}
                onChange={(e) =>
                  setForm({ ...form, default_model: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="gpt-4o"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                超时时间（秒）
              </label>
              <input
                type="number"
                value={form.request_timeout}
                onChange={(e) =>
                  setForm({ ...form, request_timeout: parseInt(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                最大重试次数
              </label>
              <input
                type="number"
                value={form.max_retries}
                onChange={(e) =>
                  setForm({ ...form, max_retries: parseInt(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-4 mb-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              启用
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_default_for_relevance}
                onChange={(e) =>
                  setForm({ ...form, is_default_for_relevance: e.target.checked })
                }
              />
              相关性默认
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_default_for_extraction}
                onChange={(e) =>
                  setForm({ ...form, is_default_for_extraction: e.target.checked })
                }
              />
              提取默认
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_default_for_digest}
                onChange={(e) =>
                  setForm({ ...form, is_default_for_digest: e.target.checked })
                }
              />
              摘要默认
            </label>
          </div>

          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            {editingId ? "更新" : "创建"}
          </button>
        </form>
      )}

      <div className="space-y-4">
        {providers?.map((p: any) => (
          <div
            key={p.id}
            className="bg-white rounded-lg border p-5 shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold text-lg">{p.name}</h3>
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs ${
                      p.enabled
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {p.enabled ? "已启用" : "已禁用"}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm text-gray-600">
                  <p>
                    <span className="text-gray-400">Base URL:</span>{" "}
                    {p.base_url}
                  </p>
                  <p>
                    <span className="text-gray-400">模型:</span>{" "}
                    {p.default_model}
                  </p>
                  <p>
                    <span className="text-gray-400">API Key:</span>{" "}
                    <button
                      onClick={() =>
                        setShowApiKey((prev) => ({
                          ...prev,
                          [p.id]: !prev[p.id],
                        }))
                      }
                      className="inline-flex items-center gap-1"
                    >
                      {showApiKey[p.id] ? p.api_key_masked : "****"}
                      {showApiKey[p.id] ? (
                        <EyeOff size={12} />
                      ) : (
                        <Eye size={12} />
                      )}
                    </button>
                  </p>
                  <p>
                    <span className="text-gray-400">超时:</span>{" "}
                    {p.request_timeout}s / 重试: {p.max_retries}
                  </p>
                </div>
                {p.last_test_status && (
                  <div className="mt-2 text-sm">
                    <span className="text-gray-400">最近测试:</span>{" "}
                    <span
                      className={
                        p.last_test_status === "success"
                          ? "text-green-600"
                          : "text-red-600"
                      }
                    >
                      {p.last_test_status === "success" ? "成功" : "失败"}
                    </span>
                    {p.last_test_message && (
                      <span className="ml-2 text-gray-500">
                        {p.last_test_message}
                      </span>
                    )}
                  </div>
                )}
                <div className="flex flex-wrap gap-2 mt-2">
                  {p.is_default_for_relevance && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs">
                      相关性
                    </span>
                  )}
                  {p.is_default_for_extraction && (
                    <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs">
                      提取
                    </span>
                  )}
                  {p.is_default_for_digest && (
                    <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs">
                      摘要
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 ml-4">
                <button
                  onClick={() => testMutation.mutate({ id: p.id, prompt: "Say hello" })}
                  className="p-2 text-gray-500 hover:text-blue-600"
                  title="测试连接"
                >
                  <TestTube size={16} />
                </button>
                <button
                  onClick={() => startEdit(p)}
                  className="p-2 text-gray-500 hover:text-gray-700"
                  title="编辑"
                >
                  <Edit2 size={16} />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(p.id)}
                  className="p-2 text-gray-500 hover:text-red-600"
                  title="删除"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
            {testResult[p.id] && (
              <div
                className={`mt-3 p-3 rounded text-sm ${
                  testResult[p.id].success
                    ? "bg-green-50 text-green-700"
                    : "bg-red-50 text-red-700"
                }`}
              >
                {testResult[p.id].success ? (
                  <p>
                    测试通过 ({testResult[p.id].latency_ms}ms):{" "}
                    {testResult[p.id].response}
                  </p>
                ) : (
                  <p>测试失败: {testResult[p.id].error}</p>
                )}
              </div>
            )}
          </div>
        ))}
        {providers?.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            尚未配置任何提供商。添加一个以开始使用。
          </div>
        )}
      </div>
    </div>
  );
}
