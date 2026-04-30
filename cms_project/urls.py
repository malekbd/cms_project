from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import health_views
from .metrics_exporter import metrics_prometheus, metrics_json, health_check, health_liveness, health_readiness
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('panel/', include('tickets.panel_urls')),
    path('', include('tickets.urls')),
    
    # Health check and monitoring endpoints
    path('health/', health_check, name='health_check'),
    path('health/liveness/', health_liveness, name='health_liveness'),
    path('health/readiness/', health_readiness, name='health_readiness'),
    path('metrics/', metrics_prometheus, name='metrics_prometheus'),
    path('metrics/json/', metrics_json, name='metrics_json'),
    path('status/', health_views.status, name='status'),
    path('info/', health_views.info, name='info'),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Add debug toolbar if installed
    try:
        import debug_toolbar
        urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
    except ImportError:
        pass
