"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ExternalLink, Filter, Link2, GitMerge, Scissors, Edit2, Trash2, X } from "lucide-react";

import { api } from "@/lib/api";

const PAGE_SIZE = 20;

const eventTypeColors: Record<string, string> = {
  "融资": "bg-green-100 text-green-700",
  "产品发布": "bg-blue-100 text-blue-700",
  "发布": "bg-blue-100 text-blue-700",
  "合作": "bg-purple-100 text-purple-700",
  "会议": "bg-amber-100 text-amber-700",
  "展会": "bg-amber-100 text-amber-700",
  "研究": "bg-indigo-100 text-indigo-700",
  "交付": "bg-emerald-100 text-emerald-700",
  "政策": "bg-cyan-100 text-cyan-700",
  "其他": "bg-gray-100 text-gray-700",
};

const eventTypeOptions = ["融资", "产品发布", "发布", "研究", "合作", "展会", "政策", "交付", "会议", "其他"];

export default function EventsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState({
    event_type: "",
    status: "active",
    included_in_digest: "",
  });
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    title: "",
    event_type: "",
    status: "active",
    importance: 3,
    summary_short: "",
    summary_long: "",
    analyst_note: "",
    included_in_digest: false,
  });
  const [attachArticleId, setAttachArticleId] = useState("");
  const [mergeSourceId, setMergeSourceId] = useState("");
  const [splitTitle, setSplitTitle] = useState("");
  const [selectedArticleIds, setSelectedArticleIds] = useState<string[]>([]);

  const params = useMemo(() => {
    const search = new URLSearchParams();
    search.set("skip", String(page * PAGE_SIZE));
    search.set("limit", String(PAGE_SIZE));
    if (filters.event_type) search.set("event_type", filters.event_type);
    if (filters.status) search.set("status", filters.status);
    if (filters.included_in_digest) search.set("included_in_digest", filters.included_in_digest);
    return search.toString();
  }, [filters, page]);

  const { data: events, isLoading } = useQuery({
    queryKey: ["events", params],
    queryFn: () => api.get(`/api/events?${params}`),
  });

  const { data: selectedEvent, isFetching: isLoadingDetail } = useQuery({
    queryKey: ["event-detail", selectedEventId],
    queryFn: () => api.get(`/api/events/${selectedEventId}`),
    enabled: Boolean(selectedEventId),
  });

  const refreshEvents = () => {
    queryClient.invalidateQueries({ queryKey: ["events"] });
    queryClient.invalidateQueries({ queryKey: ["event-detail"] });
    queryClient.invalidateQueries({ queryKey: ["articles"] });
  };

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.patch(`/api/events/${id}`, data),
    onSuccess: () => {
      refreshEvents();
      setEditingEventId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/events/${id}`),
    onSuccess: () => {
      refreshEvents();
      setSelectedEventId(null);
    },
  });

  const attachMutation = useMutation({
    mutationFn: ({ id, articleId }: { id: string; articleId: string }) =>
      api.post(`/api/events/${id}/articles`, { article_id: articleId, role: "manual" }),
    onSuccess: () => {
      refreshEvents();
      setAttachArticleId("");
    },
  });

  const detachMutation = useMutation({
    mutationFn: ({ eventId, articleId }: { eventId: string; articleId: string }) =>
      api.delete(`/api/events/${eventId}/articles/${articleId}`),
    onSuccess: () => {
      refreshEvents();
      setSelectedArticleIds([]);
    },
  });

  const mergeMutation = useMutation({
    mutationFn: ({ targetId, sourceId }: { targetId: string; sourceId: string }) =>
      api.post(`/api/events/merge`, { event_ids: [targetId, sourceId], target_event_id: targetId }),
    onSuccess: (data: any) => {
      refreshEvents();
      setSelectedEventId(data.id);
      setMergeSourceId("");
    },
  });

  const splitMutation = useMutation({
    mutationFn: ({ id, articleIds, title }: { id: string; articleIds: string[]; title: string }) =>
      api.post(`/api/events/${id}/split`, { article_ids: articleIds, title: title || undefined }),
    onSuccess: () => {
      refreshEvents();
      setSplitTitle("");
      setSelectedArticleIds([]);
    },
  });

  const startEdit = (event: any) => {
    setEditingEventId(event.id);
    setEditForm({
      title: event.title || "",
      event_type: event.event_type || "",
      status: event.status || "active",
      importance: event.importance || 3,
      summary_short: event.summary_short || "",
      summary_long: event.summary_long || "",
      analyst_note: event.analyst_note || "",
      included_in_digest: Boolean(event.included_in_digest),
    });
  };

  const toggleArticle = (articleId: string) => {
    setSelectedArticleIds((prev) =>
      prev.includes(articleId) ? prev.filter((id) => id !== articleId) : [...prev, articleId]
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">事件列表</h1>
        <p className="text-sm text-gray-500">聚合后的事件会汇总相关文章、参与方和摘要，可在详情中手工挂接、合并或拆分。</p>
      </div>

      <div className="bg-white rounded-lg border p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={16} className="text-gray-400" />
          <span className="text-sm font-medium">筛选条件</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <select
            value={filters.event_type}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, event_type: e.target.value }));
              setPage(0);
            }}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部类型</option>
            {eventTypeOptions.map((eventType) => (
              <option key={eventType} value={eventType}>
                {eventType}
              </option>
            ))}
          </select>

          <select
            value={filters.status}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, status: e.target.value }));
              setPage(0);
            }}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部状态</option>
            <option value="active">active</option>
          </select>

          <select
            value={filters.included_in_digest}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, included_in_digest: e.target.value }));
              setPage(0);
            }}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部摘要状态</option>
            <option value="true">已纳入摘要</option>
            <option value="false">未纳入摘要</option>
          </select>
        </div>
      </div>

      {editingEventId && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">编辑事件</h3>
              <button onClick={() => setEditingEventId(null)} className="text-gray-400 hover:text-gray-600">
                <X size={18} />
              </button>
            </div>
            <div className="space-y-4">
              <input
                value={editForm.title}
                onChange={(e) => setEditForm((prev) => ({ ...prev, title: e.target.value }))}
                className="w-full px-3 py-2 border rounded-md text-sm"
                placeholder="事件标题"
              />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <input
                  value={editForm.event_type}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, event_type: e.target.value }))}
                  className="px-3 py-2 border rounded-md text-sm"
                  placeholder="事件类型"
                />
                <input
                  value={editForm.status}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, status: e.target.value }))}
                  className="px-3 py-2 border rounded-md text-sm"
                  placeholder="状态"
                />
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={editForm.importance}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, importance: Number(e.target.value) }))}
                  className="px-3 py-2 border rounded-md text-sm"
                  placeholder="重要性"
                />
              </div>
              <textarea
                value={editForm.summary_short}
                onChange={(e) => setEditForm((prev) => ({ ...prev, summary_short: e.target.value }))}
                className="w-full px-3 py-2 border rounded-md text-sm"
                rows={2}
                placeholder="一句话摘要"
              />
              <textarea
                value={editForm.summary_long}
                onChange={(e) => setEditForm((prev) => ({ ...prev, summary_long: e.target.value }))}
                className="w-full px-3 py-2 border rounded-md text-sm"
                rows={4}
                placeholder="详细摘要"
              />
              <textarea
                value={editForm.analyst_note}
                onChange={(e) => setEditForm((prev) => ({ ...prev, analyst_note: e.target.value }))}
                className="w-full px-3 py-2 border rounded-md text-sm"
                rows={3}
                placeholder="分析师备注"
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={editForm.included_in_digest}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, included_in_digest: e.target.checked }))}
                />
                纳入日报摘要
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => updateMutation.mutate({ id: editingEventId, data: editForm })}
                  disabled={updateMutation.isPending}
                  className="px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
                >
                  保存
                </button>
                <button
                  onClick={() => setEditingEventId(null)}
                  className="px-4 py-2 border rounded-md text-sm hover:bg-gray-50"
                >
                  取消
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedEventId && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-40">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[92vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold">事件详情</h3>
                <p className="text-xs text-gray-400">{selectedEventId}</p>
              </div>
              <button onClick={() => setSelectedEventId(null)} className="text-gray-400 hover:text-gray-600">
                <X size={18} />
              </button>
            </div>

            {isLoadingDetail && <div className="py-12 text-center text-gray-400">加载详情中...</div>}

            {selectedEvent && (
              <div className="space-y-6">
                <div className="border rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs ${
                        eventTypeColors[selectedEvent.event_type] || "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {selectedEvent.event_type || "未分类"}
                    </span>
                    <span className="font-semibold">{selectedEvent.title}</span>
                    <span className="text-xs text-gray-400">文章数 {selectedEvent.article_count}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        selectedEvent.included_in_digest ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {selectedEvent.included_in_digest ? "摘要已选" : "摘要未选"}
                    </span>
                  </div>
                  {selectedEvent.entities?.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-3">
                      {selectedEvent.entities.map((entity: any) => (
                        <span key={entity.id} className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
                          {entity.name} · {entity.role}
                        </span>
                      ))}
                    </div>
                  )}
                  {selectedEvent.summary_short && (
                    <p className="text-sm text-gray-700 mb-2">{selectedEvent.summary_short}</p>
                  )}
                  {selectedEvent.summary_long && (
                    <p className="text-sm text-gray-500 whitespace-pre-wrap">{selectedEvent.summary_long}</p>
                  )}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3 font-medium text-sm">
                      <Link2 size={14} />
                      挂接文章
                    </div>
                    <div className="space-y-3">
                      <input
                        value={attachArticleId}
                        onChange={(e) => setAttachArticleId(e.target.value)}
                        className="w-full px-3 py-2 border rounded-md text-sm"
                        placeholder="输入 article_id"
                      />
                      <button
                        onClick={() => attachMutation.mutate({ id: selectedEvent.id, articleId: attachArticleId })}
                        disabled={!attachArticleId || attachMutation.isPending}
                        className="w-full px-3 py-2 bg-gray-900 text-white rounded-md text-sm disabled:opacity-50"
                      >
                        挂接到当前事件
                      </button>
                    </div>
                  </div>

                  <div className="border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3 font-medium text-sm">
                      <GitMerge size={14} />
                      合并事件
                    </div>
                    <div className="space-y-3">
                      <input
                        value={mergeSourceId}
                        onChange={(e) => setMergeSourceId(e.target.value)}
                        className="w-full px-3 py-2 border rounded-md text-sm"
                        placeholder="输入要并入的 event_id"
                      />
                      <button
                        onClick={() => mergeMutation.mutate({ targetId: selectedEvent.id, sourceId: mergeSourceId })}
                        disabled={!mergeSourceId || mergeMutation.isPending}
                        className="w-full px-3 py-2 bg-gray-900 text-white rounded-md text-sm disabled:opacity-50"
                      >
                        合并到当前事件
                      </button>
                    </div>
                  </div>

                  <div className="border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3 font-medium text-sm">
                      <Scissors size={14} />
                      拆分事件
                    </div>
                    <div className="space-y-3">
                      <input
                        value={splitTitle}
                        onChange={(e) => setSplitTitle(e.target.value)}
                        className="w-full px-3 py-2 border rounded-md text-sm"
                        placeholder="新事件标题（可选）"
                      />
                      <button
                        onClick={() =>
                          splitMutation.mutate({
                            id: selectedEvent.id,
                            articleIds: selectedArticleIds,
                            title: splitTitle,
                          })
                        }
                        disabled={selectedArticleIds.length === 0 || splitMutation.isPending}
                        className="w-full px-3 py-2 bg-gray-900 text-white rounded-md text-sm disabled:opacity-50"
                      >
                        用已选文章拆分新事件
                      </button>
                    </div>
                  </div>
                </div>

                <div className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="font-medium text-sm">关联文章</div>
                    <div className="text-xs text-gray-400">勾选后可拆分；每篇文章也可以单独移除</div>
                  </div>
                  <div className="space-y-3">
                    {selectedEvent.related_articles?.map((article: any) => (
                      <div key={article.id} className="border rounded-md p-3">
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={selectedArticleIds.includes(article.id)}
                            onChange={() => toggleArticle(article.id)}
                            className="mt-1"
                          />
                          <div className="flex-1">
                            <a
                              href={article.article_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-blue-600 hover:underline inline-flex items-center gap-1"
                            >
                              {article.title}
                              <ExternalLink size={12} />
                            </a>
                            <div className="text-xs text-gray-400 mt-1">
                              {article.account_name}
                              {article.publish_time ? ` · ${new Date(article.publish_time).toLocaleDateString("zh-CN")}` : ""}
                            </div>
                            {article.summary_short && (
                              <p className="text-sm text-gray-600 mt-2">{article.summary_short}</p>
                            )}
                          </div>
                          <button
                            onClick={() => detachMutation.mutate({ eventId: selectedEvent.id, articleId: article.id })}
                            className="px-2 py-1 border rounded text-xs hover:bg-gray-50"
                          >
                            移除
                          </button>
                        </div>
                      </div>
                    ))}
                    {selectedEvent.related_articles?.length === 0 && (
                      <div className="text-sm text-gray-400">当前事件还没有关联文章。</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {isLoading && <div className="text-center py-12 text-gray-400">加载中...</div>}

        {events?.map((event: any) => (
          <div key={event.id} id={`event-${event.id}`} className="bg-white rounded-lg border p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs ${
                      eventTypeColors[event.event_type] || "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {event.event_type || "未分类"}
                  </span>
                  <span className="font-semibold">{event.title}</span>
                  <span className="text-xs text-gray-400">文章 {event.article_count}</span>
                  <span className="text-xs text-gray-400">重要性 {event.importance}</span>
                </div>

                {event.entities?.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {event.entities.map((entity: any) => (
                      <span key={entity.id} className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                        {entity.name}
                      </span>
                    ))}
                  </div>
                )}

                <p className="text-sm text-gray-700 mb-3">{event.summary_short || "暂无摘要"}</p>

                {event.representative_articles?.length > 0 && (
                  <div className="space-y-1">
                    {event.representative_articles.map((article: any) => (
                      <a
                        key={article.id}
                        href={article.article_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-xs text-blue-600 hover:underline"
                      >
                        {article.title} · {article.account_name}
                      </a>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => setSelectedEventId(event.id)}
                  className="px-3 py-1.5 border rounded-md text-sm hover:bg-gray-50"
                >
                  详情
                </button>
                <button
                  onClick={() => startEdit(event)}
                  className="p-2 text-gray-400 hover:text-gray-700"
                  title="编辑"
                >
                  <Edit2 size={14} />
                </button>
                <button
                  onClick={() => {
                    if (window.confirm("确认删除这个聚合事件吗？")) {
                      deleteMutation.mutate(event.id);
                    }
                  }}
                  className="p-2 text-gray-400 hover:text-red-600"
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
            暂无聚合事件。文章分类后会自动归并到事件中。
          </div>
        )}
      </div>

      {events && events.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 mt-4 bg-white rounded-lg border">
          <span className="text-sm text-gray-500">第 {page + 1} 页</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((prev) => Math.max(0, prev - 1))}
              disabled={page === 0}
              className="flex items-center gap-1 px-3 py-1.5 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={14} />
              上一页
            </button>
            <button
              onClick={() => setPage((prev) => prev + 1)}
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
