"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import {
  FileText, RefreshCw, Settings, Eye, Code,
  Plus, Trash2, Edit2, Ban, Loader2,
  Send, ChevronDown, ChevronUp, Bell,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const CHANNEL_TYPES = [
  { value: "feishu", label: "飞书", icon: "📩" },
  { value: "wechat_work", label: "企业微信", icon: "💬" },
  { value: "dingtalk", label: "钉钉", icon: "🔔" },
  { value: "slack", label: "Slack", icon: "💜" },
  { value: "discord", label: "Discord", icon: "🎮" },
  { value: "custom_webhook", label: "自定义 Webhook", icon: "🔗" },
  { value: "email", label: "邮件", icon: "📧" },
];

export default function DigestsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showChannelManager, setShowChannelManager] = useState(false);
  const [viewMode, setViewMode] = useState<"rendered" | "raw">("rendered");
  const [showSendMenu, setShowSendMenu] = useState(false);
  const [selectedChannels, setSelectedChannels] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();

  const { data: digests, isLoading } = useQuery({
    queryKey: ["digests"],
    queryFn: () => api.get("/api/digests"),
  });

  const { data: channels } = useQuery({
    queryKey: ["notification-channels"],
    queryFn: () => api.get("/api/notification-channels"),
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

  const sendMutation = useMutation({
    mutationFn: ({ digestId, channelIds }: { digestId: string; channelIds: string[] }) =>
      api.post(`/api/notification-channels/digests/${digestId}/send`, { channel_ids: channelIds }),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["digests"] });
      setShowSendMenu(false);
      setSelectedChannels(new Set());
      const results = data.results || [];
      const failed = results.filter((r: any) => !r.success);
      if (failed.length === 0) {
        alert(`已发送到 ${results.length} 个渠道！`);
      } else {
        alert(`发送完成：${results.length - failed.length} 成功，${failed.length} 失败\n${failed.map((f: any) => `${f.channel_id}: ${f.error}`).join("\n")}`);
      }
    },
    onError: (error: Error) => {
      alert(`发送失败: ${error.message}`);
    },
  });

  const handleSend = () => {
    if (!selectedDigest || selectedChannels.size === 0) return;
    sendMutation.mutate({
      digestId: selectedDigest.id,
      channelIds: Array.from(selectedChannels),
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">每日摘要</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowChannelManager(!showChannelManager)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-md text-sm ${
              showChannelManager ? "bg-gray-100" : "hover:bg-gray-50"
            }`}
          >
            <Bell size={16} />
            发送渠道
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

      {showChannelManager && <ChannelManager channels={channels} />}

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
                  onClick={() => { setSelectedId(d.id); setShowSendMenu(false); setSelectedChannels(new Set()); }}
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

                  <div className="relative">
                    <button
                      onClick={() => setShowSendMenu(!showSendMenu)}
                      disabled={sendMutation.isPending}
                      className="flex items-center gap-2 px-4 py-1.5 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
                    >
                      <Send size={14} />
                      发送
                      {showSendMenu ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {showSendMenu && (
                      <div className="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-10 min-w-[280px]">
                        <div className="p-3 border-b">
                          <p className="text-sm font-medium">选择发送渠道</p>
                        </div>
                        <div className="max-h-[300px] overflow-y-auto">
                          {channels?.filter((c: any) => c.enabled).length === 0 && (
                            <div className="p-4 text-center text-gray-400 text-sm">
                              暂无可用的发送渠道
                            </div>
                          )}
                          {channels?.filter((c: any) => c.enabled).map((c: any) => {
                            const typeInfo = CHANNEL_TYPES.find((t) => t.value === c.channel_type);
                            const isChecked = selectedChannels.has(c.id);
                            return (
                              <label
                                key={c.id}
                                className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={(e) => {
                                    const next = new Set(selectedChannels);
                                    if (e.target.checked) next.add(c.id);
                                    else next.delete(c.id);
                                    setSelectedChannels(next);
                                  }}
                                  className="w-4 h-4"
                                />
                                <span className="text-lg">{typeInfo?.icon}</span>
                                <div className="flex-1">
                                  <div className="text-sm font-medium">{c.alias}</div>
                                  <div className="text-xs text-gray-400">{typeInfo?.label}</div>
                                </div>
                              </label>
                            );
                          })}
                        </div>
                        <div className="p-3 border-t flex justify-end gap-2">
                          <button
                            onClick={() => { setShowSendMenu(false); setSelectedChannels(new Set()); }}
                            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
                          >
                            取消
                          </button>
                          <button
                            onClick={handleSend}
                            disabled={selectedChannels.size === 0 || sendMutation.isPending}
                            className="px-4 py-1.5 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50 flex items-center gap-1"
                          >
                            {sendMutation.isPending ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <Send size={14} />
                            )}
                            发送到 {selectedChannels.size} 个渠道
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
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

function ChannelManager({ channels }: { channels?: any[] }) {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [form, setForm] = useState({
    alias: "",
    name: "",
    channel_type: "",
    enabled: true,
    send_on_digest_generated: false,
    config_json: {} as Record<string, any>,
  });
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/api/notification-channels", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-channels"] });
      setShowForm(false);
      setSelectedType(null);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/notification-channels/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-channels"] });
      setEditingId(null);
      setShowForm(false);
      setSelectedType(null);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/notification-channels/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-channels"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/api/notification-channels/${id}`, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-channels"] });
    },
  });

  const resetForm = () =>
    setForm({
      alias: "",
      name: "",
      channel_type: "",
      enabled: true,
      send_on_digest_generated: false,
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

  const startEdit = (c: any) => {
    setEditingId(c.id);
    setSelectedType(c.channel_type);
    setForm({
      alias: c.alias,
      name: c.name,
      channel_type: c.channel_type,
      enabled: c.enabled,
      send_on_digest_generated: c.send_on_digest_generated,
      config_json: c.config_json || {},
    });
    setShowForm(true);
  };

  const handleTypeSelect = (type: string) => {
    setSelectedType(type);
    setForm({ ...form, channel_type: type, alias: `${type}_${Date.now().toString(36)}` });
  };

  if (!showForm) {
    return (
      <div className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">发送渠道管理</h2>
          <button
            onClick={() => { resetForm(); setEditingId(null); setShowForm(true); setSelectedType(null); }}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
          >
            <Plus size={14} />
            添加渠道
          </button>
        </div>
        <div className="space-y-2">
          {channels?.map((c: any) => {
            const typeInfo = CHANNEL_TYPES.find((t) => t.value === c.channel_type);
            return (
              <div
                key={c.id}
                className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{typeInfo?.icon}</span>
                    <span className="font-medium">{c.alias}</span>
                    <span className="text-xs text-gray-400">({typeInfo?.label})</span>
                    {c.enabled ? (
                      <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">已启用</span>
                    ) : (
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full text-xs">已禁用</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {c.send_on_digest_generated ? "自动生成后发送" : "手动发送"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggleMutation.mutate({ id: c.id, enabled: !c.enabled })}
                    className="p-1.5 hover:text-gray-700"
                    title={c.enabled ? "禁用" : "启用"}
                  >
                    <Ban size={16} className={c.enabled ? "text-gray-400" : "text-red-500"} />
                  </button>
                  <button
                    onClick={() => startEdit(c)}
                    className="p-1.5 text-gray-400 hover:text-gray-700"
                    title="编辑"
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(c.id)}
                    className="p-1.5 text-gray-400 hover:text-red-600"
                    title="删除"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
          {channels?.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-sm">
              尚未配置发送渠道。点击"添加渠道"开始配置。
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">
          {editingId ? "编辑渠道" : selectedType ? "配置渠道" : "选择渠道类型"}
        </h2>
        <button
          onClick={() => { setShowForm(false); setSelectedType(null); setEditingId(null); resetForm(); }}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          关闭
        </button>
      </div>

      {!selectedType && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {CHANNEL_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => handleTypeSelect(t.value)}
              className="flex flex-col items-center gap-2 p-4 border rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-colors"
            >
              <span className="text-2xl">{t.icon}</span>
              <span className="text-sm font-medium">{t.label}</span>
            </button>
          ))}
        </div>
      )}

      {selectedType && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">唯一标识 (alias) *</label>
              <input
                type="text" required value={form.alias}
                onChange={(e) => setForm({ ...form, alias: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm font-mono"
                placeholder="例如: feishu-daily"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">显示名称 *</label>
              <input
                type="text" required value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="例如: AI日报群"
              />
            </div>
          </div>

          <ChannelConfigForm
            type={selectedType}
            config={form.config_json}
            onChange={(config) => setForm({ ...form, config_json: config })}
          />

          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox" checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              启用
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox" checked={form.send_on_digest_generated}
                onChange={(e) => setForm({ ...form, send_on_digest_generated: e.target.checked })}
              />
              生成后自动发送
            </label>
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
            >
              {editingId ? "更新" : "创建"}
            </button>
            <button
              type="button"
              onClick={() => { setSelectedType(null); setEditingId(null); resetForm(); }}
              className="px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
            >
              返回
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function ChannelConfigForm({
  type,
  config,
  onChange,
}: {
  type: string;
  config: Record<string, any>;
  onChange: (config: Record<string, any>) => void;
}) {
  const set = (key: string, value: any) => onChange({ ...config, [key]: value });

  const commonFields = (
    <div>
      <label className="block text-sm font-medium mb-1">消息标题</label>
      <input
        type="text" value={config.message_title || "每日摘要"}
        onChange={(e) => set("message_title", e.target.value)}
        className="w-full px-3 py-2 border rounded-md text-sm"
      />
    </div>
  );

  const webhookFields = (
    <div>
      <label className="block text-sm font-medium mb-1">Webhook URL *</label>
      <input
        type="text" required value={config.webhook_url || ""}
        onChange={(e) => set("webhook_url", e.target.value)}
        className="w-full px-3 py-2 border rounded-md text-sm font-mono"
        placeholder="https://..."
      />
    </div>
  );

  const signSecretField = (
    <div>
      <label className="block text-sm font-medium mb-1">校验签名 / Secret</label>
      <input
        type="password" value={config.sign_secret || ""}
        onChange={(e) => set("sign_secret", e.target.value)}
        className="w-full px-3 py-2 border rounded-md text-sm font-mono"
        placeholder="可选，用于签名验证"
      />
    </div>
  );

  switch (type) {
    case "feishu":
      return (
        <div className="space-y-4">
          {webhookFields}
          {signSecretField}
          {commonFields}
          <div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox" checked={config.include_source_links ?? true}
                onChange={(e) => set("include_source_links", e.target.checked)}
              />
              包含原文链接
            </label>
          </div>
        </div>
      );

    case "wechat_work":
      return (
        <div className="space-y-4">
          {webhookFields}
          {commonFields}
        </div>
      );

    case "dingtalk":
      return (
        <div className="space-y-4">
          {webhookFields}
          {signSecretField}
          {commonFields}
        </div>
      );

    case "slack":
      return (
        <div className="space-y-4">
          {webhookFields}
          <div>
            <label className="block text-sm font-medium mb-1">Channel (可选)</label>
            <input
              type="text" value={config.channel || ""}
              onChange={(e) => set("channel", e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm"
              placeholder="#general"
            />
          </div>
          {commonFields}
        </div>
      );

    case "discord":
      return (
        <div className="space-y-4">
          {webhookFields}
          {commonFields}
        </div>
      );

    case "custom_webhook":
      return (
        <div className="space-y-4">
          {webhookFields}
          <div>
            <label className="block text-sm font-medium mb-1">HTTP 方法</label>
            <select
              value={config.method || "POST"}
              onChange={(e) => set("method", e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm"
            >
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="PATCH">PATCH</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Headers (JSON)</label>
            <textarea
              value={JSON.stringify(config.headers_json || {}, null, 2)}
              onChange={(e) => {
                try { set("headers_json", JSON.parse(e.target.value)); } catch {}
              }}
              className="w-full px-3 py-2 border rounded-md text-sm font-mono"
              rows={3}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Body 模板</label>
            <textarea
              value={config.body_template || '{"content": "{content}"}'}
              onChange={(e) => set("body_template", e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm font-mono"
              rows={4}
            />
            <p className="text-xs text-gray-400 mt-1">
              可用变量: {"{content}"}, {"{digest_date}"}, {"{item_count}"}, {"{title}"}
            </p>
          </div>
        </div>
      );

    case "email": {
      const recipientsInput = (config.recipients || []).join(", ");
      const ccRecipientsInput = (config.cc_recipients || []).join(", ");
      const parseEmails = (val: string) => val.split(",").map((s: string) => s.trim()).filter(Boolean);

      return (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">SMTP 服务器 *</label>
              <input
                type="text" required value={config.smtp_host || ""}
                onChange={(e) => set("smtp_host", e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm font-mono"
                placeholder="smtp.example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">SMTP 端口</label>
              <input
                type="number" value={config.smtp_port || 587}
                onChange={(e) => set("smtp_port", parseInt(e.target.value))}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">发件人邮箱 *</label>
              <input
                type="email" required value={config.sender_email || ""}
                onChange={(e) => set("sender_email", e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">发件人名称</label>
              <input
                type="text" value={config.sender_name || "每日摘要"}
                onChange={(e) => set("sender_name", e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">邮箱密码/授权码 *</label>
              <input
                type="password" required value={config.sender_password || ""}
                onChange={(e) => set("sender_password", e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="密码或授权码"
              />
            </div>
            <div>
              <label className="flex items-center gap-2 text-sm pt-6">
                <input
                  type="checkbox" checked={config.use_tls ?? true}
                  onChange={(e) => set("use_tls", e.target.checked)}
                />
                使用 TLS
              </label>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">收件人邮箱 *</label>
            <input
              type="text" required
              defaultValue={recipientsInput}
              onBlur={(e) => set("recipients", parseEmails(e.target.value))}
              onKeyDown={(e) => { if (e.key === "Enter") set("recipients", parseEmails((e.target as HTMLInputElement).value)) }}
              className="w-full px-3 py-2 border rounded-md text-sm font-mono"
              placeholder="a@example.com, b@example.com"
            />
            <p className="text-xs text-gray-400 mt-1">多个邮箱用逗号分隔，输入完成后按回车或点击别处保存</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">抄送邮箱</label>
            <input
              type="text"
              defaultValue={ccRecipientsInput}
              onBlur={(e) => set("cc_recipients", parseEmails(e.target.value))}
              onKeyDown={(e) => { if (e.key === "Enter") set("cc_recipients", parseEmails((e.target as HTMLInputElement).value)) }}
              className="w-full px-3 py-2 border rounded-md text-sm font-mono"
              placeholder="cc@example.com"
            />
            <p className="text-xs text-gray-400 mt-1">多个邮箱用逗号分隔（可选），输入完成后按回车或点击别处保存</p>
          </div>
        </div>
      );
    }

    default:
      return null;
  }
}
