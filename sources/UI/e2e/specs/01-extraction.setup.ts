import { test as setup, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const STATE_FILE = path.join(__dirname, '..', '.extraction-state.json');
const RESULT_FILE = path.join(__dirname, '..', '.extraction-result.json');

const API_BASE = 'http://localhost:8000';

async function pollExtraction(taskId: string, maxRetries = 55): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(`${API_BASE}/api/v1/code/scan/${taskId}`);
    const data = await response.json();
    if (data.status === 'completed') return;
    if (data.status === 'failed') {
      throw new Error(`Extraction failed: ${JSON.stringify(data)}`);
    }
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error(`Extraction timed out after ${maxRetries * 2}s`);
}

setup('extract Airbyte demo fixture', async ({ request }) => {
  if (fs.existsSync(STATE_FILE) && fs.existsSync(RESULT_FILE)) {
    const existing = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    if (existing.status === 'completed') return;
  }

  const demoPath = '/app/sources/demo/airbyte';

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

  fs.writeFileSync(STATE_FILE, JSON.stringify({
    task_id: body.task_id,
    status: 'completed',
    fixture: 'airbyte',
    timestamp: Date.now(),
  }));

  const resultResponse = await fetch(`${API_BASE}/api/v1/code/scan/${body.task_id}/results`);
  expect(resultResponse.ok()).toBeTruthy();
  const resultData = await resultResponse.json();
  fs.writeFileSync(RESULT_FILE, JSON.stringify(resultData, null, 2));
  console.log(`Saved extraction result: ${resultData.statistics?.total_containers || 0} containers, ${resultData.statistics?.total_components || 0} components`);
});
