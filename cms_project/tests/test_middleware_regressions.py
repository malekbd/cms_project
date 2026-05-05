from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from cms_project.rate_limiting import RateLimiter
from cms_project.cache_utils import make_cache_key
from cms_project.security_hardening import EnhancedSecurityMiddleware


class MiddlewareRegressionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEBUG=True)
    def test_rate_limiter_handles_request_without_user(self):
        request = self.factory.get('/', REMOTE_ADDR='127.0.0.1')

        is_limited, retry_after = RateLimiter.is_rate_limited(request)

        self.assertFalse(is_limited)
        self.assertEqual(retry_after, 0)

    def test_security_headers_receives_request_context(self):
        request = self.factory.get('/api/example/')
        middleware = EnhancedSecurityMiddleware(lambda request: HttpResponse('ok'))

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_cache_key_function_accepts_django_signature(self):
        cache_key = make_cache_key('rate_limit', 'cms_cache', 1)

        self.assertTrue(cache_key.endswith('cms_cache:rate_limit:v1'))
