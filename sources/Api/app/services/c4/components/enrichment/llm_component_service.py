"""LLM-backed service for C4 component classification, grouping, and refinement."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from ..models import (
    ArchitecturalLayer,
    CodeElement,
    ComponentObject,
    ComponentType,
    DependencyEdge,
    ExtractionMethod,
)
from .prompts import (
    COMPONENT_GROUPING_PROMPT,
    COMPONENT_REFINEMENT_PROMPT,
    ELEMENT_CLASSIFICATION_PROMPT,
)

logger = logging.getLogger(__name__)

LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.2
BATCH_SIZE = 50


class LLMComponentService:
    """Uses an LLM to classify code elements and propose/refine component groupings."""

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_elements(self, elements: list[CodeElement]) -> list[CodeElement]:
        """Classify each element's architectural role and layer via LLM.

        Returns a new list of CodeElement copies with `role` and `layer` updated.
        Falls back to returning elements unchanged on any error.
        """
        if not elements:
            return elements

        try:
            if len(elements) > BATCH_SIZE:
                return self._classify_in_batches(elements)
            return self._classify_batch(elements)
        except Exception:
            logger.exception("classify_elements: unexpected error; returning unchanged")
            return list(elements)

    def group_elements(
        self,
        elements: list[CodeElement],
        edges: list[DependencyEdge],
    ) -> list[ComponentObject]:
        """Propose component groupings from classified elements and dependency edges.

        Returns `[]` on any failure (caller should fall back to Louvain).
        """
        if not elements:
            return []

        try:
            elements_json = json.dumps([self._element_to_dict(e) for e in elements])
            edges_json = json.dumps([e.model_dump() for e in edges])

            system_msg, user_template = COMPONENT_GROUPING_PROMPT
            prompt = f"{system_msg}\n\n{user_template.format(elements_json=elements_json, edges_json=edges_json)}"

            raw = self._llm.generate_text(
                prompt,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                use_cache=True,
            )
            groups = self._parse_json_array(raw)
            if groups is None:
                logger.warning("group_elements: could not parse LLM response")
                return []

            element_map = {e.qualified_name: e for e in elements}
            return [self._dict_to_component(g, element_map) for g in groups if isinstance(g, dict)]
        except Exception:
            logger.exception("group_elements: unexpected error; returning []")
            return []

    def refine_grouping(
        self,
        louvain_groups: list[list[CodeElement]],
        elements: list[CodeElement],
        edges: list[DependencyEdge],
    ) -> list[ComponentObject]:
        """Refine Louvain-detected community groupings using domain semantics.

        Falls back to converting Louvain groups directly to ComponentObjects.
        """
        element_map = {e.qualified_name: e for e in elements}

        try:
            proposed = [self._louvain_group_to_dict(i, group) for i, group in enumerate(louvain_groups)]
            proposed_json = json.dumps(proposed)
            elements_json = json.dumps([self._element_to_dict(e) for e in elements])
            edges_json = json.dumps([e.model_dump() for e in edges])

            system_msg, user_template = COMPONENT_REFINEMENT_PROMPT
            prompt = f"{system_msg}\n\n{user_template.format(proposed_groups_json=proposed_json, elements_json=elements_json, edges_json=edges_json)}"

            raw = self._llm.generate_text(
                prompt,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                use_cache=True,
            )
            groups = self._parse_json_array(raw)
            if groups is None:
                logger.warning("refine_grouping: could not parse LLM response; using Louvain fallback")
                return self._louvain_fallback(louvain_groups)

            return [self._dict_to_component(g, element_map) for g in groups if isinstance(g, dict)]
        except Exception:
            logger.exception("refine_grouping: unexpected error; using Louvain fallback")
            return self._louvain_fallback(louvain_groups)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_in_batches(self, elements: list[CodeElement]) -> list[CodeElement]:
        result: list[CodeElement] = []
        for i in range(0, len(elements), BATCH_SIZE):
            batch = elements[i: i + BATCH_SIZE]
            result.extend(self._classify_batch(batch))
        return result

    def _classify_batch(self, elements: list[CodeElement]) -> list[CodeElement]:
        dicts = [self._element_to_dict(e) for e in elements]
        system_msg, user_template = ELEMENT_CLASSIFICATION_PROMPT
        prompt = f"{system_msg}\n\n{user_template.format(elements_json=json.dumps(dicts))}"

        try:
            raw = self._llm.generate_text(
                prompt,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                use_cache=True,
            )
        except Exception:
            logger.exception("_classify_batch: LLM call failed; returning batch unchanged")
            return list(elements)

        classifications = self._parse_json_array(raw)
        if classifications is None:
            logger.warning("_classify_batch: invalid JSON response; returning batch unchanged")
            return list(elements)

        # Build name → classification map
        class_map: dict[str, dict] = {}
        for item in classifications:
            if isinstance(item, dict) and item.get("element_name"):
                class_map[item["element_name"]] = item

        updated: list[CodeElement] = []
        for elem in elements:
            classification = class_map.get(elem.qualified_name)
            if classification:
                new_elem = elem.model_copy()
                if classification.get("role"):
                    new_elem.role = classification["role"]
                raw_layer = classification.get("layer", "")
                try:
                    new_elem.layer = ArchitecturalLayer(raw_layer)
                except ValueError:
                    pass
                updated.append(new_elem)
            else:
                updated.append(elem)

        return updated

    def _parse_json_array(self, raw: Optional[str]) -> Optional[list[dict]]:
        """Strip markdown fences, extract JSON array, parse."""
        if not raw:
            return None

        # Strip ```json ... ``` fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()

        # Try direct parse
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        # Fallback: regex extract first [...]
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        logger.debug("_parse_json_array: could not extract JSON array from response")
        return None

    @staticmethod
    def _element_to_dict(element: CodeElement) -> dict:
        return {
            "qualified_name": element.qualified_name,
            "kind": element.kind.value,
            "file_path": element.file_path,
            "language": element.language,
            "annotations": element.annotations,
            "imports": element.imports,
            "base_classes": element.base_classes,
            "method_calls": element.method_calls,
        }

    @staticmethod
    def _dict_to_component(data: dict, element_map: dict[str, CodeElement]) -> ComponentObject:
        name = data.get("name", "UnknownComponent")
        component_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        element_names: list[str] = data.get("element_names") or []
        code_elements = [element_map[n] for n in element_names if n in element_map]

        raw_type = data.get("component_type", "")
        try:
            component_type = ComponentType(raw_type)
        except ValueError:
            component_type = ComponentType.COMPONENT

        return ComponentObject(
            component_id=component_id,
            name=name,
            description=data.get("description", ""),
            component_type=component_type,
            confidence=0.8,
            extraction_method=ExtractionMethod.HYBRID,
            code_elements=code_elements,
        )

    @staticmethod
    def _louvain_group_to_dict(index: int, group: list[CodeElement]) -> dict:
        names = [e.qualified_name for e in group]
        # Auto-generate name from common prefix or first element
        if names:
            parts = names[0].split(".")
            name = parts[-2] if len(parts) >= 2 else parts[0]
        else:
            name = f"Group{index}"
        return {
            "name": name,
            "description": "",
            "role": "other",
            "layer": "unknown",
            "element_names": names,
            "provided_interfaces": [],
            "required_interfaces": [],
        }

    @staticmethod
    def _louvain_fallback(louvain_groups: list[list[CodeElement]]) -> list[ComponentObject]:
        components: list[ComponentObject] = []
        for i, group in enumerate(louvain_groups):
            names = [e.qualified_name for e in group]
            if names:
                parts = names[0].split(".")
                name = parts[-2] if len(parts) >= 2 else parts[0]
            else:
                name = f"Group{i}"
            component_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"group-{i}"
            components.append(ComponentObject(
                component_id=component_id,
                name=name,
                confidence=0.5,
                extraction_method=ExtractionMethod.COMMUNITY_DETECTION,
                code_elements=list(group),
            ))
        return components
