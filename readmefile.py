import os
import shutil
from git import Repo
import requests
from collections import defaultdict
import re
from typing import Dict, List, Any
import json
from pathlib import Path
import tempfile

class GitHubRepoAnalyzer:
    def __init__(self, github_repo_url: str, github_token: str = None):
        """
        Initialize the analyzer with a GitHub repository URL and optional token
        
        Args:
            github_repo_url: URL of the GitHub repository (e.g., 'username/repo' or full HTTPS URL)
            github_token: GitHub personal access token for API access
        """
        self.github_token = github_token
        self.headers = {'Authorization': f'token {github_token}'} if github_token else {}
        
        # Parse repository URL
        if 'github.com' in github_repo_url:
            self.repo_name = github_repo_url.rstrip('.git').split('github.com/')[-1]
        else:
            self.repo_name = github_repo_url
            
        # Create temporary directory for cloning
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.temp_dir, self.repo_name.split('/')[-1])
        
        # Clone repository
        self._clone_repository()

    def _clone_repository(self):
        """Clone the repository to a temporary directory"""
        clone_url = f"https://github.com/{self.repo_name}.git"
        if self.github_token:
            clone_url = f"https://{self.github_token}@github.com/{self.repo_name}.git"
            
        print(f"Cloning repository to {self.repo_path}...")
        self.repo = Repo.clone_from(clone_url, self.repo_path)
        print("Repository cloned successfully!")

    def cleanup(self):
        """Remove the temporary directory and its contents"""
        try:
            shutil.rmtree(self.temp_dir)
            print("Cleanup completed successfully!")
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

    def get_basic_info(self) -> Dict[str, Any]:
        """Extract basic repository information"""
        remote_url = next(self.repo.remote().urls)
        repo_name = remote_url.split('/')[-1].replace('.git', '')
        owner = remote_url.split('/')[-2].split(':')[-1]
        
        return {
            'repository_name': repo_name,
            'owner': owner,
            'default_branch': self.repo.active_branch.name,
            'remote_url': remote_url
        }

    def analyze_directory_structure(self) -> Dict[str, List[str]]:
        """Analyze the repository directory structure"""
        structure = defaultdict(list)
        
        for root, dirs, files in os.walk(self.repo_path):
            if '.git' in root:
                continue
                
            rel_path = os.path.relpath(root, self.repo_path)
            if rel_path == '.':
                rel_path = 'root'
                
            structure[rel_path] = [f for f in files if not f.startswith('.')]
            
        return dict(structure)

    def get_dependencies(self) -> Dict[str, Any]:
        """Extract dependency information from common dependency files"""
        dependencies = {}
        
        # Check for package.json (Node.js)
        package_json = Path(self.repo_path) / 'package.json'
        if package_json.exists():
            with open(package_json) as f:
                data = json.load(f)
                dependencies['nodejs'] = {
                    'dependencies': data.get('dependencies', {}),
                    'devDependencies': data.get('devDependencies', {})
                }
                
        # Check for requirements.txt (Python)
        requirements_txt = Path(self.repo_path) / 'requirements.txt'
        if requirements_txt.exists():
            with open(requirements_txt) as f:
                dependencies['python'] = [line.strip() for line in f if line.strip() 
                                       and not line.startswith('#')]
                
        return dependencies

    def analyze_code_stats(self) -> Dict[str, Any]:
        """Analyze code statistics"""
        stats = defaultdict(int)
        language_patterns = {
            'python': r'\.py$',
            'javascript': r'\.js$',
            'typescript': r'\.ts$',
            'java': r'\.java$',
            'cpp': r'\.(cpp|hpp)$',
            'html': r'\.html$',
            'css': r'\.css$'
        }
        
        for root, _, files in os.walk(self.repo_path):
            if '.git' in root:
                continue
                
            for file in files:
                file_path = os.path.join(root, file)
                
                # Count files by language
                for lang, pattern in language_patterns.items():
                    if re.search(pattern, file, re.IGNORECASE):
                        stats[f'{lang}_files'] += 1
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                stats[f'{lang}_lines'] += sum(1 for _ in f)
                        except Exception:
                            # Skip files that can't be read
                            pass
                            
        return dict(stats)

    def get_commit_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent commit history"""
        commits = []
        for commit in list(self.repo.iter_commits())[:limit]:
            commits.append({
                'hash': commit.hexsha,
                'author': str(commit.author),
                'date': str(commit.committed_datetime),
                'message': commit.message.strip()
            })
        return commits

    def extract_documentation_hints(self) -> Dict[str, Any]:
        """Extract documentation hints from the codebase"""
        hints = {
            'todos': [],
            'api_endpoints': [],
            'functions': [],
            'classes': []
        }
        
        for root, _, files in os.walk(self.repo_path):
            if '.git' in root:
                continue
                
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.java')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                            # Extract TODOs
                            todos = re.findall(r'#\s*TODO:?\s*(.+)$', content, re.MULTILINE)
                            hints['todos'].extend(todos)
                            
                            # Extract API endpoints (basic detection)
                            if 'router' in content.lower() or 'app.' in content.lower():
                                endpoints = re.findall(r'@\w+\.route\([\'"]([^\'"]+)[\'"]\)', content)
                                hints['api_endpoints'].extend(endpoints)
                            
                            # Extract function definitions
                            functions = re.findall(r'def\s+(\w+)\s*\(', content)
                            hints['functions'].extend(functions)
                            
                            # Extract class definitions
                            classes = re.findall(r'class\s+(\w+)\s*[:\(]', content)
                            hints['classes'].extend(classes)
                    except Exception:
                        # Skip files that can't be read
                        pass
        
        # Remove duplicates and sort
        for key in hints:
            hints[key] = sorted(list(set(hints[key])))
            
        return hints

    def generate_readme_data(self) -> Dict[str, Any]:
        """
        Collect all repository information for README generation
        """
        return {
            'basic_info': self.get_basic_info(),
            'directory_structure': self.analyze_directory_structure(),
            'dependencies': self.get_dependencies(),
            'code_stats': self.analyze_code_stats(),
            'recent_commits': self.get_commit_history(),
            'documentation_hints': self.extract_documentation_hints()
        }

def analyze_github_repo(repo_url: str, github_token: str = None, output_file: str = 'readme_data.json'):
    """
    Analyze a GitHub repository and save the data to a JSON file
    
    Args:
        repo_url: GitHub repository URL or 'username/repo'
        github_token: Optional GitHub personal access token
        output_file: Path to save the JSON output
    """
    try:
        # Initialize analyzer and clone repository
        analyzer = GitHubRepoAnalyzer(repo_url, github_token)
        
        # Generate readme data
        readme_data = analyzer.generate_readme_data()
        
        # Save the extracted data to a JSON file
        with open(output_file, 'w') as f:
            json.dump(readme_data, f, indent=2)
        
        print(f"Repository analysis complete. Data saved to {output_file}")
        
        # Cleanup temporary files
        analyzer.cleanup()
        
    except Exception as e:
        print(f"Error analyzing repository: {str(e)}")
        raise

if __name__ == "__main__":
    # Example usage
    analyze_github_repo(
        repo_url="",
        github_token="",  # Optional
        output_file="readme_data.json"
    )