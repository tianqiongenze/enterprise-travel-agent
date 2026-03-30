"""Module provides service components and helpers."""

import os

from .base import ServiceRegistry
from .local_fallback_registry import LocalFallbackRegistry


def build_registry_from_env() -> ServiceRegistry:
    registry_type = os.getenv("TRAVEL_REGISTRY", "nacos-real").strip().lower()
    fail_fast = os.getenv("TRAVEL_REGISTRY_FAIL_FAST", "false").strip().lower() == "true"
    fallback = LocalFallbackRegistry()
    if registry_type == "etcd-real":
        from .real_etcd_registry import RealEtcdRegistry

        registry = RealEtcdRegistry()
        if registry.enabled:
            return registry
        if fail_fast:
            raise RuntimeError("TRAVEL_REGISTRY=etcd-real but etcd registry is not enabled")
        return fallback
    if registry_type == "nacos-real":
        from .real_nacos_registry import RealNacosRegistry

        registry = RealNacosRegistry()
        if registry.enabled:
            return registry
        if fail_fast:
            raise RuntimeError("TRAVEL_REGISTRY=nacos-real but nacos registry is not enabled")
        return fallback
    if registry_type == "etcd":
        from .etcd_registry import EtcdStyleRegistry

        return EtcdStyleRegistry()
    if registry_type == "nacos":
        from .nacos_registry import NacosStyleRegistry

        return NacosStyleRegistry()
    return fallback
