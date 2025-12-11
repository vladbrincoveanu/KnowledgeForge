import shutil
import sys
import tempfile
import subprocess
import logging
from pathlib import Path
import pytest

# Ensure backend sources are importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.service_extraction.service_extractor import ServiceExtractor
from app.services.service_extraction.extraction_config import ExtractionConfig
from app.domain.models.services import ServiceStatus

class TestServiceExtractionEnhancement:
    @pytest.fixture
    def test_repo(self):
        """Create a temporary git repo with service structure."""
        # Use resolve() to handle potential symlinks in tmp paths
        temp_dir = Path(tempfile.mkdtemp()).resolve()
        
        try:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=temp_dir, check=True)
            # Configure git for this repo
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
            
            # Create structure:
            # services/
            #   payment-service/ (Python) - imports core
            #   auth-service/ (Node)
            #   core/ (Shared)
            
            services_dir = temp_dir / "services"
            services_dir.mkdir()
            
            # 1. Setup Payment Service (Domain: payments, Depends: core)
            payment_dir = services_dir / "payment-service"
            payment_dir.mkdir()
            (payment_dir / "requirements.txt").write_text("flask\n")
            payment_file = payment_dir / "app.py"
            payment_file.write_text("from services.core import utils\n\nprint('processing payment')")
            
            # 2. Setup Core Service (Domain: core)
            core_dir = services_dir / "core"
            core_dir.mkdir()
            (core_dir / "setup.py").write_text("# setup")
            core_file = core_dir / "utils.py"
            core_file.write_text("def help(): pass")
            (core_dir / "__init__.py").write_text("")
            
            # 3. Setup Auth Service (Domain: identity, Owner: distinct)
            auth_dir = services_dir / "auth-service"
            auth_dir.mkdir()
            (auth_dir / "package.json").write_text('{"name": "@company/auth-service"}')
            auth_file = auth_dir / "index.js"
            auth_file.write_text("const core = require('../../core/utils');")
            
            # Commit 1: Initial (Author: dev1)
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)
            
            # Commit 2: Feature in Payment (Author: payment-owner)
            subprocess.run(["git", "config", "user.email", "payment@owner.com"], cwd=temp_dir, check=True)
            payment_file.write_text(payment_file.read_text() + "\n# feature: add stripe")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "feat: add stripe support"], cwd=temp_dir, check=True)
            
            # Commit 3: Fix in Payment (Author: payment-owner)
            payment_file.write_text(payment_file.read_text() + "\n# fix: bug")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "fix: critical bug"], cwd=temp_dir, check=True)
            
            # Commit 4: Feature in Auth (Author: auth-owner)
            subprocess.run(["git", "config", "user.email", "auth@owner.com"], cwd=temp_dir, check=True)
            auth_file.write_text(auth_file.read_text() + "\n// feature: login")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "feat: login flow"], cwd=temp_dir, check=True)

            yield temp_dir
            
        finally:
            shutil.rmtree(temp_dir)

    def test_full_extraction_chain(self, test_repo):
        """Test that all enhancement phases work together."""
        # Enable all flags
        ExtractionConfig.ENABLE_GIT_ANALYSIS = True
        ExtractionConfig.ENABLE_DOMAIN_DETECTION = True
        ExtractionConfig.ENABLE_DEPENDENCY_SCAN = True
        ExtractionConfig.ENABLE_LLM_DESCRIPTIONS = False
        
        # Configure logging to see debug output
        logging.basicConfig(level=logging.DEBUG)
        
        extractor = ServiceExtractor(test_repo)
        services = extractor.extract_services()

        # Map by name for easy checking
        svc_map = {s.name: s for s in services}
        
        print(f"Discovered services: {list(svc_map.keys())}")
        
        # 1. Verify Payment Service
        payment_svc = svc_map.get("payment-service")
        assert payment_svc is not None, "payment-service not found"
        
        # Domain: 'payments' (from name 'payment-service')
        assert payment_svc.domain == "payments", f"Expected 'payments', got {payment_svc.domain}"
        
        # Owner: 'payment@owner.com' has 2 commits vs 1 initial
        assert payment_svc.owner == "payment@owner.com", f"Expected payment@owner.com, got {payment_svc.owner}"
        
        # Status: Active-Dev (recent feature + fix)
        assert payment_svc.status.value == "Active-Dev"
        
        # 2. Verify Auth Service
        auth_svc = svc_map.get("auth-service")
        assert auth_svc is not None
        
        # Domain: 'identity' (from 'auth')
        assert auth_svc.domain == "identity"
        
        # Owner: 'auth@owner.com'
        assert auth_svc.owner == "auth@owner.com"
