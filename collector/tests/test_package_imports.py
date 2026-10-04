"""Garante que o pacote e as camadas arquiteturais são importáveis."""

import collector
import collector.application
import collector.domain
import collector.infra


def test_collector_package_is_importable() -> None:
    assert collector.__name__ == "collector"


def test_domain_package_is_importable() -> None:
    assert collector.domain.__name__ == "collector.domain"


def test_application_package_is_importable() -> None:
    assert collector.application.__name__ == "collector.application"


def test_infra_package_is_importable() -> None:
    assert collector.infra.__name__ == "collector.infra"
