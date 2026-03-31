"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function EventsPage() {
  const { data: events, isLoading } = useQuery({
    queryKey: ["events"],
    queryFn: () => api.get("/api/events"),
  });

  const eventTypeColors: Record<string, string> = {
    funding: "bg-green-100 text-green-700",
    product_launch: "bg-blue-100 text-blue-700",
    partnership: "bg-purple-100 text-purple-700",
    conference: "bg-amber-100 text-amber-700",
    research: "bg-indigo-100 text-indigo-700",
    delivery: "bg-emerald-100 text-emerald-700",
  };

  const eventTypeLabels: Record<string, string> = {
    funding: "融资",
    product_launch: "产品发布",
    partnership: "合作",
    conference: "会议",
    research: "研究",
    delivery: "交付",
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">事件列表</h1>

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
                      eventTypeColors[e.event_type] || "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {eventTypeLabels[e.event_type] || e.event_type || "未分类"}
                  </span>
                  {e.company_name && (
                    <span className="text-sm font-medium">{e.company_name}</span>
                  )}
                </div>
                <p className="text-sm text-gray-700 mb-2">
                  {e.one_line_summary || "暂无摘要"}
                </p>
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>
                    重要性: {e.importance}/5
                  </span>
                  {e.event_date && (
                    <span>
                      {new Date(e.event_date).toLocaleDateString()}
                    </span>
                  )}
                  <span>
                    已包含在摘要中: {e.included_in_digest ? "是" : "否"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
        {events?.length === 0 && !isLoading && (
          <div className="text-center py-12 text-gray-400">
            暂无事件。文章将自动分类为事件。
          </div>
        )}
      </div>
    </div>
  );
}
