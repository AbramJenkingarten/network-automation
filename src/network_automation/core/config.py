"""Configuration management and template rendering."""

from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment, FileSystemLoader, Template, TemplateError
from pydantic import BaseModel, Field

from ..exceptions import TemplateError as AutomationTemplateError


class TemplateConfig(BaseModel):
    """Template configuration."""
    template_dirs: list[str] = Field(default_factory=lambda: ["templates", "configs"])
    auto_reload: bool = False
    cache_size: int = 50


class TemplateManager:
    """Manages Jinja2 templates for configuration generation."""

    def __init__(self, config: TemplateConfig | None = None):
        self.config = config or TemplateConfig()
        self._env: Environment | None = None
        self._templates: dict[str, Template] = {}

    def _get_env(self) -> Environment:
        """Get or create Jinja2 environment."""
        if self._env is None:
            loaders = []
            for template_dir in self.config.template_dirs:
                path = Path(template_dir)
                if path.exists():
                    loaders.append(FileSystemLoader(str(path)))

            # Always add a dict loader for inline templates
            if loaders:
                from jinja2 import ChoiceLoader
                self._env = Environment(
                    loader=ChoiceLoader(loaders),
                    auto_reload=self.config.auto_reload,
                    cache_size=self.config.cache_size,
                    trim_blocks=True,
                    lstrip_blocks=True,
                )
            else:
                self._env = Environment(
                    loader=BaseLoader(),
                    auto_reload=self.config.auto_reload,
                    cache_size=self.config.cache_size,
                    trim_blocks=True,
                    lstrip_blocks=True,
                )

            # Add custom filters
            self._env.filters["to_json"] = lambda x: __import__("json").dumps(x, indent=2)
            self._env.filters["to_yaml"] = lambda x: __import__("yaml").dump(x, default_flow_style=False)
            self._env.filters["cidr_to_netmask"] = self._cidr_to_netmask
            self._env.filters["ip_network"] = self._ip_network

        return self._env

    def _cidr_to_netmask(self, cidr: str | int) -> str:
        """Convert CIDR to netmask."""
        if isinstance(cidr, str) and "/" in cidr:
            cidr = int(cidr.split("/")[1])
        cidr = int(cidr)
        mask = (0xffffffff << (32 - cidr)) & 0xffffffff
        return ".".join(str((mask >> (8 * i)) & 0xff) for i in [3, 2, 1, 0])

    def _ip_network(self, ip_cidr: str) -> str:
        """Get network address from IP/CIDR."""
        import ipaddress
        return str(ipaddress.ip_network(ip_cidr, strict=False).network_address)

    def load_template(self, name: str, content: str | None = None) -> Template:
        """Load template by name or from content."""
        cache_key = f"inline:{name}" if content else name

        if cache_key in self._templates:
            return self._templates[cache_key]

        env = self._get_env()

        if content:
            template = env.from_string(content)
        else:
            try:
                template = env.get_template(name)
            except TemplateError as e:
                raise AutomationTemplateError(f"Template '{name}' not found: {e}") from e

        self._templates[cache_key] = template
        return template

    def render(self, template_name: str, context: dict[str, Any], content: str | None = None) -> str:
        """Render template with context."""
        try:
            template = self.load_template(template_name, content)
            return template.render(**context)
        except TemplateError as e:
            raise AutomationTemplateError(f"Template rendering failed: {e}") from e
        except Exception as e:
            raise AutomationTemplateError(f"Unexpected error rendering template: {e}") from e

    def render_to_file(self, template_name: str, context: dict[str, Any], output_path: str, content: str | None = None) -> None:
        """Render template and write to file."""
        rendered = self.render(template_name, context, content)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(rendered)

    def validate_template(self, template_name: str, content: str | None = None) -> list[str]:
        """Validate template syntax, return list of errors."""
        try:
            self.load_template(template_name, content)
            return []
        except Exception as e:
            return [str(e)]


class ConfigBuilder:
    """Build configurations from templates and device data."""

    def __init__(self, template_manager: TemplateManager | None = None):
        self.template_manager = template_manager or TemplateManager()

    def build_from_template(
        self,
        template_name: str,
        device_data: dict[str, Any],
        extra_context: dict[str, Any] | None = None
    ) -> str:
        """Build configuration from template and device data."""
        context = {
            "device": device_data,
            **(extra_context or {}),
        }
        return self.template_manager.render(template_name, context)

    def build_from_inline_template(
        self,
        template_content: str,
        device_data: dict[str, Any],
        extra_context: dict[str, Any] | None = None
    ) -> str:
        """Build configuration from inline template string."""
        context = {
            "device": device_data,
            **(extra_context or {}),
        }
        return self.template_manager.render("inline", context, content=template_content)

    def build_multiple(
        self,
        template_names: list[str],
        device_data: dict[str, Any],
        extra_context: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """Build multiple configurations from templates."""
        results = {}
        for name in template_names:
            results[name] = self.build_from_template(name, device_data, extra_context)
        return results
