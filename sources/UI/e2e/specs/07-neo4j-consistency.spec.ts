import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000';

async function pollExtraction(taskId: string, maxRetries = 30): Promise<void> {
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

async function queryNeo4j(cypher: string, params: object = {}): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/v1/debug/neo4j/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cypher, params }),
  });
  if (!response.ok()) throw new Error(`Neo4j query failed: ${response.statusText}`);
  return response.json();
}

test.describe('Neo4j Consistency', () => {
  test('extraction results match Neo4j storage', async ({ request }) => {
    // 1. Trigger fresh extraction of Airbyte demo
    const response = await request.post(`${API_BASE}/api/v1/code/scan`, {
      data: {
        repo_path: '/app/sources/demo/airbyte',
        use_c4_model: true,
        max_components_per_domain: 10,
      },
    });
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.task_id).toBeDefined();

    // 2. Wait for completion
    await pollExtraction(body.task_id);

    // 3. Load JSON result
    const jsonResponse = await fetch(`${API_BASE}/api/v1/code/scan/${body.task_id}/results`);
    const jsonData = await jsonResponse.json();

    const containers = (jsonData.containers || []).filter((c: any) => !c.is_infrastructure_only);
    const extDeps = (jsonData.system_context || {}).external_dependencies || [];
    const containerRels = (jsonData.relationships || {}).containers || [];

    // 4. Query Neo4j for counts
    const containerCount = await queryNeo4j('MATCH (n:Container) RETURN count(n) as c');
    const extSystemCount = await queryNeo4j('MATCH (n:ExternalSystem) RETURN count(n) as c');
    const evidenceCount = await queryNeo4j('MATCH (n:Evidence) RETURN count(n) as c');
    const usesRelCount = await queryNeo4j('MATCH ()-[r:USES]->() RETURN count(r) as c');

    // 5. Assert counts match
    expect(containerCount[0].c).toBe(containers.length);
    expect(extSystemCount[0].c).toBe(extDeps.length);
    expect(usesRelCount[0].c).toBe(containerRels.length);

    // 6. Verify evidence count
    const totalEvidence = extDeps.reduce((sum: number, dep: any) => sum + (dep.evidence?.length || 0), 0);
    expect(evidenceCount[0].c).toBe(totalEvidence);
  });
});
