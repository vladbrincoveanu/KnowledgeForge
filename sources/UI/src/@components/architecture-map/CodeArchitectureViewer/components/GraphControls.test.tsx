import React from 'react';
import { render, screen } from '@testing-library/react';
import GraphControls from './GraphControls';

test('renders graph controls', () => {
  render(<GraphControls />);
  expect(screen.getByTestId('graph-controls')).toHaveTextContent('Graph Controls');
});
