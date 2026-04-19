import { describe, expect, test } from "vitest";

import { buildRenderedEdges } from "./edgeRendering";

describe("buildRenderedEdges", () => {
  test("uses a compact graph label while preserving the full description", () => {
    const edges = buildRenderedEdges(
      [
        {
          source_entity_id: "user",
          target_entity_id: "system",
          relationship_type: "uses",
          attributes: {
            description: "Manages content via the CMS UI",
            protocol: "HTTPS",
          },
        },
      ],
      true,
      [
        { id: "user", name: "Customer", entity_type: "person" },
        { id: "system", name: "CMS Platform", entity_type: "system" },
      ],
    );

    expect(edges).toHaveLength(1);
    expect(edges[0].label).toBe("Manages content via the CMS UI");
    expect(edges[0].data).toMatchObject({
      description: "Manages content via the CMS UI",
      graph_label: "Manages content",
      protocol: undefined,
      relationship_type: "uses",
      context_role: "actor",
      label_placement: "source",
      label_title: "Customer",
    });
  });

  test("preserves protocol metadata outside the context level", () => {
    const edges = buildRenderedEdges(
      [
        {
          source_entity_id: "api",
          target_entity_id: "payments",
          relationship_type: "calls",
          attributes: {
            description: "Creates payment intents",
            protocol: "HTTPS",
          },
        },
      ],
      false,
    );

    expect(edges).toHaveLength(1);
    expect(edges[0].label).toBeUndefined();
    expect(edges[0].data).toMatchObject({
      description: "Creates payment intents",
      protocol: "HTTPS",
      relationship_type: "calls",
    });
  });

  test("uses the external dependency name as the context title chip", () => {
    const edges = buildRenderedEdges(
      [
        {
          source_entity_id: "system",
          target_entity_id: "bank",
          relationship_type: "uses",
          attributes: {
            description: "Submits settlement files to the banking partner",
          },
        },
      ],
      true,
      [
        { id: "system", name: "OmniPay Platform", entity_type: "system" },
        { id: "bank", name: "GlobalBank", entity_type: "external_service" },
      ],
    );

    expect(edges[0].data).toMatchObject({
      context_role: "external",
      label_placement: "target",
      label_title: "GlobalBank",
    });
  });

  test("truncates very long context descriptions into a short canvas label", () => {
    const edges = buildRenderedEdges(
      [
        {
          source_entity_id: "actor",
          target_entity_id: "system",
          relationship_type: "uses",
          attributes: {
            description:
              "Reviews provider onboarding decisions and resolves ambiguous external dependency reviews.",
          },
        },
      ],
      true,
      [
        { id: "actor", name: "Risk Operations Manager", entity_type: "person" },
        { id: "system", name: "OmniPay Platform", entity_type: "system" },
      ],
    );

    expect(edges[0].label).toBe(
      "Reviews provider onboarding decisions and resolves ambiguous external dependency reviews.",
    );
    expect(edges[0].data).toMatchObject({
      description:
        "Reviews provider onboarding decisions and resolves ambiguous external dependency reviews.",
      graph_label: "Reviews provider onboarding decisions",
    });
  });
});
