'use client';

import * as React from 'react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';

export type DataTableColumn<T> = {
  /** Stable column id */
  id: string;
  /** Header label or custom node (can include sort controls) */
  header: React.ReactNode;
  /** Custom cell renderer for a given row */
  render: (row: T) => React.ReactNode;
  /** Text alignment – numeric columns should generally be right-aligned */
  align?: 'left' | 'right' | 'center';
  /** Marks a column as numeric – enables right alignment + tabular mono */
  isNumeric?: boolean;
  /** Optional fixed width utility (e.g. w-[80px]) */
  width?: string;
};

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  /**
   * Optional row id resolver. Falls back to the array index if omitted.
   */
  getRowId?: (row: T, index: number) => string | number;
  /**
   * Optional row click handler for interactive tables.
   */
  onRowClick?: (row: T) => void;
  /**
   * Enables sticky header styling using the terminal surface tokens.
   */
  stickyHeader?: boolean;
  /**
   * Compact density – applies the shared `table-dense` token.
   */
  compact?: boolean;
  /**
   * Wrapper div class (scroll container).
   */
  className?: string;
  /**
   * Additional class names applied to the underlying `<table>`.
   */
  tableClassName?: string;
  /**
   * Optional per-row className resolver for advanced layouts.
   */
  getRowClassName?: (row: T, index: number) => string;
}

export function DataTable<T>({
  columns,
  data,
  getRowId,
  onRowClick,
  stickyHeader = false,
  compact = true,
  className,
  tableClassName,
  getRowClassName,
}: DataTableProps<T>) {
  const headerBase =
    'font-mono text-[10px] text-text-dim uppercase tracking-wider py-2 px-3 whitespace-nowrap';

  return (
    <div className={cn('overflow-auto scrollbar-thin', className)}>
      <Table
        className={cn(
          'w-full min-w-max',
          compact && 'table-dense',
          // Ensure base terminal table typography
          'text-xs',
          tableClassName,
        )}
      >
        <TableHeader
          className={cn(
            '[&_tr]:border-b border-panel-border-subtle',
            stickyHeader &&
              'sticky top-0 z-10 bg-surface/95 backdrop-blur-sm supports-[backdrop-filter]:bg-surface/80',
          )}
        >
          <TableRow className='hover:bg-transparent'>
            {columns.map((col) => {
              const align = col.align ?? (col.isNumeric ? 'right' : 'left');
              return (
                <TableHead
                  key={col.id}
                  className={cn(
                    headerBase,
                    col.width,
                    align === 'right'
                      ? 'text-right'
                      : align === 'center'
                        ? 'text-center'
                        : 'text-left',
                  )}
                >
                  {col.header}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row, index) => {
            const rowKey = getRowId?.(row, index) ?? index;
            const baseRowClass =
              'data-row border-b border-panel-border-subtle last:border-b-0 cursor-pointer transition-colors duration-100 hover:bg-surface-raised';

            return (
              <TableRow
                key={rowKey}
                className={cn(
                  baseRowClass,
                  typeof getRowClassName === 'function'
                    ? getRowClassName(row, index)
                    : null,
                )}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => {
                  const align = col.align ?? (col.isNumeric ? 'right' : 'left');
                  return (
                    <TableCell
                      key={col.id}
                      className={cn(
                        'px-2 py-1.5 align-middle',
                        col.width,
                        align === 'right'
                          ? 'text-right'
                          : align === 'center'
                            ? 'text-center'
                            : 'text-left',
                        col.isNumeric && 'font-mono tabular-nums',
                      )}
                    >
                      {col.render(row)}
                    </TableCell>
                  );
                })}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

