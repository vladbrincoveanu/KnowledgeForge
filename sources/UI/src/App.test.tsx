/* @vitest-environment jsdom */

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import App from "./App";

const { wsServiceMock } = vi.hoisted(() => ({
  wsServiceMock: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  },
}));

const fetchMock = vi.fn();

vi.mock("./services/api", () => ({
  wsService: wsServiceMock,
}));

vi.mock(
  "./@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer",
  () => ({
    default: () => <div>Mock architecture viewer</div>,
  }),
);

vi.mock("./@components/notification/Notification", () => ({
  default: () => null,
}));

vi.mock("./@components/upload-extract/FileUploader/FileUploader", () => ({
  default: () => <div>Mock file uploader</div>,
}));

vi.mock("./@components/system-metrics/SystemMetrics/SystemMetrics", () => ({
  default: () => <div>Mock metrics</div>,
}));

vi.mock("./@components/settings/Settings/Settings", () => ({
  default: () => <div>Mock settings</div>,
}));

describe("App routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.pushState({}, "", "/");
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ tasks: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("redirects the root route to code architecture", async () => {
    render(<App />);

    expect(screen.getByText("Mock architecture viewer")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    expect(wsServiceMock.connect).toHaveBeenCalledTimes(1);
  });

  it("keeps the upload workspace available on the dedicated route", async () => {
    window.history.pushState({}, "", "/workspace");

    render(<App />);

    expect(
      screen.getByText("Build the Risk Evidence Baseline"),
    ).toBeInTheDocument();
    expect(screen.getByText("Mock file uploader")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    expect(wsServiceMock.connect).toHaveBeenCalledTimes(1);
  });
});
