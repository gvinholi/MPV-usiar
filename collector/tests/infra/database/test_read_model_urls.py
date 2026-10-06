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
