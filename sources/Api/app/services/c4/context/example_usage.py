"""Example usage of the enhanced Context Manager.

Shows how to extract all 7 Service model fields from a repository.
"""

from pathlib import Path
from app.services.c4.context import ContextManager


def extract_service_metadata(repo_path: str, llm_manager=None):
    """Extract complete service metadata including all 7 primary fields.
    
    Args:
        repo_path: Path to the repository
        llm_manager: Optional LLM manager for enhanced detection
    
    Returns:
        Complete context dictionary with all Service model fields
    """
    manager = ContextManager(
        repo_path=Path(repo_path),
        llm_manager=llm_manager,
        containers={}  # Can be populated if containers are pre-detected
    )
    
    # Extract complete context
    context = manager.extract_context()
    
    # Print the 7 primary Service model fields
    print("\n" + "="*80)
    print("SERVICE METADATA EXTRACTION RESULTS")
    print("="*80)
    
    print("\n🎯 PRIMARY SERVICE FIELDS (The 7 Key Attributes):")
    print("-" * 80)
    print(f"1. Domain:        {context.get('domain', 'N/A')}")
    print(f"2. Owner:         {context.get('owner', 'N/A')}")
    print(f"3. Status:        {context.get('status', 'N/A')}")
    print(f"4. Tier:          {context.get('tier', 'N/A')}")
    print(f"5. Data Class:    {context.get('data_class', 'N/A')}")
    print(f"6. Active Experts:{context.get('active_experts', 0)} contributors")
    print(f"7. Compliance:    {context.get('compliance', 'N/A')}")
    
    print("\n📊 GIT ACTIVITY METRICS:")
    print("-" * 80)
    print(f"Last Commit:      {context.get('last_commit_date', 'N/A')}")
    print(f"Commits (30d):    {context.get('commit_count_30d', 0)}")
    print(f"Commits (90d):    {context.get('commit_count_90d', 0)}")
    print(f"Commits (180d):   {context.get('commit_count_180d', 0)}")
    print(f"Contributors:     {context.get('contributor_count', 0)}")
    
    print("\n👥 OWNER & CONTRIBUTORS:")
    print("-" * 80)
    owner_stats = context.get('owner_contributor_stats', [])
    for i, contributor in enumerate(owner_stats[:5], 1):
        email = contributor.get('email', 'N/A')
        name = contributor.get('name', 'N/A')
        commits = contributor.get('commit_count', 0)
        print(f"{i}. {name:<30} {email:<40} ({commits} commits)")
    
    if context.get('status_evidence'):
        evidence = context['status_evidence']
        print("\n📈 STATUS EVIDENCE:")
        print("-" * 80)
        print(f"Recent Activity:  {evidence.get('commits_30d')} commits in 30d, "
              f"{evidence.get('commits_90d')} in 90d, {evidence.get('commits_180d')} in 180d")
        print(f"Last Activity:    {evidence.get('days_since_last_commit')} days ago")
    
    print("\n" + "="*80)
    
    return context


if __name__ == "__main__":
    # Example: Extract metadata for current repository
    import os
    current_repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    print(f"Extracting metadata from: {current_repo}")
    context = extract_service_metadata(current_repo)
    
    # Access fields programmatically
    if context['compliance'] in ['NON_COMPLIANT', 'AT_RISK']:
        print(f"\n⚠️  WARNING: Compliance issue detected: {context['compliance']}")
    
    if context['active_experts'] < 2:
        print(f"\n⚠️  WARNING: Bus factor risk! Only {context['active_experts']} active expert(s)")
    
    if context['status'] == 'Deprecated / Frozen':
        print(f"\n⚠️  WARNING: Service appears to be deprecated/frozen")
