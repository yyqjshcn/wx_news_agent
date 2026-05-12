"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import {
  FileText, RefreshCw, Settings, Eye, Code,
  Plus, Trash2, Edit2, Ban, Loader2,
  Send, ChevronDown, ChevronUp, Bell,
  Search, Calendar, X, Check, SlidersHorizontal,
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

  const [showCustomModal, setShowCustomModal] = useState(false);
  const [customTab, setCustomTab] = useState<"date" | "articles">("date");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [selectedArticleIds, setSelectedArticleIds] = useState<Set<string>>(new Set());
  const [articleSearch, setArticleSearch] = useState("");
  const [articlePage, setArticlePage] = useState(0);
  const [previewResult, setPreviewResult] = useState<any>(null);

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

  const { data: articleSearchResult } = useQuery({
    queryKey: ["articles-search", articleSearch, articlePage],
    queryFn: () =>
      api.get(
        `/api/articles?query=${encodeURIComponent(articleSearch)}&is_relevant=true&limit=30&skip=${articlePage * 30}`
      ),
    enabled: showCustomModal && customTab === "articles" && articleSearch.length >= 1,
    placeholderData: (prev: any) => prev,
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

  const customGenerateMutation = useMutation({
    mutationFn: (payload: any) => api.post("/api/digests/generate", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["digests"] });
      setShowCustomModal(false);
      setPreviewResult(null);
    },
    onError: (error: Error) => {
      alert(`生成失败: ${error.message}`);
    },
  });

  const previewMutation = useMutation({
    mutationFn: (payload: any) => api.post("/api/digests/preview", payload),
    onSuccess: (data: any) => {
      setPreviewResult(data);
    },
    onError: (error: Error) => {
      alert(`预览失败: ${error.message}`);
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
          <button
            onClick={() => {
              setShowCustomModal(true);
              setPreviewResult(null);
              setSelectedArticleIds(new Set());
              setArticleSearch("");
              setArticlePage(0);
            }}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
          >
            <SlidersHorizontal size={16} />
            自定义生成
          </button>
        </div>
      </div>

      <CustomDigestModal
        open={showCustomModal}
        onClose={() => setShowCustomModal(false)}
        tab={customTab}
        onTabChange={setCustomTab}
        dateStart={dateStart}
        onDateStartChange={setDateStart}
        dateEnd={dateEnd}
        onDateEndChange={setDateEnd}
        selectedArticleIds={selectedArticleIds}
        onToggleArticle={(id) => {
          const next = new Set(selectedArticleIds);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          setSelectedArticleIds(next);
        }}
        articleSearch={articleSearch}
        onArticleSearchChange={(v) => { setArticleSearch(v); setArticlePage(0); }}
        articlePage={articlePage}
        onArticlePageChange={setArticlePage}
        articleSearchResult={articleSearchResult}
        previewResult={previewResult}
        onPreview={() => {
          const payload: any = {};
          if (customTab === "date") {
            payload.date_start = dateStart ? new Date(dateStart).toISOString() : undefined;
            payload.date_end = dateEnd ? new Date(dateEnd + "T23:59:59").toISOString() : undefined;
          } else {
            payload.article_ids = Array.from(selectedArticleIds);
          }
          previewMutation.mutate(payload);
        }}
        isPreviewing={previewMutation.isPending}
        onGenerate={() => {
          const payload: any = {};
          if (customTab === "date") {
            payload.date_start = dateStart ? new Date(dateStart).toISOString() : undefined;
            payload.date_end = dateEnd ? new Date(dateEnd + "T23:59:59").toISOString() : undefined;
          } else {
            payload.article_ids = Array.from(selectedArticleIds);
          }
          customGenerateMutation.mutate(payload);
        }}
        isGenerating={customGenerateMutation.isPending}
      />

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
            <label className="block text-sm font-medium mb-1">邮件模板</label>
            <select
              value={config.template || "email"}
              onChange={(e) => set("template", e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm"
            >
              <option value="email">默认模板（世界模型与具身智能）</option>
            </select>
            <p className="text-xs text-gray-400 mt-1">在 apps/api/templates/ 目录下创建自定义 HTML 模板文件</p>
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

interface CustomDigestModalProps {
  open: boolean;
  onClose: () => void;
  tab: "date" | "articles";
  onTabChange: (tab: "date" | "articles") => void;
  dateStart: string;
  onDateStartChange: (v: string) => void;
  dateEnd: string;
  onDateEndChange: (v: string) => void;
  selectedArticleIds: Set<string>;
  onToggleArticle: (id: string) => void;
  articleSearch: string;
  onArticleSearchChange: (v: string) => void;
  articlePage: number;
  onArticlePageChange: (p: number) => void;
  articleSearchResult: any;
  previewResult: any;
  onPreview: () => void;
  isPreviewing: boolean;
  onGenerate: () => void;
  isGenerating: boolean;
}

function CustomDigestModal({
  open, onClose, tab, onTabChange,
  dateStart, onDateStartChange, dateEnd, onDateEndChange,
  selectedArticleIds, onToggleArticle,
  articleSearch, onArticleSearchChange,
  articlePage, onArticlePageChange,
  articleSearchResult, previewResult,
  onPreview, isPreviewing, onGenerate, isGenerating,
}: CustomDigestModalProps) {
  if (!open) return null;

  const canGenerate = tab === "date"
    ? dateStart && dateEnd
    : selectedArticleIds.size > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b">
          <h2 className="text-lg font-semibold">自定义摘要生成</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X size={18} />
          </button>
        </div>

        <div className="flex border-b px-5">
          {(["date", "articles"] as const).map((t) => (
            <button
              key={t}
              onClick={() => onTabChange(t)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t === "date" ? (
                <span className="flex items-center gap-1.5"><Calendar size={14} />按日期范围</span>
              ) : (
                <span className="flex items-center gap-1.5"><Search size={14} />按文章选择</span>
              )}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {tab === "date" && (
            <div className="space-y-4">
              <p className="text-sm text-gray-500">
                选择日期范围，系统将包含该范围内的所有相关事件和文章。
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">开始日期</label>
                  <input
                    type="date"
                    value={dateStart}
                    onChange={(e) => onDateStartChange(e.target.value)}
                    className="w-full px-3 py-2 border rounded-md text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">结束日期</label>
                  <input
                    type="date"
                    value={dateEnd}
                    onChange={(e) => onDateEndChange(e.target.value)}
                    min={dateStart || undefined}
                    className="w-full px-3 py-2 border rounded-md text-sm"
                  />
                </div>
              </div>
            </div>
          )}

          {tab === "articles" && (
            <div className="space-y-4">
              <p className="text-sm text-gray-500">
                搜索并选择文章，系统将包含选中文章对应的所有事件。
              </p>
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={articleSearch}
                  onChange={(e) => onArticleSearchChange(e.target.value)}
                  placeholder="搜索文章标题..."
                  className="w-full pl-9 pr-3 py-2 border rounded-md text-sm"
                />
              </div>

              {selectedArticleIds.size > 0 && (
                <div className="text-sm text-gray-600">
                  已选择 <span className="font-semibold text-gray-900">{selectedArticleIds.size}</span> 篇文章
                </div>
              )}

              <div className="border rounded-md divide-y max-h-60 overflow-y-auto">
                {!articleSearch && (
                  <div className="p-4 text-center text-gray-400 text-sm">
                    请输入关键词搜索文章
                  </div>
                )}
                {articleSearchResult?.length === 0 && articleSearch && (
                  <div className="p-4 text-center text-gray-400 text-sm">
                    未找到匹配的文章
                  </div>
                )}
                {articleSearchResult?.map((article: any) => (
                  <label
                    key={article.id}
                    className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedArticleIds.has(article.id)}
                      onChange={() => onToggleArticle(article.id)}
                      className="mt-0.5 w-4 h-4"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{article.title}</div>
                      <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-400">
                        <span>{article.account_name}</span>
                        <span>{article.publish_time ? new Date(article.publish_time).toLocaleDateString() : "-"}</span>
                        {article.linked_events?.length > 0 && (
                          <span className="text-blue-500">
                            {article.linked_events.map((e: any) => e.title).join(", ")}
                          </span>
                        )}
                      </div>
                    </div>
                  </label>
                ))}
              </div>

              {articleSearchResult?.length > 0 && (
                <div className="flex justify-center gap-2">
                  <button
                    onClick={() => onArticlePageChange(Math.max(0, articlePage - 1))}
                    disabled={articlePage === 0}
                    className="px-3 py-1 border rounded text-sm disabled:opacity-30"
                  >
                    上一页
                  </button>
                  <span className="px-3 py-1 text-sm text-gray-500">第 {articlePage + 1} 页</span>
                  <button
                    onClick={() => onArticlePageChange(articlePage + 1)}
                    disabled={articleSearchResult.length < 30}
                    className="px-3 py-1 border rounded text-sm disabled:opacity-30"
                  >
                    下一页
                  </button>
                </div>
              )}
            </div>
          )}

          {previewResult && (
            <div className="mt-6 p-4 bg-gray-50 rounded-lg border">
              <h3 className="text-sm font-semibold mb-2">预览结果</h3>
              <div className="flex gap-4 text-sm text-gray-600 mb-3">
                <span>事件数: <strong className="text-gray-900">{previewResult.event_count}</strong></span>
                <span>文章数: <strong className="text-gray-900">{previewResult.article_count}</strong></span>
              </div>
              {previewResult.events?.length > 0 && (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {previewResult.events.map((event: any) => (
                    <div key={event.id} className="text-xs text-gray-500 flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        (event.importance || 0) >= 7 ? "bg-red-100 text-red-700" :
                        (event.importance || 0) >= 5 ? "bg-yellow-100 text-yellow-700" :
                        "bg-gray-100 text-gray-600"
                      }`}>
                        {event.event_type || "其他"}
                      </span>
                      <span className="truncate">{event.title}</span>
                      <span className="text-gray-400">({event.article_count}篇)</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between p-5 border-t bg-gray-50 rounded-b-xl">
          <div className="text-sm text-gray-500">
            {canGenerate && !previewResult && "请先预览以确认事件范围"}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
            >
              取消
            </button>
            <button
              onClick={onPreview}
              disabled={!canGenerate || isPreviewing}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {isPreviewing ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />}
              预览
            </button>
            <button
              onClick={onGenerate}
              disabled={!canGenerate || isGenerating}
              className="flex items-center gap-1.5 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
            >
              {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              生成摘要
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
