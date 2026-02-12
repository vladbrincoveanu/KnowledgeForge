"""Service enhancement methods that enrich extracted services with additional data."""

import logging
import threading
from pathlib import Path
from typing import Any, Optional

from app.domain.models.services import Service, ServiceStatus, ServiceTier
from app.services.service_extraction.extraction_helpers import (
    resolve_service_path,
    is_missing_label,
    normalize_status_label,
    normalize_tier_label,
)
from app.services.service_extraction.owner_detector import OwnerDetector
from app.services.service_extraction.api_surface_detector import detect_api_surface_types
from app.services.service_extraction.inter_service_comm_detector import detect_inter_service_comms
from app.services.service_extraction.business_domain_classifier import classify_business_domain
from app.services.service_extraction.documentation_quality_scorer import DocumentationQualityScorer
from app.services.service_extraction.deployment_target_detector import detect_deployment_targets
from app.services.service_extraction.bus_factor_calculator import calculate_bus_factor
from app.services.service_extraction.auth_scanner import scan_auth

logger = logging.getLogger(__name__)


def enhance_with_git_status(
    services: list[Service],
    repo_root: Path,
    git_analyzer: Any,
    contributor_analyzer: Any,
    contributor_limit: int = 3,
) -> None:
    """
    Enhance services with git history analysis:
    - Owner (from top contributors)
    - Status (from commit patterns)
    - Commit statistics (counts, dates)
    - Status evidence (for debugging)
    """
    if not git_analyzer.is_git_repo:
        logger.info("Not a git repository, skipping git analysis")
        return

    logger.info("Enhancing services with git history analysis (owner, status, stats)")
    max_contributors = max(1, contributor_limit)
    owner_detector = OwnerDetector(repo_root)

    for service in services:
        service_path = resolve_service_path(repo_root, service)

        # 1. OWNER DETECTION – 4-step fallback chain
        if not service.owner:
            detected_owner, detection_source = owner_detector.detect(
                service_path=service_path,
                service_name=service.name,
            )
            if detected_owner and detected_owner != "UNKNOWN":
                service.owner = detected_owner
                service.owner_detection_source = detection_source
            else:
                service.owner_detection_source = detection_source  # "UNKNOWN"

        # 2. GET CONTRIBUTOR STATS
        contributor_stats = contributor_analyzer.analyze_service_contributors(
            service_path=service_path,
            service_name=service.name,
            max_contributors=max_contributors,
        )

        if contributor_stats:
            top_contributors = contributor_stats.top_contributors
            if top_contributors:
                service.owner_contributors = [c.email for c in top_contributors]
                service.owner_contributor_stats = [
                    {"email": c.email, "name": c.name, "commit_count": c.commit_count}
                    for c in top_contributors
                ]
            service.contributor_count = contributor_stats.unique_contributors

            service.last_commit_date = contributor_stats.last_commit_date
            service.commit_count_30d = contributor_stats.commits_30d
            service.commit_count_90d = contributor_stats.commits_90d
            service.commit_count_180d = contributor_stats.commits_180d

            service.status_evidence = {
                'total_commits': contributor_stats.total_commits,
                'commits_30d': contributor_stats.commits_30d,
                'commits_90d': contributor_stats.commits_90d,
                'commits_180d': contributor_stats.commits_180d,
                'feature_commits': contributor_stats.feature_commits,
                'bugfix_commits': contributor_stats.bugfix_commits,
                'chore_commits': contributor_stats.chore_commits,
                'last_commit_date': contributor_stats.last_commit_date.isoformat() if contributor_stats.last_commit_date else None,
                'first_commit_date': contributor_stats.first_commit_date.isoformat() if contributor_stats.first_commit_date else None,
                'unique_contributors': contributor_stats.unique_contributors,
                'top_contributors': [c.email for c in top_contributors] if top_contributors else [],
                'top_contributor_stats': [
                    {"email": c.email, "name": c.name, "commit_count": c.commit_count}
                    for c in top_contributors
                ] if top_contributors else [],
                'recent_commit_messages': contributor_stats.recent_commit_messages[:10],
            }

        # 2. ANALYZE STATUS FROM GIT HISTORY
        git_status = git_analyzer.analyze_service_status(
            service_path=service_path,
            service_name=service.name
        )

        activity_summary = git_analyzer.get_service_activity_summary(
            service_path=service_path,
            service_name=service.name
        )

        if git_status != ServiceStatus.UNKNOWN:
            old_status = service.status
            service.status = git_status

            if activity_summary:
                logger.info(
                    f"Service '{service.name}': git analysis -> {git_status.value} "
                    f"(was: {old_status.value}, commits: {activity_summary['total_commits']}, "
                    f"last: {activity_summary['days_since_last']}d ago, "
                    f"recent: {activity_summary['recent_commits_30d']} in 30d)"
                )

            # Override if git suggests deprecated (more reliable)
            if git_status == ServiceStatus.DEPRECATED:
                service.status = ServiceStatus.DEPRECATED
            elif (service.status == ServiceStatus.ACTIVE and
                  git_status == ServiceStatus.MAINTENANCE):
                activity = git_analyzer.get_service_activity_summary(
                    service_path=service_path,
                    service_name=service.name
                )
                if activity and activity.get('total_commits', 0) > 5:
                    service.status = ServiceStatus.MAINTENANCE


def enhance_with_domain_detection(
    services: list[Service],
    repo_root: Path,
    domain_extractor: Any,
) -> None:
    """Infer domain from imports and namespaces when missing."""
    if not services:
        return

    logger.info("Enhancing services with domain detection")

    for service in services:
        if service.domain:
            continue

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            continue

        scan_path = service_path if service_path.is_dir() else service_path.parent
        domain = domain_extractor.extract_domain(scan_path, service.name)
        if domain:
            service.domain = domain
            logger.info(f"Service '{service.name}': inferred domain '{domain}' from imports")


def enhance_with_dependencies(
    services: list[Service],
    repo_root: Path,
    dependency_extractor_cls: type,
) -> None:
    """Populate direct_depends by scanning imports for cross-service references."""
    if not services:
        return

    logger.info("Scanning for direct service dependencies from imports")
    dep_extractor = dependency_extractor_cls(repo_root, services)

    for service in services:
        deps = dep_extractor.extract_dependencies(service)
        if not deps:
            continue

        merged = sorted(set(service.direct_depends or []) | set(deps))
        service.direct_depends = merged

        for dep_id in deps:
            if dep_id not in service.dependencies:
                service.dependencies.append(dep_id)
            target_service = dep_extractor.service_map.get(dep_id)
            if target_service and service.id not in target_service.dependents:
                target_service.dependents.append(service.id)

        logger.debug(f"Service '{service.name}': detected direct dependencies {merged}")


def enhance_with_descriptions(
    services: list[Service],
    repo_root: Path,
    description_generator: Any,
) -> None:
    """Generate short descriptions for services."""
    if not services or not description_generator:
        return

    logger.info("Generating service descriptions (LLM flag enabled)")

    for service in services:
        if service.description:
            continue

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            continue

        scan_path = service_path if service_path.is_dir() else service_path.parent
        description = description_generator.generate_description(
            service_name=service.name,
            service_path=scan_path,
            language=service.language,
            repo_root=repo_root,
        )

        if description:
            service.description = description
            logger.info(f"Service '{service.name}': generated description")


def enhance_with_llm_enrichment(
    services: list[Service],
    repo_root: Path,
    llm_enricher: Any,
) -> None:
    """Use LLM to fill missing labels and notes."""
    if not services or not llm_enricher:
        return

    logger.info("Enhancing services with LLM labels and notes")
    llm_working = True

    for service in services:
        if not llm_working:
            break

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            service_path = repo_root

        scan_path = service_path if service_path.is_dir() else service_path.parent
        enrichment = {}
        try:
            result_container = {'enrichment': None, 'error': None, 'completed': False}

            def enrich_with_timeout():
                try:
                    result_container['enrichment'] = llm_enricher.enrich_service(
                        service, scan_path, repo_root=repo_root,
                    )
                    result_container['completed'] = True
                except Exception as e:
                    result_container['error'] = e
                    result_container['completed'] = True

            thread = threading.Thread(target=enrich_with_timeout)
            thread.daemon = True
            thread.start()
            thread.join(timeout=5)

            if thread.is_alive():
                logger.warning(
                    f"LLM enrichment timed out for service '{service.name}' after 5 seconds "
                    f"- LLM appears unavailable, skipping remaining services"
                )
                llm_working = False
                enrichment = {}
            elif result_container['error']:
                logger.warning(f"LLM enrichment failed for service '{service.name}': {result_container['error']}")
                if 'connection' in str(result_container['error']).lower() or 'refused' in str(result_container['error']).lower():
                    llm_working = False
                enrichment = {}
            else:
                enrichment = result_container['enrichment'] or {}
        except Exception as e:
            logger.warning(f"LLM enrichment error for service '{service.name}': {e}")
            llm_working = False
            enrichment = {}

        if not enrichment:
            continue

        inferred = service.attributes.setdefault("inferred_fields", {})

        domain = enrichment.get("domain")
        if domain:
            service.domain = domain
            inferred["domain"] = {"confidence": "low", "source": "llm"}

        owner = enrichment.get("owner")
        if is_missing_label(service.owner) and owner:
            service.owner = owner
            inferred["owner"] = {"confidence": "low", "source": "llm"}

        data_class = enrichment.get("data_class")
        if is_missing_label(service.data_class) and data_class:
            service.data_class = data_class
            inferred["data_class"] = {"confidence": "low", "source": "llm"}

        status = normalize_status_label(enrichment.get("status"))
        if service.status == ServiceStatus.UNKNOWN and status:
            service.status = status
            inferred["status"] = {"confidence": "low", "source": "llm"}

        tier = normalize_tier_label(enrichment.get("tier"))
        if service.tier == ServiceTier.UNKNOWN and tier:
            service.tier = tier
            inferred["tier"] = {"confidence": "low", "source": "llm"}

        notes = enrichment.get("notes")
        if notes:
            service.notes = notes
            service.description = notes
            inferred["notes"] = {"confidence": "low", "source": "llm"}


def enhance_with_api_surface_types(
    services: list[Service],
    repo_root: Path,
) -> None:
    """Detect API surface types (REST/GraphQL/gRPC/CLI/WebSocket/Event-Driven) for each service."""
    if not services:
        return

    logger.info("Detecting API surface types for services")

    for service in services:
        if service.api_surface_types:
            continue  # already populated

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            continue

        scan_path = service_path if service_path.is_dir() else service_path.parent
        surface_types = detect_api_surface_types(scan_path)

        if surface_types:
            service.api_surface_types = surface_types
            logger.info(f"Service '{service.name}': API surfaces = {surface_types}")


def enhance_with_inter_service_comms(
    services: list[Service],
    repo_root: Path,
) -> None:
    """Scan source code for HTTP/gRPC/queue calls to other services."""
    if not services:
        return

    logger.info("Detecting inter-service communications")

    for service in services:
        if service.inter_service_comms:
            continue  # already populated

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            continue

        scan_path = service_path if service_path.is_dir() else service_path.parent
        comms = detect_inter_service_comms(scan_path)

        if comms:
            service.inter_service_comms = comms
            logger.info(f"Service '{service.name}': {len(comms)} inter-service comm(s) detected")


def enhance_with_business_domain(
    services: list[Service],
    repo_root: Path,
    llm_manager=None,
) -> None:
    """Classify service business domain into fixed taxonomy using keywords + optional LLM."""
    if not services:
        return

    logger.info("Classifying business domains")

    for service in services:
        # Read README for context
        readme_text = ""
        service_path = resolve_service_path(repo_root, service)
        if service_path:
            scan_path = service_path if service_path.is_dir() else service_path.parent
            for readme_name in ("README.md", "README.rst", "README.txt"):
                readme_file = scan_path / readme_name
                if readme_file.exists():
                    try:
                        readme_text = readme_file.read_text(encoding="utf-8", errors="ignore")[:2000]
                    except OSError:
                        pass
                    break

        domain = classify_business_domain(
            service_name=service.name,
            readme_text=readme_text,
            existing_domain=service.domain,
            llm_manager=llm_manager,
        )

        if domain:
            service.business_domain = domain
            logger.info(f"Service '{service.name}': business domain = {domain}")


def enhance_with_documentation_quality(
    services: list[Service],
    repo_root: Path,
) -> None:
    """Score documentation quality for each service (0-100)."""
    if not services:
        return

    logger.info("Scoring documentation quality")
    scorer = DocumentationQualityScorer()

    for service in services:
        if service.documentation_quality is not None:
            continue  # already populated

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            continue

        scan_path = service_path if service_path.is_dir() else service_path.parent
        result = scorer.score(scan_path)
        service.documentation_quality = result.score
        logger.info(
            f"Service '{service.name}': documentation quality = {result.score}/100 ({result.tier})"
        )


def enhance_with_deployment_targets(
    services: list[Service],
    repo_root: Path,
) -> None:
    """Detect deployment targets (Container/Kubernetes/Serverless/VM/Bare-Metal/PaaS) for each service."""
    if not services:
        return

    logger.info("Detecting deployment targets")

    for service in services:
        if service.deployment_targets:
            continue  # already populated

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            continue

        scan_path = service_path if service_path.is_dir() else service_path.parent
        targets = detect_deployment_targets(scan_path)

        if targets:
            service.deployment_targets = targets
            logger.info(f"Service '{service.name}': deployment targets = {targets}")


def enhance_with_bus_factor(
    services: list[Service],
    repo_root: Path,
) -> None:
    """Compute composite Bus Factor score (1-10) and update active_experts for each service.

    Replaces the raw active_experts count with a Gini-weighted composite that reflects
    both how many active experts exist and how evenly distributed commits are.
    bus_factor_score (1-10) is written to service.bus_factor.
    The raw expert count is written to service.active_experts.
    """
    if not services:
        return

    logger.info("Computing bus factor scores")

    for service in services:
        if service.bus_factor is not None:
            continue  # already populated

        service_path = resolve_service_path(repo_root, service)
        scan_path = (service_path if service_path and service_path.is_dir() else
                     service_path.parent if service_path else None)

        result = calculate_bus_factor(
            repo_root=repo_root,
            service_path=scan_path,
        )

        service.bus_factor = result.bus_factor_score
        service.active_experts = result.active_experts


def enhance_with_auth_scanning(
    services: list[Service],
    repo_root: Path,
) -> None:
    """Scan auth configs and update service attributes with auth_types and actors.

    Checks OpenAPI securitySchemes, OAuth/JWT/APIKey code patterns, and env-var
    hints. Results stored in service.attributes['auth_types'] and
    service.attributes['actors'] (does not override if already populated).
    """
    if not services:
        return

    logger.info("Scanning auth configurations")

    for service in services:
        # Skip if already populated
        if service.attributes.get("auth_types") and service.attributes.get("actors"):
            continue

        service_path = resolve_service_path(repo_root, service)
        if not service_path:
            continue

        scan_path = service_path if service_path.is_dir() else service_path.parent
        result = scan_auth(scan_path)

        service.attributes["auth_types"] = result.auth_types
        service.attributes["actors"] = result.actors

        logger.info(
            "Service '%s': auth_types=%s, actors=%s",
            service.name,
            result.auth_types,
            result.actors,
        )

        logger.debug(
            "Service '%s': evidence=%s",
            service.name,
            result.evidence[:3] if result.evidence else [],
        )
