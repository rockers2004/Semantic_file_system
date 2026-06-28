"""Provider registry — load models by name without if/elif chains.

Usage::

    @provider("clip", "HF_transformers")
    class HFCLIPProvider(CLIPProvider):
        ...

    @provider("ocr", "doctr")
    class DoctrOCRProvider(OCRProvider):
        ...

Then in ``ModelManager``::

    provider = ProviderRegistry.get("clip", "HF_transformers")(**kwargs)
"""

from typing import Any, Callable, Dict, Optional, Type
from semantixel.core.logging import logger


class ProviderRegistryError(Exception):
    """Raised when a requested provider is not registered or cannot be loaded."""


class ProviderRegistry:
    """Thread-safe registry of model provider implementations.

    Providers are organised by *category* (e.g. ``"clip"``, ``"ocr"``,
    ``"text"``, ``"audio"``) and *name* (e.g. ``"HF_transformers"``,
    ``"doctr"``).
    """

    _registry: Dict[str, Dict[str, Type]] = {}

    @classmethod
    def register(
        cls, category: str, name: str, force: bool = False
    ) -> Callable[[Type], Type]:
        """Decorator that registers a provider class.

        Args:
            category: Provider category (``"clip"``, ``"ocr"``, etc.).
            name: Provider name (e.g. ``"HF_transformers"``).
            force: Overwrite an existing entry if ``True``.

        Returns:
            The decorator.
        """

        def decorator(provider_cls: Type) -> Type:
            if category not in cls._registry:
                cls._registry[category] = {}
            if name in cls._registry[category] and not force:
                raise ProviderRegistryError(
                    f"Provider '{name}' already registered in category '{category}'. "
                    "Use force=True to overwrite."
                )
            cls._registry[category][name] = provider_cls
            return provider_cls

        return decorator

    @classmethod
    def get(cls, category: str, name: str, **kwargs: Any) -> Any:
        """Instantiate a registered provider.

        Args:
            category: Provider category.
            name: Provider name.
            **kwargs: Keyword arguments forwarded to the provider constructor.

        Returns:
            An instance of the registered provider class.

        Raises:
            ProviderRegistryError: If the category or name is not found.
        """
        cat_registry = cls._registry.get(category)
        if not cat_registry:
            raise ProviderRegistryError(
                f"No providers registered for category '{category}'. "
                f"Available categories: {list(cls._registry)}"
            )
        provider_cls = cat_registry.get(name)
        if not provider_cls:
            raise ProviderRegistryError(
                f"Unknown provider '{name}' for category '{category}'. "
                f"Available: {list(cat_registry)}"
            )
        logger.debug(
            "Instantiating provider %s/%s (%s)", category, name, provider_cls.__name__
        )
        return provider_cls(**kwargs)

    @classmethod
    def available(cls, category: Optional[str] = None) -> Dict[str, Any]:
        """List registered providers.

        Args:
            category: If given, return only providers in this category.

        Returns:
            A dict mapping categories to dicts of ``{name: class}``.
        """
        if category:
            return {category: cls._registry.get(category, {})}
        return dict(cls._registry)

    @classmethod
    def reset(cls) -> None:
        """Clear all registered providers (useful in tests)."""
        cls._registry.clear()


# Convenience alias
provider = ProviderRegistry.register
