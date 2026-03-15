from django.contrib import admin
from .models import RSSSubscription, CachedURL

@admin.register(RSSSubscription)
class RSSSubscriptionAdmin(admin.ModelAdmin):
	list_display = ('name', 'user', 'feed_url', 'is_active', 'last_fetched_at')
	list_filter = ('is_active',)
	search_fields = ('name', 'feed_url', 'user__username')


@admin.register(CachedURL)
class CachedURLAdmin(admin.ModelAdmin):
	list_display = (
		'url',
		'title',
		'fetch_status',
		'failure_count',
		'last_http_status',
		'next_retry_at',
		'last_scraped_at',
	)
	list_filter = ('fetch_status', 'last_http_status')
	search_fields = ('url', 'title', 'site_name')
