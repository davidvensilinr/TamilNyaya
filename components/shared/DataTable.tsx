'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';

interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  keyExtractor: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function DataTable<T>({
  columns,
  data,
  total,
  page = 0,
  pageSize = 20,
  onPageChange,
  keyExtractor,
  onRowClick,
  emptyMessage = 'No data available.',
}: DataTableProps<T>) {
  const totalPages = total != null ? Math.ceil(total / pageSize) : 1;

  if (data.length === 0) {
    return (
      <div className="border border-[#263540] bg-[#101922] rounded p-10 text-center text-sm text-[#718592]">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="border border-[#263540] bg-[#101922] rounded overflow-x-auto">
      <table className="w-full min-w-[600px] border-collapse">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`text-left text-[10px] font-medium text-[#718592] uppercase tracking-wider px-4 py-3 border-b border-[#263540] ${col.className ?? ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={keyExtractor(row)}
              onClick={() => onRowClick?.(row)}
              className={`border-b border-[#1d2b34] last:border-b-0 ${
                onRowClick ? 'cursor-pointer hover:bg-[#172832]' : ''
              }`}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-4 py-3 text-[11px] text-[#a8b8c0] ${col.className ?? ''}`}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {total != null && onPageChange && totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-[#263540] text-[11px] text-[#718592]">
          <span>
            Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
          </span>
          <div className="flex gap-1">
            <button
              disabled={page === 0}
              onClick={() => onPageChange(page - 1)}
              className="p-1 rounded hover:bg-[#1d2b34] disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => onPageChange(page + 1)}
              className="p-1 rounded hover:bg-[#1d2b34] disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
