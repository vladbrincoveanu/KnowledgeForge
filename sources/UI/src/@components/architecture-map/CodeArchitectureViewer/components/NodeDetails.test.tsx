/* @vitest-environment jsdom */

import React from "react";
import { test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen } from "@testing-library/react";
import NodeDetails from "./NodeDetails";

expect.extend(matchers);

test("renders node details with id", () => {
  render(<NodeDetails node={{ id: "node-1" }} />);
  expect(screen.getByTestId("node-details")).toHaveTextContent("node-1");
});
