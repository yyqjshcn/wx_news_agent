"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { Filter, ExternalLink } from "lucide-react";

export default function ArticlesPage() {
  const [filters, setFilters] = useState({
    account_name: "",
    status: "",
    is_relevant: "",
    event_type: "",
  });

  const { data: articles, isLoading } = useQuery({
    queryKey: ["articles", filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.account_name) params.set("account_name", filters.account_name);
      if (filters.status) params.set("status", filters.status);
      if (filters.is_relevant) params.set("is_relevant", filters.is_relevant);
      if (filters.event_type) params.set("event_type", filters.event_type);
      return api.get(`/api/articles?${params}`);
    },
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Articles</h1>

      <div className="bg-white rounded-lg border p-4 mb-6 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={16} className="text-gray-400" />
          <span className="text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <input
            type="text"
            placeholder="Account name"
            value={filters.account_name}
            onChange={(e) => setFilters({ ...filters, account_name: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          />
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">All Status</option>
            <option value="new">New</option>
            <option value="classified">Classified</option>
            <option value="skipped">Skipped</option>
          </select>
          <select
            value={filters.is_relevant}
            onChange={(e) => setFilters({ ...filters, is_relevant: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          >
            <option value="">All Relevance</option>
            <option value="true">Relevant</option>
            <option value="false">Not Relevant</option>
          </select>
          <input
            type="text"
            placeholder="Event type"
            value={filters.event_type}
            onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
            className="px-3 py-2 border rounded-md text-sm"
          />
        </div>
      </div>

      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Title</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Source</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Relevant</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Event</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  Loading...
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
                  {a.is_relevant === true && (
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                      Yes
                    </span>
                  )}
                  {a.is_relevant === false && (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs">
                      No
                    </span>
                  )}
                  {a.is_relevant === null && (
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full text-xs">
                      Pending
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
        {articles?.length === 0 && !isLoading && (
          <div className="text-center py-12 text-gray-400">
            No articles found. Configure sources and run a workflow to start collecting.
          </div>
        )}
      </div>
    </div>
  );
}
