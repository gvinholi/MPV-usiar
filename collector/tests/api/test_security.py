import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWKSetError

from collector.api.security import (
    AuthenticationConfigurationError,
    AuthenticationError,
    AuthenticationUnavailableError,
    OidcJwtAuthenticator,
)

ISSUER = "https://issuer.test.example"
AUDIENCE = "mpv-api"
NOW = datetime.now(timezone.utc)


class SigningKey:
    def __init__(self, key, algorithm_name="RS256"):
        self.key = key
        self.algorithm_name = algorithm_name


class Keys:
    def __init__(self, key=None, error=None, algorithm_name="RS256"):
        self.key = key; self.error = error; self.algorithm_name = algorithm_name
    def get_signing_key_from_jwt(self, _token):
        if self.error: raise self.error
        return SigningKey(self.key, self.algorithm_name)


@pytest.fixture(scope="module")
def rsa_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def authenticator(public_key):
    value = OidcJwtAuthenticator(issuer=ISSUER, audience=AUDIENCE,
                                 jwks_url="https://issuer.test.example/jwks", algorithms=("RS256",))
    value._jwks = Keys(public_key)
    return value


def token(private_key, *, kid="test-key", **overrides):
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "user-123", "name": "Ana Revisora",
              "scope": "openid reviews:write", "exp": NOW + timedelta(minutes=5), "nbf": NOW - timedelta(seconds=1)}
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def jwk(public_key, kid):
    value = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    value.update(kid=kid, use="sig", alg="RS256")
    return value


def test_valid_asymmetric_token_builds_principal(rsa_keys):
    private, public = rsa_keys
    principal = authenticator(public).authenticate(token(private))
    assert principal.issuer == ISSUER and principal.subject == "user-123"
    assert principal.display_name == "Ana Revisora"
    assert principal.permissions == frozenset({"openid", "reviews:write"})
    assert principal.reviewer_id == f"oidc:{len(ISSUER)}:{ISSUER}user-123"


@pytest.mark.parametrize("overrides", [
    {"exp": NOW - timedelta(seconds=1)}, {"iss": "https://wrong.example"},
    {"aud": "wrong-api"}, {"nbf": NOW + timedelta(minutes=5)},
    {"sub": ""}, {"scope": ["reviews:write"]},
])
def test_invalid_claims_are_rejected(rsa_keys, overrides):
    private, public = rsa_keys
    with pytest.raises(AuthenticationError): authenticator(public).authenticate(token(private, **overrides))


def test_missing_subject_is_rejected(rsa_keys):
    private, public = rsa_keys
    claims = {"iss": ISSUER, "aud": AUDIENCE, "exp": NOW + timedelta(minutes=5)}
    value = jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test-key"})
    with pytest.raises(AuthenticationError): authenticator(public).authenticate(value)


def test_wrong_signature_is_rejected(rsa_keys):
    _private, public = rsa_keys
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthenticationError): authenticator(public).authenticate(token(other))


def test_algorithm_not_in_server_allowlist_is_rejected(rsa_keys):
    private, public = rsa_keys
    value = jwt.encode({"iss":ISSUER,"aud":AUDIENCE,"sub":"x","exp":NOW+timedelta(minutes=5)},
                       private, algorithm="RS512", headers={"kid":"test-key"})
    with pytest.raises(AuthenticationError): authenticator(public).authenticate(value)


def test_token_algorithm_must_match_selected_jwk_algorithm(rsa_keys):
    private, public = rsa_keys
    value = OidcJwtAuthenticator(
        issuer=ISSUER, audience=AUDIENCE,
        jwks_url="https://issuer.test.example/jwks", algorithms=("RS256",),
    )
    selected = jwk(public, "test-key")
    selected["alg"] = "RS512"
    value._jwks.fetch_data = lambda: {"keys": [selected]}
    with pytest.raises(AuthenticationError, match="algorithms differ"):
        value.authenticate(token(private))


@pytest.mark.parametrize("algorithm", [("HS256",), ("none",), ()])
def test_symmetric_unsigned_or_empty_server_configuration_is_rejected(algorithm):
    with pytest.raises(AuthenticationUnavailableError):
        OidcJwtAuthenticator(issuer=ISSUER, audience=AUDIENCE,
                             jwks_url="https://issuer.test.example/jwks", algorithms=algorithm)


@pytest.mark.parametrize("url", [
    "", "not-a-url", "http://issuer.test.example/jwks",
    "http://localhost/jwks", "ftp://issuer.test.example/jwks", "https://",
    " https://issuer.test.example/jwks",
    "https://user:password@issuer.test.example/jwks", "https://issuer.test.example/jwks#fragment",
    "https://issuer.test.example:invalid/jwks",
])
def test_jwks_url_requires_valid_credential_free_https(url):
    with pytest.raises(AuthenticationConfigurationError):
        OidcJwtAuthenticator(issuer=ISSUER, audience=AUDIENCE, jwks_url=url)


def test_jwks_url_comes_only_from_configuration():
    configured = "https://issuer.test.example/keys"
    value = OidcJwtAuthenticator(issuer=ISSUER, audience=AUDIENCE, jwks_url=configured)
    assert value._jwks.uri == configured


@pytest.mark.parametrize("seconds", [0, 3601, True])
def test_jwks_cache_ttl_is_bounded(seconds):
    with pytest.raises(AuthenticationConfigurationError):
        OidcJwtAuthenticator(
            issuer=ISSUER, audience=AUDIENCE,
            jwks_url="https://issuer.test.example/jwks", cache_seconds=seconds,
        )


def test_jwks_connection_failure_fails_closed(rsa_keys):
    private, public = rsa_keys
    value = authenticator(public)
    value._jwks = Keys(error=PyJWKClientConnectionError("synthetic unavailable"))
    with pytest.raises(AuthenticationUnavailableError): value.authenticate(token(private))


def test_invalid_jwks_is_service_unavailable(rsa_keys):
    private, public = rsa_keys
    value = authenticator(public)
    value._jwks = Keys(error=PyJWKSetError("synthetic invalid JWKS"))
    with pytest.raises(AuthenticationUnavailableError):
        value.authenticate(token(private))


def test_unknown_kid_is_invalid_credential(rsa_keys):
    private, public = rsa_keys
    value = authenticator(public)
    value._jwks = Keys(error=PyJWKClientError('Unable to find a signing key that matches: "unknown"'))
    with pytest.raises(AuthenticationError):
        value.authenticate(token(private))


def test_unusable_jwks_is_service_unavailable(rsa_keys):
    private, public = rsa_keys
    value = authenticator(public)
    value._jwks = Keys(error=PyJWKClientError("The JWKS endpoint did not contain any signing keys"))
    with pytest.raises(AuthenticationUnavailableError):
        value.authenticate(token(private))


def test_unexpected_authenticator_failure_is_not_reclassified(rsa_keys):
    private, public = rsa_keys
    value = authenticator(public)
    value._jwks = Keys(error=RuntimeError("synthetic programming failure"))
    with pytest.raises(RuntimeError, match="programming failure"):
        value.authenticate(token(private))


def test_jwks_set_ttl_bounds_removed_key_without_promising_immediate_revocation(rsa_keys):
    old_private, old_public = rsa_keys
    new_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    current = {"value": {"keys": [jwk(old_public, "old-key")]}}
    value = OidcJwtAuthenticator(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://issuer.test.example/jwks",
        algorithms=("RS256",),
        cache_seconds=300,
    )
    value._jwks.fetch_data = lambda: current["value"]
    old_token = token(old_private, kid="old-key")
    new_token = token(new_private, kid="new-key")

    assert value.authenticate(old_token).subject == "user-123"
    assert not hasattr(value._jwks.get_signing_key, "cache_info")
    current["value"] = {"keys": [jwk(new_private.public_key(), "new-key")]}

    # A valid set cache can still verify the old key: revocation is not instantaneous.
    assert value.authenticate(old_token).subject == "user-123"
    value._jwks.jwk_set_cache.is_expired = lambda: True
    with pytest.raises(AuthenticationError):
        value.authenticate(old_token)
    assert value.authenticate(new_token).subject == "user-123"


def test_unknown_kid_refreshes_the_configured_jwks_after_cooldown(rsa_keys):
    old_private, old_public = rsa_keys
    new_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    current = {"value": {"keys": [jwk(old_public, "old-key")]}}
    value = OidcJwtAuthenticator(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://issuer.test.example/jwks",
        cache_seconds=300,
    )
    value._jwks.fetch_data = lambda: current["value"]
    assert value.authenticate(token(old_private, kid="old-key")).subject == "user-123"

    current["value"] = {"keys": [jwk(new_private.public_key(), "new-key")]}
    value._jwks._last_successful_fetch = None  # represents the end of the library cooldown
    assert value.authenticate(token(new_private, kid="new-key")).subject == "user-123"


def test_identity_over_application_limit_is_rejected(rsa_keys):
    private, public = rsa_keys
    with pytest.raises(AuthenticationError): authenticator(public).authenticate(token(private, sub="x" * 200))
