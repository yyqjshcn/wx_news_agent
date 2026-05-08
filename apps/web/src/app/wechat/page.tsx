"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";
import { RefreshCw, AlertCircle, CheckCircle, ExternalLink, Loader2 } from "lucide-react";

export default function WeChatPage() {
  const queryClient = useQueryClient();
  const [adapterLoginUrl, setAdapterLoginUrl] = useState("//localhost:5000/login.html");

  useEffect(() => {
    setAdapterLoginUrl(`//${window.location.hostname}:5000/login.html`);
  }, []);

  const { data: status, isLoading } = useQuery({
    queryKey: ["wechat-status"],
    queryFn: () => api.get("/api/wechat/status"),
    refetchInterval: 30000,
  });

  const checkAdapterMutation = useMutation({
    mutationFn: () => api.post("/api/wechat/refresh-qr"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wechat-status"] });
    },
  });

  // Auto-refresh adapter status on page load
  useEffect(() => {
    checkAdapterMutation.mutate();
  }, []);

  const statusConfig: Record<string, { color: string; icon: any; label: string; bg: string }> = {
    logged_in: { color: "text-green-600", icon: CheckCircle, label: "已登录", bg: "bg-green-50" },
    expired: { color: "text-amber-600", icon: AlertCircle, label: "会话已过期", bg: "bg-amber-50" },
    error: { color: "text-red-600", icon: AlertCircle, label: "错误", bg: "bg-red-50" },
    unknown: { color: "text-gray-400", icon: AlertCircle, label: "未知", bg: "bg-gray-50" },
  };

  const config = statusConfig[status?.status] || statusConfig.unknown;
  const StatusIcon = config.icon;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">微信登录</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-6 shadow-sm">
          <h2 className="font-semibold mb-4">登录状态</h2>

          {isLoading ? (
            <div className="flex items-center gap-3 mb-4">
              <Loader2 className="text-gray-400 animate-spin" size={24} />
              <span className="text-lg font-medium text-gray-400">检查中...</span>
            </div>
          ) : (
            <div className={`rounded-lg p-4 mb-4 ${config.bg}`}>
              <div className="flex items-center gap-3">
                <StatusIcon className={config.color} size={24} />
                <span className="text-lg font-medium">{config.label}</span>
              </div>
            </div>
          )}

          <div className="space-y-2 text-sm text-gray-600 mb-6">
            <p>
              <span className="text-gray-400">最后检查:</span>{" "}
              {status?.last_checked_at
                ? new Date(status.last_checked_at).toLocaleString()
                : "从未"}
            </p>
            <p>
              <span className="text-gray-400">最后成功:</span>{" "}
              {status?.last_success_at
                ? new Date(status.last_success_at).toLocaleString()
                : "从未"}
            </p>
            {status?.expire_time && (
              <p>
                <span className="text-gray-400">过期时间:</span>{" "}
                {new Date(status.expire_time).toLocaleString()}
              </p>
            )}
            {status?.message && (
              <p>
                <span className="text-gray-400">消息:</span>{" "}
                {status.message}
              </p>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => checkAdapterMutation.mutate()}
              disabled={checkAdapterMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={checkAdapterMutation.isPending ? "animate-spin" : ""}
              />
              刷新状态
            </button>
            <a
              href={adapterLoginUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
            >
              <ExternalLink size={16} />
              打开登录页
            </a>
          </div>
        </div>

        <div className="bg-white rounded-lg border p-6 shadow-sm">
          <h2 className="font-semibold mb-4">扫码登录</h2>

          <div className="flex flex-col items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed">
            <div className="text-center text-gray-500">
              <ExternalLink size={48} className="mx-auto mb-3 text-gray-300" />
              <p className="text-sm mb-1">点击按钮打开微信适配器登录页面</p>
              <p className="text-xs text-gray-400 mb-4">
                在适配器页面完成扫码登录后，返回此页面刷新状态
              </p>
              <a
                href={adapterLoginUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-6 py-3 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
              >
                <ExternalLink size={16} />
                打开登录页面
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border p-6 mt-6 shadow-sm">
        <h2 className="font-semibold mb-4">适配器状态</h2>
        <div className="flex items-center gap-3">
          {status?.status === "logged_in" ? (
            <>
              <CheckCircle className="text-green-500" size={20} />
              <span className="text-sm text-green-600">微信适配器已连接</span>
            </>
          ) : (
            <>
              <AlertCircle className="text-amber-500" size={20} />
              <span className="text-sm text-amber-600">
                微信适配器运行中，但尚未登录
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
