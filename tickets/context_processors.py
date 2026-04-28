from .models import PanelBrandSettings


DEFAULT_BRAND = {
    'brand_name': 'FRC CMS & TICKETS',
    'brand_subtitle': 'ADMIN PANEL',
    'logo_icon': '⚡',
    'logo_url': '',
}


def panel_branding(request):
    settings = PanelBrandSettings.objects.first()
    if not settings:
        return {'panel_brand': DEFAULT_BRAND}

    return {
        'panel_brand': {
            'brand_name': settings.brand_name or DEFAULT_BRAND['brand_name'],
            'brand_subtitle': settings.brand_subtitle or DEFAULT_BRAND['brand_subtitle'],
            'logo_icon': settings.logo_icon or DEFAULT_BRAND['logo_icon'],
            'logo_image': settings.logo_image.url if settings.logo_image else '',
            'logo_url': settings.logo_url or '',
        }
    }
