import { describe, expect, test } from 'vitest';

import {
  getC4EdgeGeometry,
  getEdgeLaneOffset,
} from './c4EdgeGeometry';

describe('c4EdgeGeometry', () => {
  test('biases labels toward the target side of left-to-right edges', () => {
    const geometry = getC4EdgeGeometry({
      id: 'edge-globalbank',
      sourceX: 100,
      sourceY: 120,
      targetX: 500,
      targetY: 160,
    });

    expect(geometry.labelX).toBeGreaterThan(300);
  });

  test('fans upward edges out of the node center', () => {
    const geometry = getC4EdgeGeometry({
      id: 'edge-auth0',
      sourceX: 400,
      sourceY: 320,
      targetX: 760,
      targetY: 120,
    });

    expect(geometry.sourceYOffset).toBeLessThan(0);
    expect(geometry.targetYOffset).toBeGreaterThan(0);
  });

  test('keeps lane offsets within a bounded visual range', () => {
    const offset = getEdgeLaneOffset('edge-sendgrid', 220, 520);

    expect(offset).toBeGreaterThanOrEqual(-42);
    expect(offset).toBeLessThanOrEqual(42);
  });

  test('can bias actor labels toward the source side of the edge', () => {
    const geometry = getC4EdgeGeometry({
      id: 'edge-customer-omnipay',
      sourceX: 100,
      sourceY: 180,
      targetX: 520,
      targetY: 260,
      labelPlacement: 'source',
    });

    expect(geometry.labelX).toBeLessThan(320);
  });
});
