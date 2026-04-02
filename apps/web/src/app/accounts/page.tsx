"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Plus, Trash2, Edit2, Search, Loader2, Check, Rss, MessageSquare } from "lucide-react";

export default function SourcesPage() {
  const [activeTab, setActiveTab] = useState<"wechat" | "rss">("wechat");

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">来源管理</h1>

      <div className="flex gap-1 mb-6 border-b">
        <button
          onClick={() => setActiveTab("wechat")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "wechat"
              ? "border-gray-900 text-gray-900"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <MessageSquare size={16} />
          微信公众号
        </button>
        <button
          onClick={() => setActiveTab("rss")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "rss"
              ? "border-gray-900 text-gray-900"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <Rss size={16} />
          RSS 源
        </button>
      </div>

      {activeTab === "wechat" && <WeChatAccounts />}
      {activeTab === "rss" && <RssFeeds />}
    </div>
  );
}

function WeChatAccounts() {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/source-accounts"),
  });

  const [form, setForm] = useState({
    account_name: "",
    account_alias: "",
    category: "",
    priority: 5,
    enabled: true,
    notes: "",
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/api/source-accounts", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setShowForm(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/source-accounts/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setEditingId(null);
      setShowForm(false);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/source-accounts/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  const resolveMutation = useMutation({
    mutationFn: ({ id, fakeid }: { id: string; fakeid: string }) =>
      api.post(`/api/source-accounts/${id}/resolve-fakeid`, { fakeid }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setSearchResults([]);
      setSearchQuery("");
      setResolvingId(null);
    },
  });

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const results = await api.get(
        `/api/source-accounts/search?query=${encodeURIComponent(searchQuery)}`
      );
      setSearchResults(results || []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectAccount = (account: any) => {
    if (!resolvingId) return;
    resolveMutation.mutate({ id: resolvingId, fakeid: account.fakeid });
  };

  const resetForm = () =>
    setForm({
      account_name: "",
      account_alias: "",
      category: "",
      priority: 5,
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

  const startEdit = (a: any) => {
    setEditingId(a.id);
    setForm({
      account_name: a.account_name,
      account_alias: a.account_alias || "",
      category: a.category || "",
      priority: a.priority,
      enabled: a.enabled,
      notes: a.notes || "",
    });
    setShowForm(true);
  };

  const openSearch = (account: any) => {
    setResolvingId(account.id);
    setSearchQuery(account.account_name);
    setSearchResults([]);
  };

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => {
            resetForm();
            setEditingId(null);
            setShowForm(!showForm);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
        >
          <Plus size={16} />
          {showForm ? "取消" : "添加公众号"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">公众号名称 *</label>
              <input
                type="text" required value={form.account_name}
                onChange={(e) => setForm({ ...form, account_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="例如: 机器之心"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">别名</label>
              <input
                type="text" value={form.account_alias}
                onChange={(e) => setForm({ ...form, account_alias: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">分类</label>
              <input
                type="text" value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="例如: AI研究, 机器人"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">优先级</label>
              <input
                type="number" min={1} max={10} value={form.priority}
                onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-1">备注</label>
              <textarea
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                rows={2}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm mb-4">
            <input
              type="checkbox" checked={form.enabled}
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

      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">名称</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">fakeid</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">分类</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">优先级</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">状态</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">最后检查</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {accounts?.map((a: any) => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="font-medium">{a.account_name}</div>
                  {a.account_alias && <div className="text-gray-400 text-xs">{a.account_alias}</div>}
                </td>
                <td className="px-4 py-3">
                  {a.fakeid ? (
                    <span className="text-xs font-mono text-green-600">{a.fakeid.slice(0, 8)}...</span>
                  ) : (
                    <span className="text-xs text-gray-400">未设置</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">{a.category || "-"}</td>
                <td className="px-4 py-3">{a.priority}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${a.enabled ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {a.enabled ? "已启用" : "已禁用"}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {a.last_checked_at ? new Date(a.last_checked_at).toLocaleDateString() : "-"}
                </td>
                <td className="px-4 py-3 text-right space-x-1">
                  <button onClick={() => openSearch(a)} className="p-1 text-blue-500 hover:text-blue-700" title="搜索并设置 fakeid">
                    <Search size={14} />
                  </button>
                  <button onClick={() => startEdit(a)} className="p-1 text-gray-400 hover:text-gray-700" title="编辑">
                    <Edit2 size={14} />
                  </button>
                  <button onClick={() => deleteMutation.mutate(a.id)} className="p-1 text-gray-400 hover:text-red-600" title="删除">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {resolvingId && (
          <div className="border-t p-4 bg-blue-50">
            <div className="flex items-center gap-2 mb-3">
              <Search size={16} className="text-blue-600" />
              <span className="text-sm font-medium text-blue-800">搜索公众号并设置 fakeid</span>
              <button onClick={() => { setResolvingId(null); setSearchResults([]); setSearchQuery(""); }} className="ml-auto text-sm text-gray-500 hover:text-gray-700">关闭</button>
            </div>
            <div className="flex gap-2 mb-3">
              <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSearch()} placeholder="输入公众号名称搜索..." className="flex-1 px-3 py-2 border rounded-md text-sm" />
              <button onClick={handleSearch} disabled={searching} className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1">
                {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                搜索
              </button>
            </div>
            {searchResults.length > 0 && (
              <div className="space-y-1">
                {searchResults.map((r: any) => (
                  <button key={r.fakeid} onClick={() => handleSelectAccount(r)} disabled={resolveMutation.isPending} className="w-full flex items-center gap-3 px-3 py-2 bg-white rounded-md border hover:bg-blue-50 text-left text-sm disabled:opacity-50">
                    {r.round_head_img && <img src={r.round_head_img} alt="" className="w-8 h-8 rounded-full" />}
                    <div className="flex-1">
                      <div className="font-medium">{r.nickname}</div>
                      <div className="text-xs text-gray-400">{r.alias} · {r.fakeid}</div>
                    </div>
                    <Check size={14} className="text-green-600" />
                  </button>
                ))}
              </div>
            )}
            {searching && <div className="text-center py-4 text-gray-400 text-sm">搜索中...</div>}
            {searchQuery && !searching && searchResults.length === 0 && <div className="text-center py-4 text-gray-400 text-sm">未找到匹配的公众号</div>}
          </div>
        )}

        {accounts?.length === 0 && <div className="text-center py-12 text-gray-400">尚未配置任何公众号。添加一个以开始使用。</div>}
      </div>
    </div>
  );
}

function RssFeeds() {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [testingUrl, setTestingUrl] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any>(null);
  const queryClient = useQueryClient();

  const { data: feeds } = useQuery({
    queryKey: ["rss-feeds"],
    queryFn: () => api.get("/api/rss-feeds"),
  });

  const [form, setForm] = useState({
    name: "",
    feed_url: "",
    category: "",
    priority: 5,
    enabled: true,
    notes: "",
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/api/rss-feeds", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rss-feeds"] });
      setShowForm(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/rss-feeds/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rss-feeds"] });
      setEditingId(null);
      setShowForm(false);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/rss-feeds/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rss-feeds"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/api/rss-feeds/${id}`, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rss-feeds"] });
    },
  });

  const testMutation = useMutation({
    mutationFn: (feedUrl: string) => api.post("/api/rss-feeds/test", { feed_url: feedUrl }),
    onSuccess: (data) => {
      setTestResult(data);
    },
    onError: (error: Error) => {
      setTestResult({ success: false, error: error.message });
    },
  });

  const resetForm = () =>
    setForm({ name: "", feed_url: "", category: "", priority: 5, enabled: true, notes: "" });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: form });
    } else {
      createMutation.mutate(form);
    }
  };

  const startEdit = (f: any) => {
    setEditingId(f.id);
    setForm({
      name: f.name,
      feed_url: f.feed_url,
      category: f.category || "",
      priority: f.priority,
      enabled: f.enabled,
      notes: f.notes || "",
    });
    setShowForm(true);
  };

  const handleTest = (feedUrl: string) => {
    setTestingUrl(feedUrl);
    setTestResult(null);
    testMutation.mutate(feedUrl);
  };

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => { resetForm(); setEditingId(null); setShowForm(!showForm); }}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
        >
          <Plus size={16} />
          {showForm ? "取消" : "添加 RSS 源"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg border p-6 mb-6 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">名称 *</label>
              <input
                type="text" required value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="例如: 36氪"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">RSS 链接 *</label>
              <input
                type="text" required value={form.feed_url}
                onChange={(e) => setForm({ ...form, feed_url: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm font-mono"
                placeholder="https://example.com/feed.xml"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">分类</label>
              <input
                type="text" value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="例如: AI研究, 科技新闻"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">优先级</label>
              <input
                type="number" min={1} max={10} value={form.priority}
                onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-1">备注</label>
              <textarea
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full px-3 py-2 border rounded-md text-sm"
                rows={2}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm mb-4">
            <input
              type="checkbox" checked={form.enabled}
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

      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">名称</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">RSS 链接</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">分类</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">优先级</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">状态</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">最后检查</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {feeds?.map((f: any) => (
              <tr key={f.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="font-medium">{f.name}</div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs font-mono text-gray-500 truncate block max-w-[200px]">{f.feed_url}</span>
                </td>
                <td className="px-4 py-3 text-gray-600">{f.category || "-"}</td>
                <td className="px-4 py-3">{f.priority}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${f.enabled ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {f.enabled ? "已启用" : "已禁用"}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {f.last_checked_at ? new Date(f.last_checked_at).toLocaleDateString() : "-"}
                </td>
                <td className="px-4 py-3 text-right space-x-1">
                  <button onClick={() => handleTest(f.feed_url)} className="p-1 text-blue-500 hover:text-blue-700" title="测试连通性">
                    <Rss size={14} />
                  </button>
                  <button onClick={() => startEdit(f)} className="p-1 text-gray-400 hover:text-gray-700" title="编辑">
                    <Edit2 size={14} />
                  </button>
                  <button onClick={() => deleteMutation.mutate(f.id)} className="p-1 text-gray-400 hover:text-red-600" title="删除">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {feeds?.length === 0 && <div className="text-center py-12 text-gray-400">尚未配置任何 RSS 源。添加一个以开始使用。</div>}
      </div>

      {testResult && (
        <div className={`mt-4 p-4 rounded-lg border ${testResult.success ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
          <div className="flex items-center gap-2">
            {testResult.success ? <Check size={16} className="text-green-600" /> : <span className="text-red-600">✕</span>}
            <span className="text-sm font-medium">{testResult.success ? "RSS 源可用" : "RSS 源不可用"}</span>
          </div>
          {testResult.title && <p className="text-sm text-gray-600 mt-1">标题: {testResult.title}</p>}
          {testResult.article_count !== undefined && <p className="text-sm text-gray-600">文章数: {testResult.article_count}</p>}
          {testResult.error && <p className="text-sm text-red-600 mt-1">错误: {testResult.error}</p>}
        </div>
      )}
    </div>
  );
}
