import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000';

async function pollExtraction(taskId: string, maxRetries = 30): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(`${API_BASE}/api/v1/code/scan/${taskId}`);
    const data = await response.json();
    if (data.status === 'completed') return;
    if (data.status === 'failed') {
      throw new Error(`OmniPay extraction failed: ${JSON.stringify(data)}`);
    }
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error(`OmniPay extraction timed out after ${maxRetries * 2}s`);
}

test.describe('OmniPay Regression Guard', () => {
  test('omnipay-payment-processor extraction produces containers', async ({ request }) => {
    const demoPath = '/app/sources/demo/omnipay-payment-processor';

    const response = await request.post('/api/v1/code/scan', {
      data: {
        repo_path: demoPath,
        use_c4_model: true,
        max_components_per_domain: 10,
      },
    });
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.task_id).toBeDefined();

    await pollExtraction(body.task_id);

    const statusResponse = await fetch(`${API_BASE}/api/v1/code/scan/${body.task_id}`);
    const statusData = await statusResponse.json();
    expect(statusData.status).toBe('completed');

    expect(statusData.containers_count).toBeGreaterThan(0);
  });
});
