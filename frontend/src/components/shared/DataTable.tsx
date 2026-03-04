'use client';

import * as React from 'react';
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Save,
  Trash2,
} from 'lucide-react';

export type DataTableDensity = 'default' | 'compact';

export interface DataTableColumnMeta {
  align?: 'left' | 'right' | 'center';
  widthClass?: string;
}

export type DataTableColumnDef<TData, TValue = unknown> = ColumnDef<TData, TValue> & {
  meta?: DataTableColumnMeta;
};

interface SavedView {
  name: string;
  symbol?: string;
  status?: string;
  fromDate?: string;
  toDate?: string;
  sorting?: SortingState;
  pageSize?: number;
}

export interface DataTableProps<TData> {
  data: TData[];
  columns: DataTableColumnDef<TData, unknown>[];
  getRowId?: (row: TData, index: number) => string;
  density?: DataTableDensity;
  presetKey?: string;
  initialSorting?: SortingState;
  defaultPageSize?: number;
  pageSizeOptions?: number[];
  getSymbol?: (row: TData) => string | null | undefined;
  getStatus?: (row: TData) => string | null | undefined;
  getDate?: (row: TData) => string | null | undefined;
  selectedRowId?: string | null;
  onRowClick?: (row: TData) => void;
  className?: string;
}

export function DataTable<TData>({
  data,
  columns,
  getRowId,
  density = 'compact',
  presetKey,
  initialSorting,
  defaultPageSize = 25,
  pageSizeOptions = [25, 50, 100],
  getSymbol,
  getStatus,
  getDate,
  selectedRowId,
  onRowClick,
  className,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = React.useState<SortingState>(initialSorting ?? []);
  const [pagination, setPagination] = React.useState({
    pageIndex: 0,
    pageSize: defaultPageSize,
  });
  const [symbolFilter, setSymbolFilter] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState('');
  const [fromDate, setFromDate] = React.useState('');
  const [toDate, setToDate] = React.useState('');
  const [savedViews, setSavedViews] = React.useState<SavedView[]>([]);
  const [activeViewName, setActiveViewName] = React.useState<string>('default');

  const storageKey = React.useMemo(
    () => (presetKey ? `galil:datatable:${presetKey}:views` : null),
    [presetKey],
  );

  React.useEffect(() => {
    if (!storageKey || typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return;
      const parsed = JSON.parse(raw) as SavedView[];
      if (Array.isArray(parsed)) {
        setSavedViews(parsed);
      }
    } catch {
      // ignore invalid localStorage state
    }
  }, [storageKey]);

  const persistViews = React.useCallback(
    (views: SavedView[]) => {
      if (!storageKey || typeof window === 'undefined') return;
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(views));
      } catch {
        // ignore quota/serialization issues
      }
    },
    [storageKey],
  );

  const applyView = React.useCallback(
    (viewName: string) => {
      setActiveViewName(viewName);
      if (viewName === 'default') {
        setSymbolFilter('');
        setStatusFilter('');
        setFromDate('');
        setToDate('');
        setSorting(initialSorting ?? []);
        setPagination((prev) => ({ ...prev, pageIndex: 0, pageSize: defaultPageSize }));
        return;
      }
      const view = savedViews.find((v) => v.name === viewName);
      if (!view) return;
      setSymbolFilter(view.symbol ?? '');
      setStatusFilter(view.status ?? '');
      setFromDate(view.fromDate ?? '');
      setToDate(view.toDate ?? '');
      setSorting(view.sorting ?? []);
      setPagination((prev) => ({
        ...prev,
        pageIndex: 0,
        pageSize: view.pageSize ?? defaultPageSize,
      }));
    },
    [savedViews, defaultPageSize, initialSorting],
  );

  const handleSaveView = React.useCallback(() => {
    if (!storageKey) return;
    // eslint-disable-next-line no-alert
    const name = window.prompt('Save current view as:');
    if (!name) return;
    const next: SavedView = {
      name,
      symbol: symbolFilter || undefined,
      status: statusFilter || undefined,
      fromDate: fromDate || undefined,
      toDate: toDate || undefined,
      sorting,
      pageSize: pagination.pageSize,
    };
    setSavedViews((prev) => {
      const without = prev.filter((v) => v.name !== name);
      const merged = [...without, next];
      persistViews(merged);
      return merged;
    });
    setActiveViewName(name);
  }, [
    storageKey,
    symbolFilter,
    statusFilter,
    fromDate,
    toDate,
    sorting,
    pagination.pageSize,
    persistViews,
  ]);

  const handleDeleteView = React.useCallback(() => {
    if (!storageKey || activeViewName === 'default') return;
    setSavedViews((prev) => {
      const filtered = prev.filter((v) => v.name !== activeViewName);
      persistViews(filtered);
      return filtered;
    });
    setActiveViewName('default');
    applyView('default');
  }, [storageKey, activeViewName, applyView, persistViews]);

  const filteredData = React.useMemo(() => {
    if (
      !symbolFilter &&
      !statusFilter &&
      !fromDate &&
      !toDate
    ) {
      return data;
    }

    const from = fromDate ? new Date(fromDate) : null;
    const to = toDate ? new Date(toDate) : null;
    if (to) {
      to.setHours(23, 59, 59, 999);
    }

    return data.filter((row) => {
      if (symbolFilter && getSymbol) {
        const sym = (getSymbol(row) || '').toLowerCase();
        if (!sym.includes(symbolFilter.toLowerCase())) return false;
      }
      if (statusFilter && getStatus) {
        const st = (getStatus(row) || '').toLowerCase();
        if (!st.includes(statusFilter.toLowerCase())) return false;
      }
      if ((from || to) && getDate) {
        const raw = getDate(row);
        if (raw) {
          const d = new Date(raw);
          if (from && d < from) return false;
          if (to && d > to) return false;
        }
      }
      return true;
    });
  }, [data, symbolFilter, statusFilter, fromDate, toDate, getSymbol, getStatus, getDate]);

  const table = useReactTable({
    data: filteredData,
    columns,
    state: {
      sorting,
      pagination,
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getRowId: (original, index) => (getRowId ? getRowId(original, index) : String(index)),
  });

  const densityHeadClass =
    density === 'compact'
      ? 'h-8 px-2 py-1 text-[10px]'
      : 'h-9 px-3 py-2 text-xs';
  const densityCellClass =
    density === 'compact'
      ? 'px-2 py-1 text-[11px]'
      : 'px-3 py-1.5 text-sm';

  const totalRows = filteredData.length;
  const { pageIndex, pageSize } = table.getState().pagination;
  const start = totalRows === 0 ? 0 : pageIndex * pageSize + 1;
  const end = Math.min(totalRows, (pageIndex + 1) * pageSize);

  const canFilter = !!(getSymbol || getStatus || getDate);
  const canPersistViews = !!presetKey;

  return (
    <div className={cn('flex h-full min-h-0 flex-col overflow-hidden', className)}>
      {canFilter && (
        <div className='flex flex-wrap items-center justify-between gap-2 border-b border-[var(--to-border)] bg-[var(--to-surface)] px-2.5 py-1.5'>
          <div className='flex flex-wrap items-center gap-2'>
            {getSymbol && (
              <input
                value={symbolFilter}
                onChange={(e) => {
                  setSymbolFilter(e.target.value);
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }));
                }}
                placeholder='Symbol'
                className='h-7 rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 text-[11px] text-[var(--to-text-secondary)] outline-none placeholder:text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              />
            )}
            {getStatus && (
              <input
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPagination((prev) => ({ ...prev, pageIndex: 0 }));
                }}
                placeholder='Status'
                className='h-7 rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 text-[11px] text-[var(--to-text-secondary)] outline-none placeholder:text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              />
            )}
            {getDate && (
              <>
                <input
                  type='date'
                  value={fromDate}
                  onChange={(e) => {
                    setFromDate(e.target.value);
                    setPagination((prev) => ({ ...prev, pageIndex: 0 }));
                  }}
                  className='h-7 rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 text-[11px] text-[var(--to-text-secondary)] outline-none placeholder:text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                />
                <span className='text-[10px] text-[var(--to-text-dim)]'>to</span>
                <input
                  type='date'
                  value={toDate}
                  onChange={(e) => {
                    setToDate(e.target.value);
                    setPagination((prev) => ({ ...prev, pageIndex: 0 }));
                  }}
                  className='h-7 rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 text-[11px] text-[var(--to-text-secondary)] outline-none placeholder:text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                />
              </>
            )}
          </div>

          {canPersistViews && (
            <div className='flex items-center gap-1.5'>
              <select
                value={activeViewName}
                onChange={(e) => applyView(e.target.value)}
                className='h-7 rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 text-[11px] text-[var(--to-text-secondary)] outline-none'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                <option value='default'>Default view</option>
                {savedViews
                  .slice()
                  .sort((a, b) => a.name.localeCompare(b.name))
                  .map((view) => (
                    <option key={view.name} value={view.name}>
                      {view.name}
                    </option>
                  ))}
              </select>
              <button
                type='button'
                onClick={handleSaveView}
                className='inline-flex h-7 items-center justify-center rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 text-[10px] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface)]'
              >
                <Save className='mr-1 h-3 w-3' />
                Save
              </button>
              <button
                type='button'
                onClick={handleDeleteView}
                disabled={activeViewName === 'default'}
                className='inline-flex h-7 items-center justify-center rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 text-[10px] text-[var(--to-text-dim)] hover:bg-[var(--to-surface)] disabled:opacity-40'
              >
                <Trash2 className='mr-1 h-3 w-3' />
                Delete
              </button>
            </div>
          )}
        </div>
      )}

      <div className='min-h-0 flex-1 overflow-auto'>
        {totalRows === 0 ? (
          <div className='flex h-full items-center justify-center px-4 py-8'>
            <span
              className='text-[11px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              No rows to display
            </span>
          </div>
        ) : (
          <Table className={cn('text-sm', density === 'compact' && 'text-[11px]')}>
            <TableHeader className='sticky top-0 z-10 bg-[var(--to-surface)]'>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    if (header.isPlaceholder) {
                      return <TableHead key={header.id} />;
                    }
                    const isSorted = header.column.getIsSorted();
                    const meta = header.column.columnDef
                      .meta as DataTableColumnMeta | undefined;
                    const align =
                      meta?.align === 'right'
                        ? 'text-right justify-end'
                        : meta?.align === 'center'
                          ? 'text-center justify-center'
                          : 'text-left justify-start';

                    return (
                      <TableHead
                        key={header.id}
                        className={cn(
                          'align-middle font-mono uppercase tracking-wider text-[var(--to-text-dim)]',
                          densityHeadClass,
                          align,
                          meta?.widthClass,
                          header.column.getCanSort() &&
                            'cursor-pointer select-none hover:text-[var(--to-text-secondary)]',
                        )}
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        <span className='inline-flex items-center gap-1'>
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          {header.column.getCanSort() && (
                            <>
                              {isSorted === 'asc' && (
                                <ArrowUp className='h-3 w-3 opacity-80' />
                              )}
                              {isSorted === 'desc' && (
                                <ArrowDown className='h-3 w-3 opacity-80' />
                              )}
                              {!isSorted && (
                                <ChevronsUpDown className='h-3 w-3 opacity-40' />
                              )}
                            </>
                          )}
                        </span>
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.id === selectedRowId ? 'selected' : undefined}
                  className={cn(
                    'cursor-pointer',
                    density === 'compact' && 'text-[11px]',
                  )}
                  onClick={() => onRowClick?.(row.original)}
                >
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef
                      .meta as DataTableColumnMeta | undefined;
                    const align =
                      meta?.align === 'right'
                        ? 'text-right'
                        : meta?.align === 'center'
                          ? 'text-center'
                          : 'text-left';
                    const numeric =
                      meta?.align === 'right' ? 'tabular-nums' : undefined;

                    return (
                      <TableCell
                        key={cell.id}
                        className={cn(
                          densityCellClass,
                          align,
                          numeric,
                          meta?.widthClass,
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {totalRows > 0 && (
        <div className='flex items-center justify-between border-t border-[var(--to-border)] bg-[var(--to-surface)] px-2.5 py-1.5'>
          <div
            className='text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {start === 0
              ? 'No rows'
              : `Showing ${start}-${end} of ${totalRows}`}
          </div>
          <div className='flex items-center gap-2'>
            <div className='flex items-center gap-1'>
              <span className='text-[10px] text-[var(--to-text-dim)]'>
                Rows per page
              </span>
              <select
                value={pageSize}
                onChange={(e) =>
                  setPagination((prev) => ({
                    ...prev,
                    pageIndex: 0,
                    pageSize: Number(e.target.value),
                  }))
                }
                className='h-7 rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-1.5 text-[10px] text-[var(--to-text-secondary)] outline-none'
              >
                {pageSizeOptions.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </div>
            <div className='flex items-center gap-1'>
              <button
                type='button'
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
                className='inline-flex h-7 w-7 items-center justify-center rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] disabled:opacity-40'
              >
                <ChevronLeft className='h-3 w-3' />
              </button>
              <button
                type='button'
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
                className='inline-flex h-7 w-7 items-center justify-center rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] disabled:opacity-40'
              >
                <ChevronRight className='h-3 w-3' />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

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
          'w-full',
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

