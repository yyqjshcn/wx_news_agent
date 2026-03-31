"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { FileText, Download, Send, RefreshCw } from "lucide-react";

export default function DigestsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: digests, isLoading } = useQuery({
    queryKey: ["digests"],
    queryFn: () => api.get("/api/digests"),
  });

  const { data: selectedDigest } = useQuery({
    queryKey: ["digest", selectedId],
    queryFn: () => api.get(`/api/digests/${selectedId}`),
    enabled: !!selectedId,
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      api.post("/api/digests/generate", { digest_date: new Date().toISOString() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["digests"] });
    },
  });

  const sendTestMutation = useMutation({
    mutationFn: (id: string) =>
      api.post(`/api/digests/${id}/send-test`, { email: "test@example.com" }),
    onSuccess: () => {
      alert("Test email sent!");
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Daily Digests</h1>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
        >
          <RefreshCw
            size={16}
            className={generateMutation.isPending ? "animate-spin" : ""}
          />
          Generate Today
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border shadow-sm">
            <div className="p-4 border-b">
              <h2 className="font-semibold">History</h2>
            </div>
            <div className="divide-y max-h-[600px] overflow-y-auto">
              {isLoading && (
                <div className="p-4 text-center text-gray-400">Loading...</div>
              )}
              {digests?.map((d: any) => (
                <button
                  key={d.id}
                  onClick={() => setSelectedId(d.id)}
                  className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                    selectedId === d.id ? "bg-gray-50" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText size={16} className="text-gray-400" />
                      <span className="text-sm font-medium">
                        {new Date(d.digest_date).toLocaleDateString()}
                      </span>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs ${
                        d.status === "sent"
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {d.status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {d.item_count} items
                  </div>
                </button>
              ))}
              {digests?.length === 0 && !isLoading && (
                <div className="p-8 text-center text-gray-400 text-sm">
                  No digests generated yet
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          {selectedDigest ? (
            <div className="bg-white rounded-lg border shadow-sm">
              <div className="p-4 border-b flex items-center justify-between">
                <h2 className="font-semibold">
                  {new Date(selectedDigest.digest_date).toLocaleDateString()}
                </h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => sendTestMutation.mutate(selectedDigest.id)}
                    className="flex items-center gap-1 px-3 py-1.5 border rounded-md text-sm hover:bg-gray-50"
                  >
                    <Send size={14} />
                    Test Send
                  </button>
                  <button className="flex items-center gap-1 px-3 py-1.5 border rounded-md text-sm hover:bg-gray-50">
                    <Download size={14} />
                    Export
                  </button>
                </div>
              </div>
              <div className="p-6">
                <div className="prose prose-sm max-w-none">
                  <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-lg">
                    {selectedDigest.content_markdown || "No content"}
                  </pre>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg border shadow-sm flex items-center justify-center h-96 text-gray-400">
              Select a digest to view
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
