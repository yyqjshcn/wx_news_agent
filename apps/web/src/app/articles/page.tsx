"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Filter, ExternalLink, Rss, MessageSquare, ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 30;

export default function ArticlesPage() {
  const [filters, setFilters] = useState({
    account_name: "",
    status: "",
    is_relevant: "",
    event_type: "",
    source_type: "",
  });
  const [page, setPage] = useState(0);

  const { data: articles, isLoading } = useQuery({
    queryKey: ["articles", filters, page],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("skip", String(page * PAGE_SIZE));
      params.set("limit", String(PAGE_SIZE));
      if (filters.account_name) params.set("account_name", filters.account_name);
      if (filters.status) params.set("status", filters.status);
      if (filters.is_relevant) params.set("is_relevant", filters.is_relevant);
      if (filters.event_type) params.set("event_type", filters.event_type);
      if (filters.source_type) params.set("source_type", filters.source_type);
      return api.get(`/api/articles?${params}`);
    },
  });

  const { data: totalCount } = useQuery({
    queryKey: ["articles-count", filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.account_name) params.set("account_name", filters.account_name);
      if (filters.status) params.set("status", filters.status);
      if (filters.is_relevant) params.set("is_relevant", filters.is_relevant);
      if (filters.event_type) params.set("event_type", filters.event_type);
      if (filters.source_type) params.set("source_type", filters.source_type);
      return api.get(`/api/articles/count?${params}`).then((r: any) => r.count);
    },
  });

  const totalPages = Math.ceil((totalCount || 0) / PAGE_SIZE);

  const handleFilterChange = (newFilters: typeof filters) => {
    setFilters(newFilters);
    setPage(0);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">文章列表</h1>

      <div className="bg-white rounded-lg border p-4 mb-6 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={16} className="text-gray-400" />
          <span className="text-sm font-medium">筛选条件</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <input
            type="text"
            placeholder="来源名称"
            value={filters.account_name}
            onChange={(e) => handleFilterChange({ ...filters, account_name: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          />
          <select
            value={filters.source_type}
            onChange={(e) => handleFilterChange({ ...filters, source_type: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部来源</option>
            <option value="wechat">微信公众号</option>
            <option value="rss">RSS 源</option>
          </select>
          <select
            value={filters.status}
            onChange={(e) => handleFilterChange({ ...filters, status: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部状态</option>
            <option value="new">新文章</option>
            <option value="classified">已分类</option>
            <option value="skipped">已跳过</option>
          </select>
          <select
            value={filters.is_relevant}
            onChange={(e) => handleFilterChange({ ...filters, is_relevant: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">全部相关性</option>
            <option value="true">相关</option>
            <option value="false">不相关</option>
          </select>
          <input
            type="text"
            placeholder="事件类型"
            value={filters.event_type}
            onChange={(e) => handleFilterChange({ ...filters, event_type: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          />
        </div>
      </div>

      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">标题</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">来源</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">类型</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">相关性</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">事件</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">日期</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  加载中...
                </td>
              </tr>
            )}
            {articles?.map((a: any) => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <a
                    href={a.article_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline inline-flex items-center gap-1"
                  >
                    {a.title}
                    <ExternalLink size={12} />
                  </a>
                </td>
                <td className="px-4 py-3 text-gray-600">{a.account_name}</td>
                <td className="px-4 py-3">
                  {a.source_type === "rss" ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs">
                      <Rss size={10} />
                      RSS
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs">
                      <MessageSquare size={10} />
                      微信
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {a.is_relevant === true && (
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                      是
                    </span>
                  )}
                  {a.is_relevant === false && (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs">
                      否
                    </span>
                  )}
                  {a.is_relevant === null && (
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full text-xs">
                      待处理
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">{a.primary_event_type || "-"}</td>
                <td className="px-4 py-3 text-gray-500">
                  {a.publish_time
                    ? new Date(a.publish_time).toLocaleDateString()
                    : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {totalCount !== undefined && totalCount > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <span className="text-sm text-gray-500">
              共 {totalCount} 条，第 {page + 1}/{totalPages || 1} 页
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
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="flex items-center gap-1 px-3 py-1.5 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                下一页
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}

        {articles?.length === 0 && !isLoading && (
          <div className="text-center py-12 text-gray-400">
            未找到文章。配置来源并运行工作流以开始采集。
          </div>
        )}
      </div>
    </div>
  );
}
