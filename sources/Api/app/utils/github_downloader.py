"""Minimal GitHub repository downloader for C4 extraction."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitHubDownloader:
    """Download GitHub repositories for analysis."""

    @staticmethod
    def is_github_url(url: str) -> bool:
        """Validate if URL is a GitHub repository URL."""
        github_pattern = r'^https://github\.com/[\w\-\.]+/[\w\-\.]+/?$'
        return bool(re.match(github_pattern, url.strip()))

    @staticmethod
    def download_repository(
        github_url: str,
        output_dir: Path,
        use_git: bool = True,
        full_history: bool = False,
    ) -> Path:
        """Download a GitHub repository.
        
        Args:
            github_url: GitHub repository URL
            output_dir: Directory to save the repository
            use_git: Use git clone (True) or download archive (False)
            full_history: Clone with full history (True) or shallow (False)
            
        Returns:
            Path to the downloaded repository
        """
        logger.info(f"Downloading repository from {github_url}")
        
        # Extract owner and repo name
        match = re.search(r'github\.com/([\w\-\.]+)/([\w\-\.]+)', github_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {github_url}")
        
        owner, repo = match.groups()
        repo = repo.rstrip('/')
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        repo_path = output_dir / repo
        
        if use_git:
            # Use git clone
            try:
                github_token = os.getenv('GITHUB_TOKEN')
                
                if github_token:
                    # Use authenticated URL
                    clone_url = f"https://{github_token}@github.com/{owner}/{repo}.git"
                else:
                    clone_url = f"https://github.com/{owner}/{repo}.git"
                
                git_cmd = ['git', 'clone']
                
                if not full_history:
                    git_cmd.extend(['--depth', '1'])
                
                git_cmd.extend([clone_url, str(repo_path)])
                
                logger.info(f"Running: git clone {'--depth 1 ' if not full_history else ''}{github_url}")
                subprocess.run(git_cmd, check=True, capture_output=True, text=True)
                
                logger.info(f"Repository cloned successfully to {repo_path}")
                return repo_path
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Git clone failed: {e.stderr}")
                raise RuntimeError(f"Failed to clone repository: {e.stderr}")
        
        else:
            # Use archive download (simpler, no git required)
            import requests
            
            archive_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
            
            logger.info(f"Downloading archive from {archive_url}")
            
            try:
                response = requests.get(archive_url, timeout=60)
                response.raise_for_status()
                
                zip_path = output_dir / f"{repo}.zip"
                with open(zip_path, 'wb') as f:
                    f.write(response.content)
                
                # Extract ZIP
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                
                # Find extracted directory (usually repo-main)
                extracted_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith(repo)]
                if extracted_dirs:
                    extracted_dir = extracted_dirs[0]
                    if extracted_dir != repo_path:
                        extracted_dir.rename(repo_path)
                
                zip_path.unlink()  # Clean up ZIP
                
                logger.info(f"Repository downloaded successfully to {repo_path}")
                return repo_path
                
            except Exception as e:
                logger.error(f"Archive download failed: {e}")
                raise RuntimeError(f"Failed to download repository: {str(e)}")
