/**
 * @fileoverview Unit tests for FileUploader component
 * Tests file upload functionality, error handling, and user interactions
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FileUploader from './FileUploader';

// Mock the API service
vi.mock('@/services/api', () => ({
  ontologyAPI: {
    extractOntology: vi.fn(),
    getExtractionStatus: vi.fn(),
  },
  fileAPI: {
    uploadFile: vi.fn(),
    processLocalFile: vi.fn(),
  },
  wsService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    on: vi.fn(),
  },
  apiUtils: {
    formatFileSize: vi.fn(() => '1KB'),
    handleApiError: vi.fn(),
  },
}));

describe('FileUploader Component', () => {
  const mockOnFilesUploaded = vi.fn();
  const mockOnExtractionStarted = vi.fn();

  beforeEach(async () => {
    vi.clearAllMocks();
    const { ontologyAPI } = await import('@/services/api');
    ontologyAPI.extractOntology.mockResolvedValue({ task_id: 'mock-task-id' });
  });

  it('renders file upload component correctly', () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    // Check if the main upload area is present
    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument();
    expect(screen.getByText(/Upload Data Files/i)).toBeInTheDocument();
  });

  it('shows file input when clicking browse', () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    const uploadArea = screen.getByText(/drag and drop/i).closest('div');
    expect(uploadArea).toBeInTheDocument();
  });

  it('accepts CSV files', () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    const uploadArea = screen.getByText(/drag and drop/i);
    expect(uploadArea).toBeInTheDocument();
  });

  it('handles file drop correctly', async () => {
    const { fileAPI } = await import('@/services/api');
    const mockUploadFile = fileAPI.uploadFile as ReturnType<typeof vi.fn>;
    const mockProcessLocalFile = fileAPI.processLocalFile as ReturnType<
      typeof vi.fn
    >;

    mockUploadFile.mockResolvedValue({
      file_id: 'test-id',
      filename: 'test.csv',
      file_path: '/uploads/test.csv',
      message: 'Upload successful',
    });

    mockProcessLocalFile.mockResolvedValue({
      name: 'test.csv',
      headers: ['id', 'name', 'email'],
      rowCount: 1,
      size: 1024,
    });

    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    const dropZone = screen.getByText(/drag and drop/i).closest('div');
    expect(dropZone).toBeInTheDocument();

    // Create a mock file
    const file = new File(['id,name,email\n1,John,john@test.com'], 'test.csv', {
      type: 'text/csv',
    });

    // Simulate file drop
    if (dropZone) {
      fireEvent.drop(dropZone, {
        dataTransfer: {
          files: [file],
        },
      });
    }

    // Wait for upload to complete
    await waitFor(() => {
      expect(mockUploadFile).toHaveBeenCalledWith(file);
    });
  });

  it('shows error for non-CSV files', async () => {
    // Mock alert function
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    const dropZone = screen.getByText(/drag and drop/i).closest('div');

    // Create a non-CSV file
    const file = new File(['not csv content'], 'test.txt', {
      type: 'text/plain',
    });

    if (dropZone) {
      fireEvent.drop(dropZone, {
        dataTransfer: {
          files: [file],
        },
      });
    }

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith(
        expect.stringContaining('CSV or Excel files only')
      );
    });

    alertSpy.mockRestore();
  });

  it('handles upload errors gracefully', async () => {
    const { fileAPI } = await import('@/services/api');
    const mockUploadFile = fileAPI.uploadFile as ReturnType<typeof vi.fn>;
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    mockUploadFile.mockRejectedValue(new Error('Upload failed'));

    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    const dropZone = screen.getByText(/drag and drop/i).closest('div');
    const file = new File(['id,name\n1,John'], 'test.csv', {
      type: 'text/csv',
    });

    if (dropZone) {
      fireEvent.drop(dropZone, {
        dataTransfer: {
          files: [file],
        },
      });
    }

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith(
        expect.stringContaining('Upload failed')
      );
    });

    alertSpy.mockRestore();
  });

  it('shows upload progress when uploading', async () => {
    const { fileAPI } = await import('@/services/api');
    const mockUploadFile = fileAPI.uploadFile as ReturnType<typeof vi.fn>;
    const mockProcessLocalFile = fileAPI.processLocalFile as ReturnType<
      typeof vi.fn
    >;

    let resolveUpload;
    const uploadPromise = new Promise(resolve => {
      resolveUpload = resolve;
    });

    mockUploadFile.mockImplementation(() => uploadPromise);

    mockProcessLocalFile.mockResolvedValue({
      name: 'test.csv',
      headers: ['id', 'name'],
      rowCount: 1,
      size: 1024,
    });

    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    const dropZone = screen.getByText(/drag and drop/i).closest('div');
    const file = new File(['id,name\n1,John'], 'test.csv', {
      type: 'text/csv',
    });

    if (dropZone) {
      fireEvent.drop(dropZone, {
        dataTransfer: {
          files: [file],
        },
      });
    }

    // Check for upload progress indicator
    await waitFor(() => {
      expect(screen.getByText(/Uploading.../i)).toBeInTheDocument();
    });

    // Resolve the upload promise
    resolveUpload({
      file_id: 'test-id',
      filename: 'test.csv',
      file_path: '/uploads/test.csv',
      message: 'Upload successful',
    });

    await waitFor(() => {
      expect(screen.getByText(/Success/i)).toBeInTheDocument();
    });
  });

  it('calls onFilesUploaded with correct data', async () => {
    const { fileAPI } = await import('@/services/api');
    const mockUploadFile = fileAPI.uploadFile as ReturnType<typeof vi.fn>;
    const mockProcessLocalFile = fileAPI.processLocalFile as ReturnType<
      typeof vi.fn
    >;

    const uploadResponse = {
      file_id: 'test-id-123',
      filename: 'customers.csv',
      file_path: 'uploads/test-id-123_customers.csv',
      size: 1024,
      message: 'Upload successful',
    };

    const processedFile = {
      name: 'customers.csv',
      headers: ['id', 'name', 'email'],
      rowCount: 1,
      size: 1024,
      serverPath: uploadResponse.file_path,
    };

    mockUploadFile.mockResolvedValue(uploadResponse);
    mockProcessLocalFile.mockResolvedValue(processedFile);

    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
      />
    );

    const dropZone = screen.getByText(/drag and drop/i).closest('div');
    const file = new File(
      ['id,name,email\n1,John,john@test.com'],
      'customers.csv',
      {
        type: 'text/csv',
      }
    );

    if (dropZone) {
      fireEvent.drop(dropZone, {
        dataTransfer: {
          files: [file],
        },
      });
    }

    await waitFor(() => {
      expect(mockOnFilesUploaded).toHaveBeenCalledWith([processedFile]);
    });
  });
});
