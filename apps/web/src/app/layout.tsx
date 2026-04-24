import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "OmniNewsFlow",
    template: "%s | OmniNewsFlow",
  },
  description: "本地微信智能简报系统",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    apple: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
