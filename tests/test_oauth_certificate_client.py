import httpx
import pytest
import respx

from soar_sdk.auth.client import CertificateOAuthClient, OAuthClientError
from soar_sdk.auth.models import CertificateCredentials, OAuthConfig

RSA_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAvK/ZhjoDqbSxOimg6gPoPMotudDwmKAKi8W8dKfeYLQOLj0U
jsqDzux2ISQtaPLGEIYmFWN6N9ZdPwyURkialAEbRqeBczBbMT+xKRMBkE8TxZ8P
pQ6xtz7fh0Xr3e0TCQ+r0pVMK+JBq6uNVMbw0foAArDGKE+swO30Ahc6vbMoEszF
hk84jNXiZZVVeCn40uDHFqrgxYwLNmCuDTboRUaO+6fgvhUnhXwG+cGxi5uQ7/D3
N83gskQLhRGqNW0oR87x9s+xgnjGYjY3c+dAQfiJH6Rj/rz1RSth1n/s6SDNjwOw
ovgwHuCXsANfZVNAi04PwPpoesRHPRcfBoRgNQIDAQABAoIBABoA0wW+R4RzACyf
kYtGlBISm9gcjRe/kIyAKO9bthgWIFErfkKKcr1I1aPOGEr7ECQ1VJjEf5Kj4nBe
s6128oScnW1whrTA8IRaPnhGZAQG/dbRi6an3oJ+MfByyKVqN2IbjIamKBvxH7NA
nmbVTtllLmywf3KNPmXNNUA3gtMjGbnyPfx6pZrOlWWa3pgJADqPs5/yXR8wAY6z
dSK0AtsLEI9DnQLQ5Nax+93VK2IveZZVZa2ptkgAKQpAUT1rSXF+MlygFZ+rJIVq
dy49sRWWitflZGIN8lH9uwe1UTPTndxoQE81P1PvXXK3NsYZybnkaUDbnP4BAEPX
us0ccjECgYEA3J3WyjF8ZAN5mD+jEKe5hNKQ9rzftjiVi4+xuznQi0rd4AFWRss3
llG7Ag0UB1HRXzXReOYEYUoXCNGLkye7JAo4Dwf7QYUQRB8AlxR70NHn1Jshz5m7
0fQ+Rq4b/IJ8OkB+FByaKmvrHbsT+OrdEIlfvQMd0cnxv8nkA6DN31ECgYEA2vMH
4hk37riXWLuyXFCA/7Hw+3ONTXDypqlP2bcSj6gQPvOC3QGvbNVtvdIRqkW6Epw6
Jqtt9frcKffJ0cI/r5/c2920R9xzRGudaCyLhOL2hh6XRwI1JYAapd7DTncLloe9
NcNiWdH59xhh5BPwIymS6IGQCNZr5oAeJjjqIaUCgYEAu1xpD+qbA61X1Q8mg3yO
N9lEN+gL7gt8Jbxxatoc3E9Gw3kfNpxbpxPeSE2nFthLghqIva5LRfzQNzMO4Hi7
nE35cfqLTged2tyhea1xwdSimJLvUgnz0sklIo23QunmaupeqOHpo+FnGibJPXrp
J6QjZLiC2Koy33isZtBoRyECgYBX10shXca/4pTtx5f+S1oFu6kX6LsXB6qCTMk5
aqZqth2Wc/HboxJzUolNr5rgukq1rrHx07MxDa0ItV3l5s3QMw3Ts/XhIsOn/pjP
M5fh/4CyPFGq7mrOGcAXLfEjaMVgZiL2D+ZEbOahSMn1TD56jPJgj6JuuT/e4SW3
Zfwg9QKBgBVy302P6xLte2BLcE0pFvfpLChF4fOwew3jLdbJL9wAmUP4rtXrmimB
OKQ62HFoJ6gYlT1h6Y8shWkQgnkO6FhYk558e5LidigUcVCZSjz0wbbWG3rnvycS
6mNMYuTjvb669Ia7pDAwRoavRfoV2aTbPXLfeHfBvC5s8ieD/5os
-----END RSA PRIVATE KEY-----"""


@pytest.fixture
def mock_auth_state():
    class MockAuthState:
        def __init__(self):
            self._data = {}

        def get_all(self, *, force_reload=False):
            return self._data

        def put_all(self, data):
            self._data = dict(data)

    return MockAuthState()


@pytest.fixture
def oauth_config():
    return OAuthConfig(
        client_id="test_client_id",
        token_endpoint="https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
        scope=["https://graph.microsoft.com/.default"],
    )


@pytest.fixture
def certificate_credentials():
    return CertificateCredentials(
        certificate_thumbprint="abc123thumbprint",
        private_key=RSA_PRIVATE_KEY,
        tenant_id="test-tenant-id",
    )


@pytest.fixture
def certificate_client(oauth_config, mock_auth_state, certificate_credentials):
    return CertificateOAuthClient(
        oauth_config, mock_auth_state, certificate_credentials
    )


class TestCertificateOAuthClientInit:
    def test_client_initialization(
        self, oauth_config, mock_auth_state, certificate_credentials
    ):
        client = CertificateOAuthClient(
            oauth_config, mock_auth_state, certificate_credentials
        )
        assert client._certificate == certificate_credentials
        assert client.config == oauth_config


class TestFetchTokenWithCertificate:
    @respx.mock
    def test_fetch_token_success(self, certificate_client):
        route = respx.post(
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "certificate_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )

        token = certificate_client.fetch_token_with_certificate()

        assert token.access_token == "certificate_token"
        assert token.expires_in == 3600

        request = route.calls.last.request
        content = request.content.decode()
        assert "client_assertion=" in content
        assert "client_assertion_type=" in content
        assert (
            "urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer"
            in content
        )

    @respx.mock
    def test_fetch_token_without_scope(self, mock_auth_state, certificate_credentials):
        config = OAuthConfig(
            client_id="test_client_id",
            token_endpoint="https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
        )
        client = CertificateOAuthClient(
            config, mock_auth_state, certificate_credentials
        )

        route = respx.post(
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        client.fetch_token_with_certificate()

        request = route.calls.last.request
        assert b"scope=" not in request.content

    @respx.mock
    def test_fetch_token_without_extra_params(self, certificate_client):
        route = respx.post(
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        certificate_client.fetch_token_with_certificate()
        assert route.calls.last is not None

    @respx.mock
    def test_fetch_token_includes_scope(self, certificate_client):
        route = respx.post(
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        certificate_client.fetch_token_with_certificate()

        request = route.calls.last.request
        assert b"scope=" in request.content

    @respx.mock
    def test_fetch_token_with_extra_params(self, certificate_client):
        route = respx.post(
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "token", "expires_in": 3600},
            )
        )

        certificate_client.fetch_token_with_certificate(
            extra_params={"resource": "https://api.example.com"}
        )

        request = route.calls.last.request
        assert b"resource=" in request.content

    @respx.mock
    def test_fetch_token_stores_token(self, certificate_client, mock_auth_state):
        respx.post("https://login.microsoftonline.com/tenant/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "stored_token", "expires_in": 3600},
            )
        )

        certificate_client.fetch_token_with_certificate()

        state_data = mock_auth_state.get_all()
        assert "oauth" in state_data
        assert state_data["oauth"]["token"]["access_token"] == "stored_token"

    @respx.mock
    def test_fetch_token_http_error(self, certificate_client):
        respx.post("https://login.microsoftonline.com/tenant/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                401,
                json={
                    "error": "invalid_client",
                    "error_description": "Certificate validation failed",
                },
            )
        )

        with pytest.raises(OAuthClientError) as exc_info:
            certificate_client.fetch_token_with_certificate()
        assert "Certificate validation failed" in str(exc_info.value)

    @respx.mock
    def test_fetch_token_network_error(self, certificate_client):
        respx.post("https://login.microsoftonline.com/tenant/oauth2/v2.0/token").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(OAuthClientError) as exc_info:
            certificate_client.fetch_token_with_certificate()
        assert "failed" in str(exc_info.value)


class TestJWTAssertion:
    @respx.mock
    def test_jwt_contains_required_claims(self, certificate_client):
        import jwt

        captured_assertion = None

        def capture_request(request):
            nonlocal captured_assertion
            content = request.content.decode()
            for param in content.split("&"):
                if param.startswith("client_assertion="):
                    captured_assertion = param.split("=", 1)[1]
                    from urllib.parse import unquote

                    captured_assertion = unquote(captured_assertion)
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 3600}
            )

        respx.post("https://login.microsoftonline.com/tenant/oauth2/v2.0/token").mock(
            side_effect=capture_request
        )

        certificate_client.fetch_token_with_certificate()

        assert captured_assertion is not None

        decoded = jwt.decode(
            captured_assertion,
            options={"verify_signature": False},
        )

        assert decoded["iss"] == "test_client_id"
        assert decoded["sub"] == "test_client_id"
        assert (
            decoded["aud"]
            == "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
        )
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded

    @respx.mock
    def test_jwt_header_contains_thumbprint(self, certificate_client):
        import jwt

        captured_assertion = None

        def capture_request(request):
            nonlocal captured_assertion
            content = request.content.decode()
            for param in content.split("&"):
                if param.startswith("client_assertion="):
                    captured_assertion = param.split("=", 1)[1]
                    from urllib.parse import unquote

                    captured_assertion = unquote(captured_assertion)
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 3600}
            )

        respx.post("https://login.microsoftonline.com/tenant/oauth2/v2.0/token").mock(
            side_effect=capture_request
        )

        certificate_client.fetch_token_with_certificate()

        headers = jwt.get_unverified_header(captured_assertion)

        assert headers["alg"] == "RS256"
        assert headers["typ"] == "JWT"
        assert headers["x5t"] == "abc123thumbprint"
