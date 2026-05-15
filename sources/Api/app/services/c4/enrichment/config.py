import os


def ENRICHMENT_ENABLED() -> bool:
    return os.getenv("ENRICHMENT_ENABLED", "true").lower() == "true"


def ENRICHMENT_TIMEOUT_S() -> float:
    return float(os.getenv("ENRICHMENT_TIMEOUT_S", "300"))


def ENRICHMENT_MAX_CONCURRENT() -> int:
    return int(os.getenv("ENRICHMENT_MAX_CONCURRENT", "3"))


def ENRICHMENT_MAX_TOOL_CALLS() -> int:
    return int(os.getenv("ENRICHMENT_MAX_TOOL_CALLS", "20"))


def ENRICHMENT_MAX_TOKENS() -> int:
    return int(os.getenv("ENRICHMENT_MAX_TOKENS", "100000"))


def ENRICHMENT_TOP_K() -> int:
    return int(os.getenv("ENRICHMENT_TOP_K", "20"))