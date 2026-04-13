"use client";

import { useCallback, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  const [jumpInput, setJumpInput] = useState("");

  const getPageNumbers = (): (number | "...")[] => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i);
    }

    const pages: (number | "...")[] = [];
    pages.push(0);

    if (currentPage <= 2) {
      pages.push(1, 2, 3, "...", totalPages - 1);
    } else if (currentPage >= totalPages - 3) {
      pages.push("...", totalPages - 3, totalPages - 2, totalPages - 1);
    } else {
      pages.push("...", currentPage - 1, currentPage, currentPage + 1, "...", totalPages - 1);
    }

    return pages;
  };

  const handleJump = useCallback(() => {
    const num = parseInt(jumpInput, 10);
    if (!isNaN(num) && num >= 1 && num <= totalPages) {
      onPageChange(num - 1);
      setJumpInput("");
    }
  }, [jumpInput, onPageChange, totalPages]);

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t">
      <span className="text-sm text-gray-500">
        共 {totalPages} 页
      </span>

      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(Math.max(0, currentPage - 1))}
          disabled={currentPage === 0}
          className="flex items-center gap-1 px-2 py-1.5 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft size={14} />
          上一页
        </button>

        <div className="flex items-center gap-0.5 mx-1">
          {getPageNumbers().map((p, i) =>
            p === "..." ? (
              <span key={`ellipsis-${i}`} className="px-2 py-1.5 text-sm text-gray-400">
                ...
              </span>
            ) : (
              <button
                key={`page-${p}`}
                onClick={() => onPageChange(p as number)}
                className={`min-w-[32px] h-8 px-2 py-1 text-sm rounded-md border transition-colors ${
                  p === currentPage
                    ? "bg-blue-600 text-white border-blue-600 hover:bg-blue-700"
                    : "text-gray-700 border-gray-200 hover:bg-gray-50"
                }`}
              >
                {(p as number) + 1}
              </button>
            )
          )}
        </div>

        <button
          onClick={() => onPageChange(Math.min(totalPages - 1, currentPage + 1))}
          disabled={currentPage >= totalPages - 1}
          className="flex items-center gap-1 px-2 py-1.5 border rounded-md text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          下一页
          <ChevronRight size={14} />
        </button>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">跳至</span>
        <input
          type="number"
          min={1}
          max={totalPages}
          value={jumpInput}
          onChange={(e) => setJumpInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleJump()}
          className="w-16 h-8 px-2 py-1 border rounded-md text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="页码"
        />
        <span className="text-sm text-gray-500">页</span>
        <button
          onClick={handleJump}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
        >
          GO
        </button>
      </div>
    </div>
  );
}
