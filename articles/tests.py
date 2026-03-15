from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Article


@override_settings(CELERY_TASK_ALWAYS_EAGER=False)
class QuickSaveApiTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='tester', password='pass1234')
		self.client.force_authenticate(user=self.user)
		self.url = '/api/articles/quick_save/'

	@patch('articles.views.fetch_article_metadata.delay', return_value=None)
	def test_quick_save_accepts_url_field(self, _mock_delay):
		response = self.client.post(self.url, {'url': 'https://example.com/a'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(Article.objects.filter(user=self.user).count(), 1)

	@patch('articles.views.fetch_article_metadata.delay', return_value=None)
	def test_quick_save_accepts_url_input_field(self, _mock_delay):
		response = self.client.post(self.url, {'url_input': 'https://example.com/b'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(Article.objects.filter(user=self.user).count(), 1)

	def test_quick_save_without_url_returns_400(self):
		response = self.client.post(self.url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('hint', response.data)
