"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Filter, Trash2, Edit2, ExternalLink, ChevronLeft, ChevronRight, X } from "lucide-react";

const PAGE_SIZE = 20;

export default function EventsPage() {
  const [filters, setFilters] = useState({
    event_type: "",
    included_in_digest: "",
  });
  const [page, setPage] = useState(0);
  const [editingEvent, setEditingEvent] = useState<any>(null);
  const [editForm, setEditForm] = useState({
    importance: 3,
    included_in_digest: false,
    analyst_note: "",
    one_line_summary: "",
  });

  const queryClient = useQueryClient();

  const { data: events, isLoading } = useQuery({
    queryKey: ["events", filters, page],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("skip", String(page * PAGE_SIZE));
      params.set("limit", String(PAGE_SIZE));
      if (filters.event_type) params.set("event_type", filters.event_type);
      if (filters.included_in_digest)
        params.set("included_in_digest", filters.included_in_digest);
      return api.get(`/api/events?${params}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.patch(`/api/events/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setEditingEvent(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/events/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });

  const toggleDigestMutation = useMutation({
    mutationFn: ({
      id,
      value,
    }: {
      id: string;
      value: boolean;
    }) => api.patch(`/api/events/${id}`, { included_in_digest: value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });

  const eventTypeColors: Record<string, string> = {
    "融资": "bg-green-100 text-green-700",
    "产品发布": "bg-blue-100 text-blue-700",
    "合作": "bg-purple-100 text-purple-700",
    "会议": "bg-amber-100 text-amber-700",
    "研究": "bg-indigo-100 text-indigo-700",
    "交付": "bg-emerald-100 text-emerald-700",
    "政策": "bg-cyan-100 text-cyan-700",
    "发布": "bg-blue-100 text-blue-700",
    "展会": "bg-amber-100 text-amber-700",
    "其他": "bg-gray-100 text-gray-700",
  };

  const eventTypeOptions = [
    { value: "融资", label: "融资" },
    { value: "产品发布", label: "产品发布" },
    { value: "发布", label: "发布" },
    { value: "研究", label: "研究" },
    { value: "合作", label: "合作" },
    { value: "展会", label: "展会" },
    { value: "政策", label: "政策" },
    { value: "交付", label: "交付" },
    { value: "会议", label: "会议" },
    { value: "其他", label: "其他" },
  ];

  const handleFilterChange = (newFilters: typeof filters) => {
    setFilters(newFilters);
    setPage(0);
  };

  const startEdit = (e: any) => {
    setEditingEvent(e.id);
    setEditForm({
      importance: e.importance,
      included_in_digest: e.included_in_digest,
      analyst_note: e.analyst_note || "",
      one_line_summary: e.one_line_summary || "",
    });
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">事件列表</h1>

      <div className="bg-white rounded-lg border p-4 mb-6 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={16} className="text-gray-400" />
          <span className="text-sm font-medium">筛选条件</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <select
            value={filters.event_type}
            onChange={(e) =>
              handleFilterChange({ ...filters, event_type: e.target.value })
            }
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部类型</option>
            {eventTypeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={filters.included_in_digest}
            onChange={(e) =>
              handleFilterChange({
                ...filters,
                included_in_digest: e.target.value,
              })
            }
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部状态</option>
            <option value="true">已包含在摘要中</option>
            <option value="false">未包含在摘要中</option>
          </select>
        </div>
      </div>

      {editingEvent && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">编辑事件</h3>
              <button
                onClick={() => setEditingEvent(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  一句话摘要
                </label>
                <textarea
                  value={editForm.one_line_summary}
                  onChange={(e) =>
                    setEditForm({ ...editForm, one_line_summary: e.target.value })
                  }
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  分析师备注
                </label>
                <textarea
                  value={editForm.analyst_note}
                  onChange={(e) =>
                    setEditForm({ ...editForm, analyst_note: e.target.value })
                  }
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  rows={3}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  重要性 (1-5)
                </label>
                <div className="flex gap-2">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      onClick={() => setEditForm({ ...editForm, importance: n })}
                      className={`w-8 h-8 rounded-full text-sm font-medium transition-colors ${
                        editForm.importance >= n
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={editForm.included_in_digest}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      included_in_digest: e.target.checked,
                    })
                  }
                />
                包含在每日摘要中
              </label>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => {
                    updateMutation.mutate({
                      id: editingEvent,
                      data: editForm,
                    });
                  }}
                  disabled={updateMutation.isPending}
                  className="px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
                >
                  保存
                </button>
                <button
                  onClick={() => setEditingEvent(null)}
                  className="px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
                >
                  取消
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {isLoading && (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        )}
        {events?.map((e: any) => (
          <div
            key={e.id}
            className="bg-white rounded-lg border p-5 shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs ${
                      eventTypeColors[e.event_type] ||
                      "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {e.event_type || "未分类"}
                  </span>
                  {e.company_name && (
                    <span className="text-sm font-medium">
                      {e.company_name}
                    </span>
                  )}
                  {e.article_id && (
                    <a
                      href={`/articles`}
                      className="text-xs text-blue-500 hover:underline inline-flex items-center gap-0.5"
                    >
                      <ExternalLink size={10} />
                      查看原文
                    </a>
                  )}
                </div>
                <p className="text-sm text-gray-700 mb-2">
                  {e.one_line_summary || "暂无摘要"}
                </p>
                {e.analyst_note && (
                  <p className="text-xs text-gray-500 mb-2 bg-gray-50 p-2 rounded">
                    {e.analyst_note}
                  </p>
                )}
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <div className="flex items-center gap-1">
                    <span>重要性:</span>
                    <div className="flex gap-0.5">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <div
                          key={n}
                          className={`w-2.5 h-2.5 rounded-full ${
                            n <= e.importance
                              ? "bg-blue-500"
                              : "bg-gray-200"
                          }`}
                        />
                      ))}
                    </div>
                  </div>
                  {e.event_date && (
                    <span>
                      {new Date(e.event_date).toLocaleDateString("zh-CN")}
                    </span>
                  )}
                  <button
                    onClick={() =>
                      toggleDigestMutation.mutate({
                        id: e.id,
                        value: !e.included_in_digest,
                      })
                    }
                    className={`px-2 py-0.5 rounded text-xs transition-colors cursor-pointer ${
                      e.included_in_digest
                        ? "bg-green-100 text-green-700 hover:bg-green-200"
                        : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                    }`}
                  >
                    {e.included_in_digest ? "已包含" : "未包含"}
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-1 ml-4">
                <button
                  onClick={() => startEdit(e)}
                  className="p-1.5 text-gray-400 hover:text-gray-700"
                  title="编辑"
                >
                  <Edit2 size={14} />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(e.id)}
                  className="p-1.5 text-gray-400 hover:text-red-600"
                  title="删除"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
        {events?.length === 0 && !isLoading && (
          <div className="text-center py-12 text-gray-400">
            暂无事件。文章分类后会自动生成事件。
          </div>
        )}
      </div>

      {events && events.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 mt-4 bg-white rounded-lg border">
          <span className="text-sm text-gray-500">
            第 {page + 1} 页
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="flex items-center gap-1 px-3 py-1.5 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={14} />
              上一页
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={events.length < PAGE_SIZE}
              className="flex items-center gap-1 px-3 py-1.5 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              下一页
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
