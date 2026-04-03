"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState, Fragment } from "react";
import { Filter, ExternalLink, Rss, MessageSquare, ChevronLeft, ChevronRight, FileText, ChevronDown, ChevronUp } from "lucide-react";

const PAGE_SIZE = 30;

function ArticleRow({ article }: { article: any }) {
  const [expanded, setExpanded] = useState(false);

  const hasSummary = article.status === "classified" && (article.summary_short || article.summary_long);

  return (
    <Fragment>
      <tr className="hover:bg-gray-50">
        <td className="px-4 py-3">
          <a
            href={article.article_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline inline-flex items-center gap-1"
          >
            {article.title}
            <ExternalLink size={12} />
          </a>
        </td>
        <td className="px-4 py-3 text-gray-600">{article.account_name}</td>
        <td className="px-4 py-3">
          {article.source_type === "rss" ? (
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
          {article.is_relevant === true && (
            <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
              是
            </span>
          )}
          {article.is_relevant === false && (
            <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs">
              否
            </span>
          )}
          {article.is_relevant === null && (
            <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full text-xs">
              待处理
            </span>
          )}
        </td>
        <td className="px-4 py-3 text-gray-600">{article.primary_event_type || "-"}</td>
        <td className="px-4 py-3">
          {hasSummary ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-600 rounded-md hover:bg-blue-100 transition-colors"
            >
              <FileText size={14} />
              <span className="text-xs">查看</span>
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          ) : (
            <span className="text-gray-400 text-xs">待分类</span>
          )}
        </td>
        <td className="px-4 py-3 text-gray-500">
          {article.publish_time
            ? new Date(article.publish_time).toLocaleDateString()
            : "-"}
        </td>
      </tr>
      {expanded && hasSummary && (
        <tr>
          <td colSpan={7} className="px-0 py-0">
            <div className="bg-gray-50 border-y border-gray-200 px-6 py-5">
              <div className="max-w-4xl">
                <div className="flex items-center gap-2 mb-4">
                  <FileText size={14} className="text-blue-500" />
                  <span className="text-sm font-semibold text-gray-800">文章摘要</span>
                  <span className="text-xs text-gray-400">— {article.title}</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  {article.summary_short && (
                    <div className="bg-white rounded-lg border p-3">
                      <div className="flex items-center gap-1.5 mb-2">
                        <span className="text-xs font-medium text-blue-600">💬 一句话摘要</span>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed">{article.summary_short}</p>
                    </div>
                  )}
                  {article.summary_long && (
                    <div className="bg-white rounded-lg border p-3">
                      <div className="flex items-center gap-1.5 mb-2">
                        <span className="text-xs font-medium text-blue-600">📋 详细摘要</span>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{article.summary_long}</p>
                    </div>
                  )}
                </div>

                <div className="border-t border-gray-200 pt-4">
                  <div className="flex flex-wrap gap-4">
                    {article.tags_json && article.tags_json.length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-gray-400 mb-1.5">🏷️ 标签</div>
                        <div className="flex flex-wrap gap-1.5">
                          {article.tags_json.map((tag: string, i: number) => (
                            <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {article.companies_json && article.companies_json.length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-gray-400 mb-1.5">🏢 公司</div>
                        <div className="flex flex-wrap gap-1.5">
                          {article.companies_json.map((c: string, i: number) => (
                            <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                              {c}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {article.primary_event_type && (
                      <div>
                        <div className="text-xs font-medium text-gray-400 mb-1.5">📊 事件类型</div>
                        <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">
                          {article.primary_event_type}
                        </span>
                      </div>
                    )}
                    {article.relevance_score != null && (
                      <div>
                        <div className="text-xs font-medium text-gray-400 mb-1.5">⭐ 相关性</div>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                article.relevance_score >= 7
                                  ? "bg-green-500"
                                  : article.relevance_score >= 4
                                    ? "bg-yellow-500"
                                    : "bg-red-500"
                              }`}
                              style={{ width: `${article.relevance_score * 10}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium text-gray-600">
                            {article.relevance_score}/10
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

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
              <th className="text-left px-4 py-3 font-medium text-gray-500">摘要</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">日期</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  加载中...
                </td>
              </tr>
            )}
            {articles?.map((a: any) => (
              <ArticleRow key={a.id} article={a} />
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
