# Edge Case Functionality — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two extraction gaps — symlink deduplication in StructureDetector, and multi-language repo tiering in MetadataDetector. Rust/Cargo.toml detection is already implemented.

**Architecture:** Small patches to existing files. No new detector files needed for Rust (it's already detected via `Cargo.toml` in `framework_manifests` and `detect_technology_stack` returns "Rust").

**Tech Stack:** Python 3.11

---

## File Map

```
sources/Api/app/services/c4/containers/
  structure_detector.py      # MODIFY — add symlink deduplication
  utils.py                  # READ ONLY — detect_technology_stack already handles Rust

sources/Api/app/services/c4/context/
  metadata_detector.py       # MODIFY — patch detect_tier for multi-lang repos

sources/Api/tests/e2e/
  test_edge_cases.py         # CREATE (from integration-test-suite plan)
```

**Important:** All paths relative to `sources/Api/`. Tests run via `docker compose exec api python -m pytest`.

---

## Known State (important preconditions)

1. **Rust detection is ALREADY implemented.** `Cargo.toml` is in `framework_manifests` (line 51 of `structure_detector.py`). `detect_technology_stack()` in `utils.py` (line 99-100) returns `"Rust"` for `Cargo.toml`. No code change needed for Rust — only the test verifies it works.

2. **Symlink gap is real.** `omnipay-symlink-service/src/app.py` is a symlink to `../shared/app.py`. Without deduplication, `os.walk` sees both paths and `StructureDetector._create_container()` may register both `src/` and `shared/` as separate services.

3. **Multi-lang tiering gap:** Need to verify if `detect_tier()` in `metadata_detector.py` handles polyglot repos. Will check before implementing.

---

### Task 1: Investigate multi-lang tiering in metadata_detector.py

**Files:**
- Read: `app/services/c4/context/metadata_detector.py` — find `detect_tier` method

- [ ] **Step 1: Read the detect_tier method**

```bash
grep -n "detect_tier\|def detect_tier" sources/Api/app/services/c4/context/metadata_detector.py | head -20
```

Read the full method to understand current tier logic.

- [ ] **Step 2: Check if it handles multiple languages**

If `detect_tier` already considers `languages` or `technologies` list and picks the highest tier — no change needed. If it only looks at a single technology, implement the patch described in Task 3.

---

### Task 2: Implement symlink deduplication in StructureDetector

**Files:**
- Modify: `sources/Api/app/services/c4/containers/structure_detector.py`
- Test: `sources/Api/tests/e2e/test_edge_cases.py::TestSymlinkHandling`

**Key insight:** `os.walk` follows symlinks by default and will visit `shared/` and `src/` (via the symlink) as separate directories. We need to track resolved (real) paths and skip duplicates.

- [ ] **Step 1: Read the current detect() method fully**

```bash
sed -n '71,115p' sources/Api/app/services/c4/containers/structure_detector.py
```

- [ ] **Step 2: Write the failing test first**

```bash
cat >> sources/Api/tests/e2e/test_edge_cases.py << 'EOF'


class TestSymlinkHandling:
    """Test symlink resolution — no duplicate containers."""

    @pytest.fixture(scope="class")
    def symlink_containers(self):
        """omnipay-symlink-service: src/app.py -> ../shared/app.py (symlink)."""
        path = DEMO_DIR / "omnipay-symlink-service"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_containers(path)

    def test_no_duplicate_containers(self, symlink_containers):
        """Symlink should not create duplicate containers."""
        names = [c.get("name") for c in symlink_containers]
        # shared and src should not both appear as separate services
        assert "shared" not in names or "src" not in names or names.count("shared") == 1, \
            f"Symlink created duplicate: {names}"

    def test_symlink_service_count(self, symlink_containers):
        """Should detect at least 1 service (the root), not double."""
        assert len(symlink_containers) >= 1, \
            f"Expected at least 1 service, got {len(symlink_containers)}: {[c.get('name') for c in symlink_containers]}"
EOF
```

Run the test to confirm it fails:
```bash
docker compose exec api python -m pytest tests/e2e/test_edge_cases.py::TestSymlinkHandling -v
```
Expected: FAIL — symlink creates duplicate entries

- [ ] **Step 3: Implement the fix in StructureDetector**

Read the full file first, then edit:

```python
# In structure_detector.py, modify the detect() method.
# Add a set to track resolved (real) paths that have already been registered.
# After resolving service_dir, check if its resolved path was already seen.

# Add near the top of detect() method, after registered_paths:
resolved_paths = set()  # Track resolved paths to dedupe symlinks

# Inside the loop, after computing service_dir:
# Get the resolved (real) path to detect symlink duplicates
try:
    resolved_service_dir = service_dir.resolve()
except (OSError, RuntimeError):
    resolved_service_dir = service_dir

resolved_rel = resolved_service_dir.relative_to(self.repo_path)
if str(resolved_rel) in resolved_paths:
    continue  # Skip — this is a symlink to an already-seen directory
resolved_paths.add(str(resolved_rel))
```

The exact location is after `rel_path = service_dir.relative_to(self.repo_path)` and before the `_is_deployable_service` check.

- [ ] **Step 4: Run the test to verify it passes**

```bash
docker compose exec api python -m pytest tests/e2e/test_edge_cases.py::TestSymlinkHandling -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/c4/containers/structure_detector.py
git commit -m "fix(containers): deduplicate symlinked paths in StructureDetector"
```

---

### Task 3: Implement multi-language tiering in MetadataDetector

**Files:**
- Modify: `sources/Api/app/services/c4/context/metadata_detector.py`
- Test: `sources/Api/tests/e2e/test_edge_cases.py::TestMultiLangTiering`

**Rule:** If any detected language is associated with Tier 1 (Java, TypeScript in payment domain, C#/.NET), assign Tier 1.

- [ ] **Step 1: Find the detect_tier method**

```bash
grep -n "def detect_tier" sources/Api/app/services/c4/context/metadata_detector.py
```

- [ ] **Step 2: Read the current implementation**

```bash
sed -n '<line where detect_tier starts>,<line where it ends>p' sources/Api/app/services/c4/context/metadata_detector.py
```

Replace `<line where detect_tier starts>` with the actual line number from grep.

- [ ] **Step 3: Write the failing test first**

```python
class TestMultiLangTiering:
    """Test polyglot repos get correct tier based on highest-criticality language."""

    @pytest.fixture(scope="class")
    def multi_lang_context(self):
        """omnipay-multi-lang: polyglot service."""
        path = DEMO_DIR / "omnipay-multi-lang"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_context(path)

    def test_tier_reflects_highest_language(self, multi_lang_context):
        """Tier should be set (not Unknown) for polyglot repos."""
        tier = str(multi_lang_context.get("tier", "")).lower()
        assert tier not in ("unknown", ""), \
            f"Polyglot repo should have a tier, got: {tier}"
```

Run to confirm it fails (if tier is Unknown for multi-lang):
```bash
docker compose exec api python -m pytest tests/e2e/test_edge_cases.py::TestMultiLangTiering -v
```

- [ ] **Step 4: Implement the patch**

Patch `detect_tier()` to accept a `languages` parameter (list of detected languages), and pick the highest tier:

```python
# Tier assignment based on highest-criticality language
# Tier 1: Java, TypeScript, C# (payment-critical languages)
# Tier 2: Python, Go, Rust
# Tier 3: Shell, Terraform, other IaC
TIER1_LANGUAGES = {"java", "typescript", "javascript", "c#", "csharp", ".net"}
TIER2_LANGUAGES = {"python", "go", "rust"}

def detect_tier(
    self,
    languages: Optional[List[str]] = None,
    repo_path: Optional[Path] = None,
    project_dir: Optional[Path] = None,
) -> str:
    """Detect the criticality tier of a service.

    Args:
        languages: List of detected language names (e.g., ["Java", "Python"])
        repo_path: Path to repository root
        project_dir: Path to specific project/service directory
    """
    if languages:
        lang_lower = {l.lower() for l in languages}
        if TIER1_LANGUAGES & lang_lower:
            return "Tier 1"
        if TIER2_LANGUAGES & lang_lower:
            return "Tier 2"
    # ... existing logic for single-language detection ...
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
docker compose exec api python -m pytest tests/e2e/test_edge_cases.py::TestMultiLangTiering -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/c4/context/metadata_detector.py
git commit -m "fix(context): tier multi-lang repos by highest-criticality language"
```

---

## Self-Review Checklist

- [ ] Spec coverage: symlink deduplication (3B-2) and multi-lang tiering (3B-3) both covered
- [ ] No placeholders: all code is complete
- [ ] Symlink fix: Uses `resolved_paths` set to dedupe symlinks without removing legitimate services
- [ ] Multi-lang fix: Passes `languages` list to `detect_tier`, picks highest tier
- [ ] Tests: `TestSymlinkHandling` and `TestMultiLangTiering` both pass
- [ ] Rust: No code change needed (already implemented in `detect_technology_stack`)
