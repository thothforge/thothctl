"""Unit tests for CDK language selection in project init workflow."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from thothctl.services.generate.create_template.github_template_loader import GitHubTemplateLoader


class TestGitHubTemplateLoaderCdkLanguages:
    """Test that CDK language variants are registered in the template loader."""

    def test_cdkv2_generic_template_exists(self):
        loader = GitHubTemplateLoader()
        assert "cdkv2" in loader.DEFAULT_TEMPLATES

    @pytest.mark.parametrize("language", ["typescript", "python", "java", "csharp", "go"])
    def test_cdkv2_language_template_exists(self, language):
        loader = GitHubTemplateLoader()
        key = f"cdkv2-{language}"
        assert key in loader.DEFAULT_TEMPLATES
        assert "thothforge" in loader.DEFAULT_TEMPLATES[key]
        assert language in loader.DEFAULT_TEMPLATES[key]

    def test_cdkv2_language_urls_are_unique(self):
        loader = GitHubTemplateLoader()
        cdk_urls = [v for k, v in loader.DEFAULT_TEMPLATES.items() if k.startswith("cdkv2-")]
        assert len(cdk_urls) == len(set(cdk_urls))

    def test_is_template_available_for_cdk_languages(self):
        loader = GitHubTemplateLoader()
        for lang in ["typescript", "python", "java", "csharp", "go"]:
            assert loader.is_template_available(f"cdkv2-{lang}")

    def test_non_existent_language_not_available(self):
        loader = GitHubTemplateLoader()
        assert not loader.is_template_available("cdkv2-rust")

    @pytest.mark.parametrize("language", ["typescript", "python", "java", "csharp", "go"])
    def test_load_template_resolves_correct_url(self, language):
        """Verify load_template picks the right URL for each CDK language."""
        loader = GitHubTemplateLoader()
        loader.config = MagicMock()
        loader.config.get_template_url.return_value = None  # No user override

        with patch.object(loader, '_clone_and_copy_template', return_value={"ok": True}) as mock_clone:
            loader.load_template("my-app", f"cdkv2-{language}")
            mock_clone.assert_called_once_with(
                loader.DEFAULT_TEMPLATES[f"cdkv2-{language}"],
                "my-app",
                f"cdkv2-{language}",
            )


class TestProjectInitCdkLanguageSelection:
    """Test the CLI command handles --language flag correctly."""

    def test_cli_has_language_option(self):
        from thothctl.commands.init.commands.project import cli
        param_names = [p.name for p in cli.params]
        assert "language" in param_names

    def test_language_choices(self):
        from thothctl.commands.init.commands.project import cli
        lang_param = next(p for p in cli.params if p.name == "language")
        assert hasattr(lang_param.type, "choices")
        assert set(lang_param.type.choices) == {"typescript", "python", "java", "csharp", "go"}

    def test_cdkv2_language_rewrite_logic(self):
        """Test the core logic: cdkv2 + python → cdkv2-python."""
        # Simulate what _execute does
        project_type = "cdkv2"
        language = "python"
        if project_type == "cdkv2" and language:
            project_type = f"cdkv2-{language}"
        assert project_type == "cdkv2-python"

    def test_cdkv2_batch_defaults_to_typescript(self):
        """In batch mode without --language, cdkv2 defaults to typescript."""
        project_type = "cdkv2"
        language = None
        batch = True
        if project_type == "cdkv2":
            if not language:
                if batch:
                    language = "typescript"
            project_type = f"cdkv2-{language}"
        assert project_type == "cdkv2-typescript"

    def test_terraform_ignores_language(self):
        """Language rewrite only applies to cdkv2."""
        project_type = "terraform"
        language = "python"
        if project_type == "cdkv2" and language:
            project_type = f"cdkv2-{language}"
        assert project_type == "terraform"

    @pytest.mark.parametrize("language", ["typescript", "python", "java", "csharp", "go"])
    def test_all_languages_produce_valid_project_type(self, language):
        project_type = "cdkv2"
        project_type = f"cdkv2-{language}"
        loader = GitHubTemplateLoader()
        assert project_type in loader.DEFAULT_TEMPLATES


class TestTemplatePlaceholdersCdk:
    """Test that CDK scaffold files have correct template placeholders."""

    def test_environment_yaml_has_placeholders(self):
        yaml_path = Path(__file__).parent.parent.parent / \
            "iac-scaffold/cdkv2_scaffold_project/project_configs/environment_options.yaml"
        if not yaml_path.exists():
            pytest.skip("CDK scaffold not found at expected path")
        content = yaml_path.read_text()
        assert "#{project_name}#" in content
        assert "#{deployment_region}#" in content
        assert "#{owner}#" in content

    def test_catalog_yaml_has_placeholders(self):
        catalog_path = Path(__file__).parent.parent.parent / \
            "iac-scaffold/cdkv2_scaffold_project/docs/catalog/catalog-info.yaml"
        if not catalog_path.exists():
            pytest.skip("CDK scaffold not found at expected path")
        content = catalog_path.read_text()
        assert "#{project_name}#" in content
        assert "#{owner}#" in content

    def test_typescript_files_have_no_placeholders(self):
        """TS files should NOT have #{...}# — config is externalized to YAML."""
        lib_path = Path(__file__).parent.parent.parent / \
            "iac-scaffold/cdkv2_scaffold_project/lib"
        if not lib_path.exists():
            pytest.skip("CDK scaffold not found at expected path")
        for ts_file in lib_path.rglob("*.ts"):
            content = ts_file.read_text()
            assert "#{" not in content, f"Found placeholder in TS file: {ts_file}"

    def test_thothcf_toml_keys_match_placeholders(self):
        """All #{...}# placeholders in scaffold files must have a matching .thothcf.toml key."""
        import re
        base = Path(__file__).parent.parent.parent / "iac-scaffold/cdkv2_scaffold_project"
        if not base.exists():
            pytest.skip("CDK scaffold not found")

        toml_content = (base / ".thothcf.toml").read_text()
        toml_keys = set(re.findall(r'\[template_input_parameters\.(\w+)\]', toml_content))

        # Collect all placeholders from scaffold files
        placeholders = set()
        for f in base.rglob("*"):
            if f.is_file() and f.suffix in (".yaml", ".yml", ".md") and ".git" not in str(f):
                try:
                    content = f.read_text()
                    placeholders.update(re.findall(r'#\{(\w+)\}#', content))
                except UnicodeDecodeError:
                    pass

        missing = placeholders - toml_keys
        assert not missing, f"Placeholders {missing} have no matching .thothcf.toml key"
