/* @vitest-environment jsdom */

import React from "react";
import { test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen } from "@testing-library/react";
import ServiceLegend from "./ServiceLegend";

expect.extend(matchers);

test("renders service legend", () => {
  render(<ServiceLegend />);
  expect(screen.getByTestId("service-legend")).toHaveTextContent(
    "Service Legend",
  );
});
