/* @vitest-environment jsdom */

import React from 'react';
import { test, expect } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { render, screen } from '@testing-library/react';
import GraphControls from './GraphControls';

expect.extend(matchers);

test('renders graph controls', () => {
  render(<GraphControls />);
  expect(screen.getByTestId('graph-controls')).toHaveTextContent('Graph Controls');
});
