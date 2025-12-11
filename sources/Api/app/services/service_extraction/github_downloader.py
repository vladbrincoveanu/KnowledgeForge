"""GitHub repository downloader and extractor."""

import logging
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class GitHubDownloader:
    """Download and extract repositories from GitHub."""
    
    @staticmethod
    def is_github_url(url: str) -> bool:
        """Check if URL is a GitHub repository URL."""
        parsed = urlparse(url)
        return 'github.com' in parsed.netloc.lower() or 'github.io' in parsed.netloc.lower()
    
    @staticmethod
    def download_repository(
        github_url: str,
        output_dir: Optional[Path] = None,
        use_git: bool = True,
        full_history: Optional[bool] = None,
    ) -> Path:
        """
        Download a GitHub repository.
        
        Args:
            github_url: GitHub repository URL (e.g., https://github.com/user/repo)
            output_dir: Directory to extract to (creates temp dir if None)
            use_git: Use git clone if available, otherwise use ZIP download
        
        Returns:
            Path to extracted repository directory
        
        Raises:
            ValueError: If URL is not a valid GitHub URL
            RuntimeError: If download fails
        """
        if not GitHubDownloader.is_github_url(github_url):
            raise ValueError(f"Not a valid GitHub URL: {github_url}")
        
        # Parse GitHub URL
        parsed = urlparse(github_url)
        path_parts = [p for p in parsed.path.split('/') if p]
        
        if len(path_parts) < 2:
            if len(path_parts) == 1:
                # Organization URL provided, suggest repository URL
                org = path_parts[0]
                raise ValueError(
                    f"Invalid GitHub URL format: {github_url}. "
                    f"This appears to be an organization URL. Please provide a full repository URL. "
                    f"Example: https://github.com/{org}/{org} or https://github.com/{org}/<repository-name>"
                )
            else:
                raise ValueError(
                    f"Invalid GitHub URL format: {github_url}. "
                    f"Please provide a full repository URL in the format: https://github.com/owner/repository"
                )
        
        owner = path_parts[0]
        repo = path_parts[1].replace('.git', '')
        
        # Handle branch/tag if specified
        branch = None
        if len(path_parts) > 3 and path_parts[2] in ['tree', 'blob']:
            branch = path_parts[3]
        elif '#' in github_url:
            branch = github_url.split('#')[-1]
        
        # Create output directory
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix=f"github_{owner}_{repo}_"))
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        repo_dir = output_dir / repo
        
        # Try git clone first if requested
        if use_git:
            try:
                logger.info(f"Attempting git clone for {owner}/{repo}")
                clone_url = f"https://github.com/{owner}/{repo}.git"
                
                clone_cmd = ['git', 'clone']
                if full_history is None:
                    full_history = False
                if not full_history:
                    clone_cmd.extend(['--depth', '1'])
                if branch:
                    clone_cmd.extend(['--branch', branch])
                clone_cmd.extend([clone_url, str(repo_dir)])
                
                result = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=True
                )
                
                logger.info(f"Successfully cloned repository to {repo_dir}")
                return repo_dir
            
            except subprocess.TimeoutExpired:
                logger.warning("Git clone timed out, falling back to ZIP download")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.warning(f"Git clone failed: {e}, falling back to ZIP download")
        
        # Fall back to ZIP download
        logger.info(f"Downloading repository as ZIP for {owner}/{repo}")
        
        # Construct ZIP download URL
        if branch:
            zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
        else:
            zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
        
        # Try main branch first, then master
        try:
            zip_path = GitHubDownloader._download_zip(zip_url, output_dir)
        except requests.HTTPError as e:
            if e.response.status_code == 404 and not branch:
                # Try master branch
                zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip"
                zip_path = GitHubDownloader._download_zip(zip_url, output_dir)
            else:
                raise
        
        # Extract ZIP
        extract_dir = output_dir / 'extracted'
        extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find the extracted repository directory
        extracted_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        if extracted_dirs:
            repo_dir = extracted_dirs[0]
            # Move to expected location
            final_dir = output_dir / repo
            if repo_dir != final_dir:
                if final_dir.exists():
                    shutil.rmtree(final_dir)
                shutil.move(str(repo_dir), str(final_dir))
                repo_dir = final_dir
        else:
            raise RuntimeError("Failed to extract repository from ZIP")
        
        # Cleanup ZIP file
        zip_path.unlink()
        extract_dir.rmdir()
        
        logger.info(f"Successfully extracted repository to {repo_dir}")
        return repo_dir
    
    @staticmethod
    def _download_zip(zip_url: str, output_dir: Path) -> Path:
        """Download ZIP file from URL."""
        logger.info(f"Downloading ZIP from {zip_url}")
        
        response = requests.get(zip_url, stream=True, timeout=300)
        response.raise_for_status()
        
        zip_path = output_dir / 'repo.zip'
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded ZIP to {zip_path}")
        return zip_path
