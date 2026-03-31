"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState, useEffect, useRef } from "react";
import { RefreshCw, QrCode, AlertCircle, CheckCircle, Loader2, LogIn } from "lucide-react";

type LoginStep = "idle" | "session_created" | "showing_qr" | "scanned" | "confirmed" | "expired" | "error";

export default function WeChatPage() {
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [loginStep, setLoginStep] = useState<LoginStep>("idle");
  const [sessionId] = useState(() => `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  const [adapterReady, setAdapterReady] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const queryClient = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ["wechat-status"],
    queryFn: () => api.get("/api/wechat/status"),
    refetchInterval: 30000,
  });

  const checkAdapterMutation = useMutation({
    mutationFn: () => api.post("/api/wechat/refresh-qr"),
    onSuccess: (data) => {
      setAdapterReady(data.adapter_ready || false);
    },
  });

  const createSessionMutation = useMutation({
    mutationFn: async () => {
      const resp = await fetch(`/api/login/session/${sessionId}`, {
        method: "POST",
        credentials: "include",
      });
      return resp.json();
    },
    onSuccess: () => {
      setLoginStep("session_created");
      getQrMutation.mutate();
    },
    onError: () => {
      setLoginStep("error");
    },
  });

  const getQrMutation = useMutation({
    mutationFn: async () => {
      const resp = await fetch(`/api/login/getqrcode`, {
        method: "GET",
        credentials: "include",
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text);
      }
      const blob = await resp.blob();
      return URL.createObjectURL(blob);
    },
    onSuccess: (url) => {
      setQrUrl(url);
      setLoginStep("showing_qr");
      startPolling();
    },
    onError: () => {
      setLoginStep("error");
    },
  });

  const pollScanMutation = useMutation({
    mutationFn: async () => {
      const resp = await fetch(`/api/login/scan`, {
        method: "GET",
        credentials: "include",
      });
      return resp.json();
    },
    onSuccess: (data) => {
      const status = data.status;
      if (status === 1) {
        setLoginStep("confirmed");
        stopPolling();
        completeLoginMutation.mutate();
      } else if (status === 4 || status === 6) {
        setLoginStep("scanned");
      } else if (status === 3) {
        setLoginStep("expired");
        stopPolling();
      }
    },
  });

  const completeLoginMutation = useMutation({
    mutationFn: async () => {
      const resp = await fetch(`/api/login/bizlogin`, {
        method: "POST",
        credentials: "include",
      });
      return resp.json();
    },
    onSuccess: (data) => {
      if (data.success) {
        queryClient.invalidateQueries({ queryKey: ["wechat-status"] });
      }
    },
  });

  const startPolling = () => {
    stopPolling();
    pollRef.current = setInterval(() => {
      pollScanMutation.mutate();
    }, 2000);
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => {
    return () => stopPolling();
  }, []);

  const handleStartLogin = () => {
    setLoginStep("idle");
    setQrUrl(null);
    createSessionMutation.mutate();
  };

  const statusConfig: Record<string, { color: string; icon: any; label: string }> = {
    logged_in: { color: "text-green-600", icon: CheckCircle, label: "已登录" },
    expired: { color: "text-amber-600", icon: AlertCircle, label: "会话已过期" },
    error: { color: "text-red-600", icon: AlertCircle, label: "错误" },
    unknown: { color: "text-gray-400", icon: AlertCircle, label: "未知" },
  };

  const stepLabels: Record<LoginStep, string> = {
    idle: "准备就绪",
    session_created: "正在获取二维码...",
    showing_qr: "请使用微信扫描下方二维码",
    scanned: "已扫码，请在手机上确认登录",
    confirmed: "登录成功！",
    expired: "二维码已过期，请重新开始",
    error: "获取二维码失败",
  };

  const config = statusConfig[status?.status] || statusConfig.unknown;
  const StatusIcon = config.icon;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">微信登录</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-6 shadow-sm">
          <h2 className="font-semibold mb-4">登录状态</h2>
          <div className="flex items-center gap-3 mb-4">
            <StatusIcon className={config.color} size={24} />
            <span className="text-lg font-medium">{config.label}</span>
          </div>

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
              检查状态
            </button>
          </div>
        </div>

        <div className="bg-white rounded-lg border p-6 shadow-sm">
          <h2 className="font-semibold mb-4">扫码登录</h2>

          <div className="text-center mb-4">
            <p className="text-sm font-medium text-gray-700">{stepLabels[loginStep]}</p>
          </div>

          {qrUrl && loginStep === "showing_qr" || loginStep === "scanned" ? (
            <div className="flex flex-col items-center">
              <div className="relative">
                <img
                  src={qrUrl}
                  alt="微信登录二维码"
                  className="max-w-[250px] rounded-lg"
                />
                {loginStep === "scanned" && (
                  <div className="absolute inset-0 bg-white/80 flex items-center justify-center rounded-lg">
                    <div className="text-center">
                      <CheckCircle size={48} className="text-green-500 mx-auto mb-2" />
                      <p className="text-sm font-medium text-green-600">已扫码</p>
                      <p className="text-xs text-gray-500">请在手机上确认</p>
                    </div>
                  </div>
                )}
              </div>
              {loginStep === "showing_qr" && (
                <p className="text-xs text-gray-400 mt-3">二维码有效期 5 分钟</p>
              )}
            </div>
          ) : loginStep === "confirmed" ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <CheckCircle size={64} className="text-green-500 mx-auto mb-3" />
                <p className="text-lg font-medium text-green-600">登录成功！</p>
              </div>
            </div>
          ) : loginStep === "expired" ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center text-gray-400">
                <AlertCircle size={48} className="mx-auto mb-2" />
                <p className="text-sm">二维码已过期</p>
                <button
                  onClick={handleStartLogin}
                  className="mt-3 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
                >
                  重新开始
                </button>
              </div>
            </div>
          ) : loginStep === "error" ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center text-gray-400">
                <AlertCircle size={48} className="mx-auto mb-2" />
                <p className="text-sm">获取二维码失败</p>
                <p className="text-xs mt-1">请确认微信适配器已启动</p>
                <button
                  onClick={handleStartLogin}
                  className="mt-3 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800"
                >
                  重试
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed">
              <div className="text-center text-gray-400">
                <QrCode size={48} className="mx-auto mb-2" />
                <p className="text-sm mb-3">点击按钮开始扫码登录</p>
                <button
                  onClick={handleStartLogin}
                  disabled={createSessionMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50 mx-auto"
                >
                  {createSessionMutation.isPending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <LogIn size={16} />
                  )}
                  开始登录
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg border p-6 mt-6 shadow-sm">
        <h2 className="font-semibold mb-4">适配器状态</h2>
        <div className="flex items-center gap-3">
          {adapterReady ? (
            <>
              <CheckCircle className="text-green-500" size={20} />
              <span className="text-sm text-green-600">微信适配器已连接</span>
            </>
          ) : (
            <>
              <AlertCircle className="text-red-500" size={20} />
              <span className="text-sm text-red-600">微信适配器未连接，请确保已启动 wechat-download-api</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
