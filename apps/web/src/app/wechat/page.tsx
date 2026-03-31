"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { RefreshCw, QrCode, AlertCircle, CheckCircle } from "lucide-react";

export default function WeChatPage() {
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ["wechat-status"],
    queryFn: () => api.get("/api/wechat/status"),
    refetchInterval: 30000,
  });

  const refreshQrMutation = useMutation({
    mutationFn: () => api.post("/api/wechat/refresh-qr"),
    onSuccess: (data) => {
      setQrUrl(data.qr_url || null);
      queryClient.invalidateQueries({ queryKey: ["wechat-status"] });
    },
  });

  const checkMutation = useMutation({
    mutationFn: () => api.post("/api/wechat/check"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wechat-status"] });
    },
  });

  const statusConfig: Record<string, { color: string; icon: any; label: string }> = {
    logged_in: { color: "text-green-600", icon: CheckCircle, label: "Logged In" },
    expired: { color: "text-amber-600", icon: AlertCircle, label: "Session Expired" },
    error: { color: "text-red-600", icon: AlertCircle, label: "Error" },
    unknown: { color: "text-gray-400", icon: AlertCircle, label: "Unknown" },
  };

  const config = statusConfig[status?.status] || statusConfig.unknown;
  const StatusIcon = config.icon;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">WeChat Login</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-6 shadow-sm">
          <h2 className="font-semibold mb-4">Login Status</h2>
          <div className="flex items-center gap-3 mb-4">
            <StatusIcon className={config.color} size={24} />
            <span className="text-lg font-medium">{config.label}</span>
          </div>

          <div className="space-y-2 text-sm text-gray-600 mb-6">
            <p>
              <span className="text-gray-400">Last checked:</span>{" "}
              {status?.last_checked_at
                ? new Date(status.last_checked_at).toLocaleString()
                : "Never"}
            </p>
            <p>
              <span className="text-gray-400">Last success:</span>{" "}
              {status?.last_success_at
                ? new Date(status.last_success_at).toLocaleString()
                : "Never"}
            </p>
            {status?.message && (
              <p>
                <span className="text-gray-400">Message:</span>{" "}
                {status.message}
              </p>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => checkMutation.mutate()}
              disabled={checkMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={checkMutation.isPending ? "animate-spin" : ""}
              />
              Check Status
            </button>
            <button
              onClick={() => refreshQrMutation.mutate()}
              disabled={refreshQrMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
            >
              <QrCode size={16} />
              Refresh QR
            </button>
          </div>
        </div>

        <div className="bg-white rounded-lg border p-6 shadow-sm">
          <h2 className="font-semibold mb-4">QR Code</h2>
          {qrUrl ? (
            <div className="flex items-center justify-center">
              <img
                src={qrUrl}
                alt="WeChat Login QR"
                className="max-w-[250px] rounded-lg"
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed">
              <div className="text-center text-gray-400">
                <QrCode size={48} className="mx-auto mb-2" />
                <p className="text-sm">Click &quot;Refresh QR&quot; to generate</p>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg border p-6 mt-6 shadow-sm">
        <h2 className="font-semibold mb-4">Recent Errors</h2>
        <p className="text-sm text-gray-400">No recent errors</p>
      </div>
    </div>
  );
}
