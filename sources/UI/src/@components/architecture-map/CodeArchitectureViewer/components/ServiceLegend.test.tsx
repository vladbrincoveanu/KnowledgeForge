import React from 'react';
import { render, screen } from '@testing-library/react';
import ServiceLegend from './ServiceLegend';

test('renders service legend', () => {
  render(<ServiceLegend />);
  expect(screen.getByTestId('service-legend')).toHaveTextContent('Service Legend');
});
