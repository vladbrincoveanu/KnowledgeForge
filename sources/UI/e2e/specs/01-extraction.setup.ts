import { test as setup, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const STATE_FILE = path.join(__dirname, '..', '.extraction-state.json');

async function pollExtraction(baseURL: string, taskId: string, maxRetries = 30): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(`${baseURL}/api/v1/code/scan/${taskId}`);
    const data = await response.json();
    if (data.status === 'completed') return;
    if (data.status === 'failed') {
      throw new Error(`Extraction failed: ${JSON.stringify(data)}`);
    }
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error(`Extraction timed out after ${maxRetries * 2}s`);
}

setup('extract OmniPay demo fixture', async ({ request }) => {
  if (fs.existsSync(STATE_FILE)) {
    const existing = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    if (existing.status === 'completed') return;
  }

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

  const apiBase = 'http://localhost:8000';
  await pollExtraction(apiBase, body.task_id);

  fs.writeFileSync(STATE_FILE, JSON.stringify({
    task_id: body.task_id,
    status: 'completed',
    fixture: 'omnipay-payment-processor',
    timestamp: Date.now(),
  }));
});
