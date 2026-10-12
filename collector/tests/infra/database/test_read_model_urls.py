import pytest
from collector.infra.database.read_model_store import public_url


@pytest.mark.parametrize('value', [None,'','file:///private/key','http://localhost/file',
    'http://127.0.0.1/file','http://10.0.0.1/file','https://files.internal/file',
    'https://user:password@example.com/file','https://example.com/file?token=secret',
    'https://example.com/file#token','http://[::1]/file','http://[bad'])
def test_unsafe_or_sensitive_urls_not_returned(value):
    assert public_url(value) is None


def test_public_reference_preserved():
    value='https://pncp.gov.br/api/pncp/v1/orgaos/123/compras/2026/1/arquivos/1'
    assert public_url(value)==value


def test_public_source_reference_with_non_sensitive_query_is_preserved():
    value = (
        "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/landing"
        "?destino=acompanhamento-compra&compra=38911405900082025"
    )
    assert public_url(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/file?access_token=secret",
        "https://example.com/file?signature=secret",
        "https://example.com/file?X-Amz-Signature=secret",
        "https://example.com/file?X-Amz-Security-Token=secret",
        " https://example.com/file",
        "https://example.com:99999/file",
        "https://example.com/file\nheader:value",
    ],
)
def test_sensitive_or_malformed_public_references_are_rejected(value):
    assert public_url(value) is None
