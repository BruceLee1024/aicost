/**
 * BizTable — Excel-style dense editable table for cost software.
 *
 * Thin wrapper around antd Table that:
 *   - Applies the `.biz-table` CSS class set (dense, gridded, striped)
 *   - Defaults to `size="small"`, bordered, sticky header on scroll
 *   - Optionally adds a 序号 (row index) leading column
 *   - Tags parent / total rows via `rowClassName` helpers
 *   - Sane defaults for pagination (compact, with size switcher)
 *
 * All antd Table props pass through, so any existing `<Table>` call site
 * can be migrated by simply renaming the import.
 *
 * Helpers exported alongside:
 *   - bizCellNum(value, opts)   — formatted right-aligned numeric cell
 *   - bizCellCode(value, onCopy) — copyable code cell
 *   - bizRowClass({ isParent, isTotal }) — row class util
 */
import { Table } from "antd";
import type { TableProps } from "antd";
import type { ColumnsType, ColumnType } from "antd/es/table";
import { useMemo } from "react";

export interface BizTableProps<RecordType> extends TableProps<RecordType> {
  /** Add a leading 序号 column (1-based, follows current page). Default false. */
  showIndex?: boolean;
  /** Pixel width of the index column. Default 56. */
  indexWidth?: number;
  /** Use ultra-compact density (smaller padding + font). Default false. */
  ultraCompact?: boolean;
  /** Predicate marking a row as a parent/group row (visually emphasised). */
  isParentRow?: (record: RecordType, index: number) => boolean;
  /** Predicate marking a row as a totals row. */
  isTotalRow?: (record: RecordType, index: number) => boolean;
}

export function BizTable<RecordType extends object = any>({
  showIndex = false,
  indexWidth = 56,
  ultraCompact = false,
  isParentRow,
  isTotalRow,
  columns,
  className,
  rowClassName,
  size = "small",
  pagination,
  ...rest
}: BizTableProps<RecordType>) {
  // Build final columns: prepend 序号 column if requested.
  const finalColumns = useMemo<ColumnsType<RecordType> | undefined>(() => {
    if (!showIndex || !columns) return columns;
    const indexCol: ColumnType<RecordType> = {
      title: "序号",
      key: "_biz_index",
      width: indexWidth,
      align: "center",
      className: "biz-cell-index",
      render: (_v, _r, idx) => idx + 1,
    };
    return [indexCol, ...columns];
  }, [columns, showIndex, indexWidth]);

  // Compose row class name combining caller + parent/total flags.
  const composedRowClassName = (record: RecordType, index: number, indent: number) => {
    const classes: string[] = [];
    if (typeof rowClassName === "function") {
      classes.push(rowClassName(record, index, indent) ?? "");
    } else if (typeof rowClassName === "string") {
      classes.push(rowClassName);
    }
    if (isParentRow?.(record, index)) classes.push("biz-table-row-parent");
    if (isTotalRow?.(record, index)) classes.push("biz-table-row-total");
    return classes.filter(Boolean).join(" ");
  };

  const cls = [
    "biz-table",
    ultraCompact ? "biz-table--ultracompact" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  // Default pagination — compact + size switcher, but only when caller has
  // not opted out (`pagination={false}`) or supplied their own object.
  const finalPagination =
    pagination === false
      ? false
      : {
          showSizeChanger: true,
          pageSizeOptions: ["20", "50", "100"],
          showTotal: (t: number) => `共 ${t} 条`,
          ...(typeof pagination === "object" && pagination !== null
            ? pagination
            : {}),
        };

  return (
    <Table<RecordType>
      {...rest}
      size={size}
      bordered
      columns={finalColumns}
      rowClassName={composedRowClassName}
      pagination={finalPagination}
      className={cls}
    />
  );
}

// ─── Cell helpers ────────────────────────────────────────────────

/** Render a right-aligned numeric cell. Empty when value is 0/null/undefined. */
export function bizCellNum(
  value: number | null | undefined,
  opts: { decimals?: number; suffix?: string; emptyChar?: string } = {},
) {
  const { decimals = 2, suffix = "", emptyChar = "·" } = opts;
  if (value == null || value === 0 || !isFinite(value)) {
    return (
      <span className="biz-cell-num biz-cell-num-muted" style={{ display: "block" }}>
        {emptyChar}
      </span>
    );
  }
  return (
    <span className="biz-cell-num" style={{ display: "block" }}>
      {value.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/** Render a clickable monospaced code cell that copies on click. */
export function bizCellCode(value: string, onCopy?: (v: string) => void) {
  if (!value) return null;
  return (
    <span
      className="biz-cell-code"
      onClick={(e) => {
        e.stopPropagation();
        onCopy?.(value);
      }}
    >
      {value}
    </span>
  );
}

export default BizTable;
