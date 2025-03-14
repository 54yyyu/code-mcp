                    license_type = "MIT"
                elif "Apache" in license_content:
                    license_type = "Apache"
                elif "GPL" in license_content:
                    license_type = "GPL"
                elif "BSD" in license_content:
                    license_type = "BSD"
                
                readme_content += f"## License\n\nThis project is licensed under the {license_type} License - see the LICENSE file for details.\n\n"
        else:
            readme_content += "## License\n\nSpecify your project license here.\n\n"
        
        # Prepare the final README preview
        readme_preview = f"""# README.md Preview

Below is a preview of what the generated README.md will look like:

```markdown
{readme_content}
```

To actually create this README.md file, use the `confirm_generate_readme` tool.
"""
        
        return readme_preview
        
    except Exception as e:
        return f"Error generating README: {str(e)}"

@mcp.tool()
async def confirm_generate_readme(ctx: Context) -> str:
    """
    Confirm and create a README.md file based on the previously generated preview.
    """
    try:
        # Detect project type and structure
        package_json_path = PROJECT_ROOT / "package.json"
        requirements_txt_path = PROJECT_ROOT / "requirements.txt"
        pyproject_toml_path = PROJECT_ROOT / "pyproject.toml"
        cargo_toml_path = PROJECT_ROOT / "Cargo.toml"
        gradle_path = PROJECT_ROOT / "build.gradle"
        maven_path = PROJECT_ROOT / "pom.xml"
        
        # Check for existing README
        readme_path = PROJECT_ROOT / "README.md"
        if readme_path.exists():
            backup_path = PROJECT_ROOT / "README.md.bak"
            shutil.copy2(readme_path, backup_path)
            ctx.info(f"Backed up existing README.md to {backup_path}")
        
        # Gather project information
        project_name = PROJECT_ROOT.name
        project_type = "Unknown"
        project_description = ""
        
        # Node.js project
        if package_json_path.exists():
            project_type = "Node.js"
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                project_description = package_data.get("description", "")
            except:
                pass
        
        # Python project
        elif requirements_txt_path.exists() or pyproject_toml_path.exists():
            project_type = "Python"
            if pyproject_toml_path.exists():
                # Try to extract description from pyproject.toml
                with open(pyproject_toml_path, 'r') as f:
                    pyproject_content = f.read()
                    import re
                    description_match = re.search(r'description\s*=\s*"([^"]*)"', pyproject_content)
                    if description_match:
                        project_description = description_match.group(1)
        
        # Rust project
        elif cargo_toml_path.exists():
            project_type = "Rust"
            with open(cargo_toml_path, 'r') as f:
                cargo_content = f.read()
                import re
                description_match = re.search(r'description\s*=\s*"([^"]*)"', cargo_content)
                if description_match:
                    project_description = description_match.group(1)
        
        # Java with Gradle
        elif gradle_path.exists():
            project_type = "Java (Gradle)"
        
        # Java with Maven
        elif maven_path.exists():
            project_type = "Java (Maven)"
        
        # Generate README structure
        readme_content = f"# {project_name}\n\n"
        
        if project_description:
            readme_content += f"{project_description}\n\n"
        
        # Generate project structure section
        readme_content += "## Project Structure\n\n"
        
        # List main directories
        top_level_dirs = [d for d in PROJECT_ROOT.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if top_level_dirs:
            readme_content += "The project consists of the following main directories:\n\n"
            for directory in sorted(top_level_dirs):
                readme_content += f"- **{directory.name}/**: "
                
                # Try to guess directory purpose
                if directory.name.lower() in ["src", "source", "lib"]:
                    readme_content += "Contains the source code for the project."
                elif directory.name.lower() in ["test", "tests", "spec"]:
                    readme_content += "Contains the test suite for the project."
                elif directory.name.lower() in ["docs", "documentation"]:
                    readme_content += "Contains project documentation."
                elif directory.name.lower() == "examples":
                    readme_content += "Contains example code and usage examples."
                elif directory.name.lower() in ["scripts", "tools"]:
                    readme_content += "Contains utility scripts and tools."
                elif directory.name.lower() == "public":
                    readme_content += "Contains public assets for web projects."
                elif directory.name.lower() == "assets":
                    readme_content += "Contains project assets like images, fonts, etc."
                elif directory.name.lower() == "config":
                    readme_content += "Contains configuration files."
                
                readme_content += "\n"
            
            readme_content += "\n"
        
        # Installation section based on project type
        readme_content += "## Installation\n\n"
        
        if project_type == "Node.js":
            readme_content += "```bash\n# Clone the repository\ngit clone https://github.com/username/repo.git\ncd repo\n\n# Install dependencies\nnpm install\n```\n\n"
        elif project_type == "Python":
            readme_content += "```bash\n# Clone the repository\ngit clone https://github.com/username/repo.git\ncd repo\n\n# Create and activate virtual environment (optional)\npython -m venv venv\nsource venv/bin/activate  # On Windows: venv\\Scripts\\activate\n\n# Install dependencies\npip install -r requirements.txt\n```\n\n"
        elif project_type == "Rust":
            readme_content += "```bash\n# Clone the repository\ngit clone https://github.com/username/repo.git\ncd repo\n\n# Build the project\ncargo build\n```\n\n"
        elif project_type.startswith("Java"):
            if project_type == "Java (Gradle)":
                readme_content += "```bash\n# Clone the repository\ngit clone https://github.com/username/repo.git\ncd repo\n\n# Build with Gradle\n./gradlew build\n```\n\n"
            else:
                readme_content += "```bash\n# Clone the repository\ngit clone https://github.com/username/repo.git\ncd repo\n\n# Build with Maven\nmvn install\n```\n\n"
        else:
            readme_content += "```bash\n# Clone the repository\ngit clone https://github.com/username/repo.git\ncd repo\n```\n\n"
        
        # Usage section
        readme_content += "## Usage\n\n"
        readme_content += "Describe how to use your project here.\n\n"
        
        # Add license section
        license_path = PROJECT_ROOT / "LICENSE"
        if license_path.exists():
            with open(license_path, 'r') as f:
                license_content = f.read()
                license_type = "Custom"
                
                # Try to detect license type
                if "MIT" in license_content:
                    license_type = "MIT"
                elif "Apache" in license_content:
                    license_type = "Apache"
                elif "GPL" in license_content:
                    license_type = "GPL"
                elif "BSD" in license_content:
                    license_type = "BSD"
                
                readme_content += f"## License\n\nThis project is licensed under the {license_type} License - see the LICENSE file for details.\n\n"
        else:
            readme_content += "## License\n\nSpecify your project license here.\n\n"
        
        # Write the README.md file
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
        return f"Successfully generated README.md at {readme_path}"
        
    except Exception as e:
        return f"Error creating README: {str(e)}"

@mcp.tool()
async def generate_contributing_guide(ctx: Context) -> str:
    """
    Generate a CONTRIBUTING.md file with guidelines for project contributors.
    """
    try:
        # Check for existing CONTRIBUTING.md
        contributing_path = PROJECT_ROOT / "CONTRIBUTING.md"
        if contributing_path.exists():
            with open(contributing_path, 'r') as f:
                existing_content = f.read()
            return f"""CONTRIBUTING.md already exists with the following content:

```markdown
{existing_content}
```

If you want to generate a new CONTRIBUTING.md, use the `confirm_generate_contributing` tool.
"""
        
        # Detect project type
        has_git = (PROJECT_ROOT / ".git").exists()
        package_json_path = PROJECT_ROOT / "package.json"
        requirements_txt_path = PROJECT_ROOT / "requirements.txt"
        pyproject_toml_path = PROJECT_ROOT / "pyproject.toml"
        cargo_toml_path = PROJECT_ROOT / "Cargo.toml"
        
        # Determine project type
        if package_json_path.exists():
            project_type = "Node.js"
        elif requirements_txt_path.exists() or pyproject_toml_path.exists():
            project_type = "Python"
        elif cargo_toml_path.exists():
            project_type = "Rust"
        else:
            project_type = "Generic"
        
        # Generate content
        contributing_content = "# Contributing Guidelines\n\n"
        contributing_content += "Thank you for your interest in contributing to this project! This document provides guidelines and instructions for contributing.\n\n"
        
        # Code of Conduct section
        contributing_content += "## Code of Conduct\n\n"
        contributing_content += "Please note that this project adheres to a Code of Conduct. By participating, you are expected to uphold this code.\n\n"
        
        # Getting Started section
        contributing_content += "## Getting Started\n\n"
        
        if has_git:
            contributing_content += "### Fork and Clone the Repository\n\n"
            contributing_content += "1. Fork the repository on GitHub\n"
            contributing_content += "2. Clone your fork locally\n"
            contributing_content += "```bash\n"
            contributing_content += "git clone https://github.com/YOUR_USERNAME/REPOSITORY_NAME.git\n"
            contributing_content += "cd REPOSITORY_NAME\n"
            contributing_content += "git remote add upstream https://github.com/ORIGINAL_OWNER/REPOSITORY_NAME.git\n"
            contributing_content += "```\n\n"
        
        # Setup section based on project type
        contributing_content += "### Setting Up Development Environment\n\n"
        
        if project_type == "Node.js":
            contributing_content += "```bash\n# Install dependencies\nnpm install\n\n# Run tests\nnpm test\n```\n\n"
        elif project_type == "Python":
            contributing_content += "```bash\n# Create and activate virtual environment\npython -m venv venv\nsource venv/bin/activate  # On Windows: venv\\Scripts\\activate\n\n# Install dependencies\npip install -r requirements.txt\n\n# Install development dependencies (if applicable)\npip install -r requirements-dev.txt\n```\n\n"
        elif project_type == "Rust":
            contributing_content += "```bash\n# Build the project\ncargo build\n\n# Run tests\ncargo test\n```\n\n"
        else:
            contributing_content += "Please refer to the README.md for setting up the development environment.\n\n"
        
        # Making Changes section
        contributing_content += "## Making Changes\n\n"
        
        if has_git:
            contributing_content += "1. Create a new branch for your changes\n"
            contributing_content += "```bash\ngit checkout -b feature/your-feature-name\n```\n\n"
            contributing_content += "2. Make your changes\n"
            contributing_content += "3. Add and commit your changes with a meaningful commit message\n"
            contributing_content += "```bash\ngit add .\ngit commit -m \"Add feature: brief description of changes\"\n```\n\n"
        
        # Style guidelines
        contributing_content += "## Style Guidelines\n\n"
        
        if project_type == "Node.js":
            contributing_content += "- Follow the existing code style\n"
            contributing_content += "- Run linting before submitting changes: `npm run lint`\n"
        elif project_type == "Python":
            contributing_content += "- Follow PEP 8 guidelines\n"
            contributing_content += "- Use docstrings for functions and classes\n"
            contributing_content += "- Run linting tools like flake8 or pylint before submitting changes\n"
        elif project_type == "Rust":
            contributing_content += "- Run `cargo fmt` before submitting changes\n"
            contributing_content += "- Run `cargo clippy` to check for common mistakes\n"
        else:
            contributing_content += "- Follow the existing code style in the project\n"
        
        contributing_content += "\n"
        
        # Testing section
        contributing_content += "## Testing\n\n"
        contributing_content += "- Add tests for new features\n"
        contributing_content += "- Ensure all tests pass before submitting a pull request\n"
        
        if project_type == "Node.js":
            contributing_content += "- Run tests with: `npm test`\n"
        elif project_type == "Python":
            contributing_content += "- Run tests with: `pytest` or `python -m unittest`\n"
        elif project_type == "Rust":
            contributing_content += "- Run tests with: `cargo test`\n"
        
        contributing_content += "\n"
        
        # Pull Request section
        if has_git:
            contributing_content += "## Submitting a Pull Request\n\n"
            contributing_content += "1. Push your changes to your fork\n"
            contributing_content += "```bash\ngit push origin feature/your-feature-name\n```\n\n"
            contributing_content += "2. Go to the original repository and create a pull request\n"
            contributing_content += "3. Fill in the PR template with all required information\n"
            contributing_content += "4. Wait for maintainers to review your PR\n\n"
        
        # Prepare the final CONTRIBUTING preview
        contributing_preview = f"""# CONTRIBUTING.md Preview

Below is a preview of what the generated CONTRIBUTING.md will look like:

```markdown
{contributing_content}
```

To actually create this CONTRIBUTING.md file, use the `confirm_generate_contributing` tool.
"""
        
        return contributing_preview
        
    except Exception as e:
        return f"Error generating CONTRIBUTING guide: {str(e)}"

@mcp.tool()
async def confirm_generate_contributing(ctx: Context) -> str:
    """
    Confirm and create a CONTRIBUTING.md file based on the previously generated preview.
    """
    try:
        # Check for existing CONTRIBUTING.md
        contributing_path = PROJECT_ROOT / "CONTRIBUTING.md"
        if contributing_path.exists():
            backup_path = PROJECT_ROOT / "CONTRIBUTING.md.bak"
            shutil.copy2(contributing_path, backup_path)
            ctx.info(f"Backed up existing CONTRIBUTING.md to {backup_path}")
        
        # Detect project type
        has_git = (PROJECT_ROOT / ".git").exists()
        package_json_path = PROJECT_ROOT / "package.json"
        requirements_txt_path = PROJECT_ROOT / "requirements.txt"
        pyproject_toml_path = PROJECT_ROOT / "pyproject.toml"
        cargo_toml_path = PROJECT_ROOT / "Cargo.toml"
        
        # Determine project type
        if package_json_path.exists():
            project_type = "Node.js"
        elif requirements_txt_path.exists() or pyproject_toml_path.exists():
            project_type = "Python"
        elif cargo_toml_path.exists():
            project_type = "Rust"
        else:
            project_type = "Generic"
        
        # Generate content
        contributing_content = "# Contributing Guidelines\n\n"
        contributing_content += "Thank you for your interest in contributing to this project! This document provides guidelines and instructions for contributing.\n\n"
        
        # Code of Conduct section
        contributing_content += "## Code of Conduct\n\n"
        contributing_content += "Please note that this project adheres to a Code of Conduct. By participating, you are expected to uphold this code.\n\n"
        
        # Getting Started section
        contributing_content += "## Getting Started\n\n"
        
        if has_git:
            contributing_content += "### Fork and Clone the Repository\n\n"
            contributing_content += "1. Fork the repository on GitHub\n"
            contributing_content += "2. Clone your fork locally\n"
            contributing_content += "```bash\n"
            contributing_content += "git clone https://github.com/YOUR_USERNAME/REPOSITORY_NAME.git\n"
            contributing_content += "cd REPOSITORY_NAME\n"
            contributing_content += "git remote add upstream https://github.com/ORIGINAL_OWNER/REPOSITORY_NAME.git\n"
            contributing_content += "```\n\n"
        
        # Setup section based on project type
        contributing_content += "### Setting Up Development Environment\n\n"
        
        if project_type == "Node.js":
            contributing_content += "```bash\n# Install dependencies\nnpm install\n\n# Run tests\nnpm test\n```\n\n"
        elif project_type == "Python":
            contributing_content += "```bash\n# Create and activate virtual environment\npython -m venv venv\nsource venv/bin/activate  # On Windows: venv\\Scripts\\activate\n\n# Install dependencies\npip install -r requirements.txt\n\n# Install development dependencies (if applicable)\npip install -r requirements-dev.txt\n```\n\n"
        elif project_type == "Rust":
            contributing_content += "```bash\n# Build the project\ncargo build\n\n# Run tests\ncargo test\n```\n\n"
        else:
            contributing_content += "Please refer to the README.md for setting up the development environment.\n\n"
        
        # Making Changes section
        contributing_content += "## Making Changes\n\n"
        
        if has_git:
            contributing_content += "1. Create a new branch for your changes\n"
            contributing_content += "```bash\ngit checkout -b feature/your-feature-name\n```\n\n"
            contributing_content += "2. Make your changes\n"
            contributing_content += "3. Add and commit your changes with a meaningful commit message\n"
            contributing_content += "```bash\ngit add .\ngit commit -m \"Add feature: brief description of changes\"\n```\n\n"
        
        # Style guidelines
        contributing_content += "## Style Guidelines\n\n"
        
        if project_type == "Node.js":
            contributing_content += "- Follow the existing code style\n"
            contributing_content += "- Run linting before submitting changes: `npm run lint`\n"
        elif project_type == "Python":
            contributing_content += "- Follow PEP 8 guidelines\n"
            contributing_content += "- Use docstrings for functions and classes\n"
            contributing_content += "- Run linting tools like flake8 or pylint before submitting changes\n"
        elif project_type == "Rust":
            contributing_content += "- Run `cargo fmt` before submitting changes\n"
            contributing_content += "- Run `cargo clippy` to check for common mistakes\n"
        else:
            contributing_content += "- Follow the existing code style in the project\n"
        
        contributing_content += "\n"
        
        # Testing section
        contributing_content += "## Testing\n\n"
        contributing_content += "- Add tests for new features\n"
        contributing_content += "- Ensure all tests pass before submitting a pull request\n"
        
        if project_type == "Node.js":
            contributing_content += "- Run tests with: `npm test`\n"
        elif project_type == "Python":
            contributing_content += "- Run tests with: `pytest` or `python -m unittest`\n"
        elif project_type == "Rust":
            contributing_content += "- Run tests with: `cargo test`\n"
        
        contributing_content += "\n"
        
        # Pull Request section
        if has_git:
            contributing_content += "## Submitting a Pull Request\n\n"
            contributing_content += "1. Push your changes to your fork\n"
            contributing_content += "```bash\ngit push origin feature/your-feature-name\n```\n\n"
            contributing_content += "2. Go to the original repository and create a pull request\n"
            contributing_content += "3. Fill in the PR template with all required information\n"
            contributing_content += "4. Wait for maintainers to review your PR\n\n"
        
        # Write the CONTRIBUTING.md file
        with open(contributing_path, 'w') as f:
            f.write(contributing_content)
        
        return f"Successfully generated CONTRIBUTING.md at {contributing_path}"
        
    except Exception as e:
        return f"Error creating CONTRIBUTING.md: {str(e)}"

# Run the server
if __name__ == "__main__":
    mcp.run()
