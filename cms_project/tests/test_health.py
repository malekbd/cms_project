from django.test import TestCase, Client


class HealthEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_endpoint(self):
        resp = self.client.get('/health/')
        self.assertIn(resp.status_code, (200, 206, 503))
        data = resp.json()
        self.assertIn('status', data)
        self.assertIn('timestamp', data)

    def test_liveness_endpoint(self):
        resp = self.client.get('/health/liveness/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('status'), 'alive')
        self.assertIn('timestamp', data)

    def test_readiness_endpoint(self):
        resp = self.client.get('/health/readiness/')
        self.assertIn(resp.status_code, (200, 503))
        data = resp.json()
        self.assertIn('status', data)
        self.assertIn('timestamp', data)
