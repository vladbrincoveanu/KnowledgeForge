import React from 'react';
import { render, screen } from '@testing-library/react';
import NodeDetails from './NodeDetails';

test('renders node details with id', () => {
  render(<NodeDetails node={{ id: 'node-1' }} />);
  expect(screen.getByTestId('node-details')).toHaveTextContent('node-1');
});
