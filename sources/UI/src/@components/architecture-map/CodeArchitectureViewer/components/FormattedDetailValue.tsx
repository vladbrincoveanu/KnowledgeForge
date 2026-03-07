import React from "react";

interface FormattedDetailValueProps {
  value: unknown;
  className?: string;
  preserveWhitespace?: boolean;
}

/**
 * Renders inspector values with basic structure so multiline text, arrays, and
 * metadata objects remain readable inside the details panel.
 */
export default function FormattedDetailValue({
  value,
  className = "",
  preserveWhitespace = false,
}: FormattedDetailValueProps) {
  if (value == null || value === "") {
    return <span className={`detail-value ${className}`.trim()}>-</span>;
  }

  if (Array.isArray(value)) {
    const items = value
      .flatMap((item) => normalizeListItem(item))
      .filter(Boolean);

    if (items.length === 0) {
      return <span className={`detail-value ${className}`.trim()}>-</span>;
    }

    return (
      <ul className={`detail-value detail-list ${className}`.trim()}>
        {items.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    );
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value).filter(([, entryValue]) =>
      hasRenderableValue(entryValue),
    );

    if (entries.length === 0) {
      return <span className={`detail-value ${className}`.trim()}>-</span>;
    }

    return (
      <dl className={`detail-value detail-kv-list ${className}`.trim()}>
        {entries.map(([key, entryValue]) => (
          <React.Fragment key={key}>
            <dt>{humanizeKey(key)}</dt>
            <dd>{stringifyValue(entryValue)}</dd>
          </React.Fragment>
        ))}
      </dl>
    );
  }

  const normalizedValue = stringifyValue(value);
  const listItems =
    typeof value === "string" ? splitListLikeString(normalizedValue) : [];

  if (listItems.length > 1) {
    return (
      <ul className={`detail-value detail-list ${className}`.trim()}>
        {listItems.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    );
  }

  return (
    <span
      className={`detail-value ${preserveWhitespace ? "preserve-whitespace" : ""} ${className}`.trim()}
    >
      {normalizedValue}
    </span>
  );
}

function hasRenderableValue(value: unknown): boolean {
  if (value == null || value === "") {
    return false;
  }

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  if (isPlainObject(value)) {
    return Object.keys(value).length > 0;
  }

  return true;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringifyValue(value: unknown): string {
  if (value == null) {
    return "-";
  }

  if (typeof value === "string") {
    return value.trim() || "-";
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => stringifyValue(item)).join(", ");
  }

  if (isPlainObject(value)) {
    return Object.entries(value)
      .map(
        ([key, entryValue]) =>
          `${humanizeKey(key)}: ${stringifyValue(entryValue)}`,
      )
      .join(" | ");
  }

  return String(value);
}

function normalizeListItem(value: unknown): string[] {
  if (value == null || value === "") {
    return [];
  }

  if (isPlainObject(value)) {
    return [
      Object.entries(value)
        .map(
          ([key, entryValue]) =>
            `${humanizeKey(key)}: ${stringifyValue(entryValue)}`,
        )
        .join(" | "),
    ];
  }

  return splitListLikeString(stringifyValue(value));
}

function splitListLikeString(value: string): string[] {
  if (!value) {
    return [];
  }

  if (value.includes("\n")) {
    return value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  if (value.includes(";")) {
    return value
      .split(";")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return [value.trim()];
}

function humanizeKey(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^./, (char) => char.toUpperCase());
}
