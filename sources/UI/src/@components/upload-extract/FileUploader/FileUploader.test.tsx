/* @vitest-environment jsdom */

/**
 * @fileoverview Unit tests for FileUploader component (GitHub repo extraction)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import FileUploader from "./FileUploader";
import { codeArchitectureAPI } from "@/services/api";

expect.extend(matchers);

// Test URLs
const REPO_FACEBOOK = "https://github.com/facebook/react";
const REPO_MICROSOFT = "https://github.com/microsoft/typescript";
const REPO_GITLAB = "https://gitlab.tuwien.ac.at/ai-factory/monorepo";
const INPUT_PLACEHOLDER = /github\.com\/owner\/repo/i;

// Mock the API service
vi.mock("@/services/api", () => ({
  codeArchitectureAPI: {
    extractFromGitHub: vi.fn(),
    getExtractionStatus: vi.fn(),
  },
  wsService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  },
}));

describe("FileUploader Component", () => {
  const mockOnFilesUploaded = vi.fn();
  const mockOnExtractionStarted = vi.fn();
  const mockShowNotification = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    codeArchitectureAPI.extractFromGitHub.mockResolvedValue({
      task_id: "mock-task-id",
    });
    codeArchitectureAPI.getExtractionStatus.mockResolvedValue({
      status: "pending",
      message: "Queued",
      progress: 0,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders empty state with GitHub URL input", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    expect(screen.getByPlaceholderText(INPUT_PLACEHOLDER)).toBeInTheDocument();
    expect(
      screen.getByText(/Add one or more repository URLs above/i),
    ).toBeInTheDocument();
  });

  it("shows error for empty URL submission", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(
      screen.getByText(/please enter a repository url/i),
    ).toBeInTheDocument();
  });

  it("shows error for invalid GitHub URL", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: "not-a-valid-url" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(
      screen.getByText(/enter a valid repository url/i),
    ).toBeInTheDocument();
  });

  it("adds a valid GitLab URL to the repo list", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_GITLAB },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(screen.getByText(/ai-factory\/monorepo/i)).toBeInTheDocument();
    expect(screen.getByText(/ready to extract/i)).toBeInTheDocument();
  });

  it("adds a valid GitHub URL to the repo list", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(screen.getByText(/facebook\/react/i)).toBeInTheDocument();
    expect(screen.getByText(/ready to extract/i)).toBeInTheDocument();
  });

  it("strips .git suffix from GitHub URL", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: "https://github.com/facebook/react.git" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(screen.getByText(/facebook\/react/i)).toBeInTheDocument();
    expect(screen.queryByText(/\.git/i)).not.toBeInTheDocument();
  });

  it("shows error for duplicate GitHub URL", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(
      screen.getByText(/this repository has already been added/i),
    ).toBeInTheDocument();
  });

  it("removes a repo from the list", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(screen.getByText(/facebook\/react/i)).toBeInTheDocument();

    const removeButtons = screen.getAllByTitle(/remove/i);
    fireEvent.click(removeButtons[0]);

    expect(screen.queryByText(/facebook\/react/i)).not.toBeInTheDocument();
  });

  it("clears all repos", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_MICROSOFT },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(screen.getByText(/facebook\/react/i)).toBeInTheDocument();
    expect(screen.getByText(/microsoft\/typescript/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /clear all/i }));

    expect(screen.queryByText(/facebook\/react/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/microsoft\/typescript/i),
    ).not.toBeInTheDocument();
  });

  it("starts extraction when Extract button is clicked", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    fireEvent.click(screen.getByRole("button", { name: /extract/i }));

    expect(codeArchitectureAPI.extractFromGitHub).toHaveBeenCalledWith(
      REPO_FACEBOOK,
      true,
      false, // appendMode defaults to false (replace)
      undefined,
    );
  });

  it("shows extract button enabled when repo is added", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(screen.getByRole("button", { name: /extract/i })).not.toBeDisabled();
  });

  it("adds repo via Enter key", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      key: "Enter",
    });

    expect(screen.getByText(/facebook\/react/i)).toBeInTheDocument();
  });

  it("shows ready to extract message after adding repo", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(screen.getByText(/ready to extract/i)).toBeInTheDocument();
  });

  it("shows multiple repos with correct status labels", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    fireEvent.change(screen.getByPlaceholderText(INPUT_PLACEHOLDER), {
      target: { value: REPO_MICROSOFT },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    // Each repo has "Ready to extract" message and "Ready" status label
    const readyLabels = screen.getAllByText(/ready/i);
    expect(readyLabels).toHaveLength(4);
  });

  it("clears input after adding repo", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );

    const input = screen.getByPlaceholderText(INPUT_PLACEHOLDER);
    fireEvent.change(input, {
      target: { value: REPO_FACEBOOK },
    });
    fireEvent.click(screen.getByRole("button", { name: /add/i }));

    expect(input).toHaveValue("");
  });

  it("renders GitHub URL tab and Local Folder tab by default", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );
    expect(screen.getByRole("tab", { name: /github url/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /local folder/i })).toBeInTheDocument();
  });

  it("switches to Local Folder tab on click", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: /local folder/i }));
    expect(screen.getByRole("region", { name: /drop project folder/i })).toBeInTheDocument();
  });

  it("GitHub tab still shows URL input after tab switch and back", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );
    // Switch to local
    fireEvent.click(screen.getByRole("tab", { name: /local folder/i }));
    // Switch back to github
    fireEvent.click(screen.getByRole("tab", { name: /github url/i }));
    // GitHub URL input should be visible again
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});
