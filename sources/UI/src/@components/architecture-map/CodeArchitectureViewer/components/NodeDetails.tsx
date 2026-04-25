import React from "react";

type Props = { node?: { id?: string } };

export default function NodeDetails({ node }: Props) {
  return <div data-testid="node-details">{node?.id ?? "No node selected"}</div>;
}
