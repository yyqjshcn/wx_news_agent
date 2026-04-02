"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  BarChart3,
  FileText,
  BookOpen,
  CheckCircle,
  AlertCircle,
  Clock,
} from "lucide-react";

export default function DashboardPage() {
  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.get("/api/dashboard/stats"),
    refetchInterval: 30000,
  });

  const { data: sysStatus } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => api.get("/api/system/status"),
    refetchInterval: 30000,
  });

  const cards = [
    {
      label: "今日文章",
      value: stats?.today_articles ?? 0,
      icon: FileText,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: "文章总数",
      value: stats?.total_articles ?? 0,
      icon: BarChart3,
      color: "text-indigo-600",
      bg: "bg-indigo-50",
    },
    {
      label: "摘要总数",
      value: stats?.total_digests ?? 0,
      icon: BookOpen,
      color: "text-emerald-600",
      bg: "bg-emerald-50",
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">仪表盘</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="bg-white rounded-lg border p-5 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">{card.label}</p>
                  <p className="text-3xl font-bold mt-1">{card.value}</p>
                </div>
                <div className={`p-3 rounded-lg ${card.bg}`}>
                  <Icon className={card.color} size={24} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-white rounded-lg border p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">系统状态</h2>
        <div className="space-y-3">
          <StatusItem
            label="微信登录"
            status={sysStatus?.wechat?.status ?? "unknown"}
            message={sysStatus?.wechat?.message ?? "加载中..."}
          />
          <StatusItem
            label="模型提供商"
            status={sysStatus?.llm?.status ?? "unknown"}
            message={sysStatus?.llm?.message ?? "加载中..."}
          />
          <StatusItem
            label="定时任务"
            status={sysStatus?.scheduler?.status ?? "unknown"}
            message={sysStatus?.scheduler?.message ?? "加载中..."}
          />
        </div>
      </div>
    </div>
  );
}

function StatusItem({
  label,
  status,
  message,
}: {
  label: string;
  status: string;
  message: string;
}) {
  const config = {
    success: { icon: CheckCircle, color: "text-green-600" },
    failed: { icon: AlertCircle, color: "text-red-600" },
    unknown: { icon: Clock, color: "text-gray-400" },
    info: { icon: Clock, color: "text-blue-500" },
  }[status] || { icon: Clock, color: "text-gray-400" };
  const Icon = config.icon;

  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex items-center gap-3">
        <Icon className={config.color} size={18} />
        <span className="text-sm font-medium">{label}</span>
      </div>
      <span className="text-sm text-gray-500">{message}</span>
    </div>
  );
}
