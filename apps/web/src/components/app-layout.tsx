"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  Users,
  KeyRound,
  Settings,
  Workflow,
  FileText,
  Zap,
  BookOpen,
  ScrollText,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { href: "/", label: "仪表盘", icon: LayoutDashboard },
  { href: "/wechat", label: "微信登录", icon: MessageSquare },
  { href: "/accounts", label: "来源管理", icon: Users },
  { href: "/keywords", label: "关键词管理", icon: KeyRound },
  { href: "/providers", label: "模型配置", icon: Settings },
  { href: "/workflows", label: "工作流", icon: Workflow },
  { href: "/articles", label: "文章列表", icon: FileText },
  { href: "/events", label: "事件列表", icon: Zap },
  { href: "/digests", label: "每日摘要", icon: BookOpen },
  { href: "/logs", label: "任务日志", icon: ScrollText },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      <button
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-md shadow"
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-white border-r transform transition-transform lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-6 border-b">
          <h1 className="text-lg font-bold">OmniNewsFlow</h1>
          <p className="text-xs text-gray-500">智能新闻简报系统</p>
        </div>
        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-gray-900 text-white"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="lg:ml-64 min-h-screen">
        <div className="p-6 lg:p-8 max-w-7xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
