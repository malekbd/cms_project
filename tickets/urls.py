from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/panel/', permanent=False), name='root_redirect'),
]
