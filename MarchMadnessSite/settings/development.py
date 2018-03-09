from .base_settings import *

SECRET_KEY = None  # CHANGE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

DEBUG = True


# Use the debug toolbar if it is installed
try:
    import debug_toolbar

    if 'debug_toolbar' not in INSTALLED_APPS:

        INTERNAL_IPS = ('127.0.0.1',)

        MIDDLEWARE = [
            'debug_toolbar.middleware.DebugToolbarMiddleware',
        ] + MIDDLEWARE

        INSTALLED_APPS += (
            'debug_toolbar',
        )

        DEBUG_TOOLBAR_PANELS = [
            'debug_toolbar.panels.versions.VersionsPanel',
            'debug_toolbar.panels.timer.TimerPanel',
            'debug_toolbar.panels.settings.SettingsPanel',
            'debug_toolbar.panels.headers.HeadersPanel',
            'debug_toolbar.panels.request.RequestPanel',
            'debug_toolbar.panels.sql.SQLPanel',
            'debug_toolbar.panels.staticfiles.StaticFilesPanel',
            'debug_toolbar.panels.templates.TemplatesPanel',
            'debug_toolbar.panels.cache.CachePanel',
            'debug_toolbar.panels.signals.SignalsPanel',
            'debug_toolbar.panels.logging.LoggingPanel',
            'debug_toolbar.panels.redirects.RedirectsPanel',
        ]

        DEBUG_TOOLBAR_CONFIG = {
            'INTERCEPT_REDIRECTS': False,
            'JQUERY_URL': '',
        }
except ImportError:
    debug_toolbar = None
