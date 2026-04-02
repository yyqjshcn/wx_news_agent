"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import {
  FileText, Download, Send, RefreshCw, Settings, Eye, Code,
  Plus, Trash2, Edit2, CheckCircle, XCircle, Loader2,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function DigestsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [viewMode, setViewMode] = useState<"rendered" | "raw">("rendered");
  const queryClient = useQueryClient();

  const { data: digests, isLoading } = useQuery({
    queryKey: ["digests"],
    queryFn: () => api.get("/api/digests"),
  });

  const { data: webhooks } = useQuery({
    queryKey: ["feishu-webhooks"],
    queryFn: () => api.get("/api/feishu-webhooks"),
  });

  const { data: selectedDigest } = useQuery({
    queryKey: ["digest", selectedId],
    queryFn: () => api.get(`/api/digests/${selectedId}`),
    enabled: !!selectedId,
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      api.post("/api/digests/generate", { digest_date: new Date().toISOString() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["digests"] });
    },
    onError: (error: Error) => {
      alert(`生成失败: ${error.message}`);
    },
  });

  const sendToFeishuMutation = useMutation({
    mutationFn: ({ webhookId, digestId }: { webhookId: string; digestId: string }) =>
      api.post("/api/feishu-webhooks/send-digest", { webhook_id: webhookId, digest_id: digestId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["digests"] });
      alert("已发送到飞书！");
    },
    onError: (error: Error) => {
      alert(`发送失败: ${error.message}`);
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">每日摘要</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="flex items-center gap-2 px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
          >
            <Settings size={16} />
            飞书设置
          </button>
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            <RefreshCw
              size={16}
              className={generateMutation.isPending ? "animate-spin" : ""}
            />
            生成今日摘要
          </button>
        </div>
      </div>

      {showSettings && <FeishuSettings webhooks={webhooks} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border shadow-sm">
            <div className="p-4 border-b">
              <h2 className="font-semibold">历史记录</h2>
            </div>
            <div className="divide-y max-h-[600px] overflow-y-auto">
              {isLoading && (
                <div className="p-4 text-center text-gray-400">加载中...</div>
              )}
              {digests?.map((d: any) => (
                <button
                  key={d.id}
                  onClick={() => setSelectedId(d.id)}
                  className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                    selectedId === d.id ? "bg-gray-50" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText size={16} className="text-gray-400" />
                      <span className="text-sm font-medium">
                        {new Date(d.digest_date).toLocaleDateString()}
                      </span>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs ${
                        d.status === "sent"
                          ? "bg-green-100 text-green-700"
                          : d.status === "draft"
                          ? "bg-gray-100 text-gray-500"
                          : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {d.status === "sent" ? "已发送" : d.status === "draft" ? "草稿" : d.status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {d.item_count} 条
                  </div>
                </button>
              ))}
              {digests?.length === 0 && !isLoading && (
                <div className="p-8 text-center text-gray-400 text-sm">
                  尚未生成任何摘要
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          {selectedDigest ? (
            <div className="bg-white rounded-lg border shadow-sm">
              <div className="p-4 border-b flex items-center justify-between">
                <h2 className="font-semibold">
                  {new Date(selectedDigest.digest_date).toLocaleDateString()}
                </h2>
                <div className="flex gap-2 items-center">
                  <div className="flex border rounded-md overflow-hidden">
                    <button
                      onClick={() => setViewMode("rendered")}
                      className={`flex items-center gap-1 px-3 py-1.5 text-sm ${
                        viewMode === "rendered"
                          ? "bg-gray-900 text-white"
                          : "hover:bg-gray-50"
                      }`}
                    >
                      <Eye size={14} />
                      渲染
                    </button>
                    <button
                      onClick={() => setViewMode("raw")}
                      className={`flex items-center gap-1 px-3 py-1.5 text-sm ${
                        viewMode === "raw"
                          ? "bg-gray-900 text-white"
                          : "hover:bg-gray-50"
                      }`}
                    >
                      <Code size={14} />
                      源码
                    </button>
                  </div>

                  {webhooks?.filter((w: any) => w.enabled).length > 0 && (
                    <div className="flex gap-1">
                      {webhooks
                        ?.filter((w: any) => w.enabled)
                        .map((w: any) => (
                          <button
                            key={w.id}
                            onClick={() =>
                              sendToFeishuMutation.mutate({
                                webhookId: w.id,
                                digestId: selectedDigest.id,
                              })
                            }
                            disabled={sendToFeishuMutation.isPending}
                            className="flex items-center gap-1 px-3 py-1.5 bg-[#3370FF] text-white rounded-md text-sm hover:bg-[#2B5FE6] disabled:opacity-50"
                            title={`发送到飞书: ${w.name}`}
                          >
                            <Send size={14} />
                            {w.name}
                          </button>
                        ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="p-6">
                {viewMode === "rendered" ? (
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {selectedDigest.content_markdown || "暂无内容"}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-lg font-mono">
                    {selectedDigest.content_markdown || "暂无内容"}
                  </pre>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg border shadow-sm flex items-center justify-center h-96 text-gray-400">
              请选择一个摘要查看
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FeishuSettings({ webhooks }: { webhooks?: any[] }) {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    webhook_url: "",
    message_title: "每日摘要",
    include_source_links: true,
    send_on_digest_generated: false,
    enabled: true,
  });
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/api/feishu-webhooks", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feishu-webhooks"] });
      setShowForm(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/feishu-webhooks/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feishu-webhooks"] });
      setEditingId(null);
      setShowForm(false);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/feishu-webhooks/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feishu-webhooks"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/api/feishu-webhooks/${id}`, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feishu-webhooks"] });
    },
  });

  const resetForm = () =>
    setForm({
      name: "",
      webhook_url: "",
      message_title: "每日摘要",
      include_source_links: true,
      send_on_digest_generated: false,
      enabled: true,
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
      name: w.name,
      webhook_url: w.webhook_url,
      message_title: w.message_title || "每日摘要",
      include_source_links: w.include_source_links ?? true,
      send_on_digest_generated: w.send_on_digest_generated ?? false,
      enabled: w.enabled,
    });
    setShowForm(true);
  };

  return (
    <div className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">飞书机器人配置</h2>
        <button
          onClick={() => {
            resetForm();
            setEditingId(null);
            setShowForm(!showForm);
          }}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
        >
          <Plus size={14} />
          {showForm ? "取消" : "添加机器人"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="space-y-4 mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">名称 *</label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="例如: AI日报群"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Webhook URL *</label>
              <input
                type="text"
                required
                value={form.webhook_url}
                onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm font-mono"
                placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">消息标题</label>
              <input
                type="text"
                value={form.message_title}
                onChange={(e) => setForm({ ...form, message_title: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div className="flex items-center gap-6 pt-6">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.include_source_links}
                  onChange={(e) =>
                    setForm({ ...form, include_source_links: e.target.checked })
                  }
                />
                包含原文链接
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.send_on_digest_generated}
                  onChange={(e) =>
                    setForm({ ...form, send_on_digest_generated: e.target.checked })
                  }
                />
                生成后自动发送
              </label>
            </div>
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

      <div className="space-y-2">
        {webhooks?.map((w: any) => (
          <div
            key={w.id}
            className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{w.name}</span>
                {w.enabled ? (
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                    已启用
                  </span>
                ) : (
                  <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full text-xs">
                    已禁用
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-400 mt-1 font-mono truncate max-w-md">
                {w.webhook_url}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                标题: {w.message_title} · {w.include_source_links ? "含链接" : "不含链接"}
                {w.send_on_digest_generated ? " · 自动生成后发送" : ""}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => toggleMutation.mutate({ id: w.id, enabled: !w.enabled })}
                className="p-1.5 text-gray-400 hover:text-gray-700"
                title={w.enabled ? "禁用" : "启用"}
              >
                {w.enabled ? <CheckCircle size={16} /> : <XCircle size={16} />}
              </button>
              <button
                onClick={() => startEdit(w)}
                className="p-1.5 text-gray-400 hover:text-gray-700"
                title="编辑"
              >
                <Edit2 size={14} />
              </button>
              <button
                onClick={() => deleteMutation.mutate(w.id)}
                className="p-1.5 text-gray-400 hover:text-red-600"
                title="删除"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
        {webhooks?.length === 0 && (
          <div className="text-center py-8 text-gray-400 text-sm">
            尚未配置飞书机器人。点击"添加机器人"开始配置。
          </div>
        )}
      </div>
    </div>
  );
}
