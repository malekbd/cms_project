import logging

from .models import PanelBrandSettings


logger = logging.getLogger(__name__)


DEFAULT_BRAND = {
    'brand_name': 'FRC CMS & TICKETS',
    'brand_subtitle': 'ADMIN PANEL',
    'logo_icon': '⚡',
    'logo_url': '',
}


def panel_branding(request):
    try:
        brand_settings = PanelBrandSettings.objects.first()
        if not brand_settings:
            return {'panel_brand': DEFAULT_BRAND}

        return {
            'panel_brand': {
                'brand_name': brand_settings.brand_name or DEFAULT_BRAND['brand_name'],
                'brand_subtitle': brand_settings.brand_subtitle or DEFAULT_BRAND['brand_subtitle'],
                'logo_icon': brand_settings.logo_icon or DEFAULT_BRAND['logo_icon'],
                'logo_image': brand_settings.logo_image.url if brand_settings.logo_image else '',
                'logo_url': brand_settings.logo_url or '',
            }
        }
    except Exception:
        logger.exception("Unable to load panel branding settings; using defaults.")
        return {'panel_brand': DEFAULT_BRAND}
