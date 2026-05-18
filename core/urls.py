from django.contrib import admin
from django.urls import path
from api.views import CheckUSBView, ping

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/check-usb/', CheckUSBView.as_view()),
    path('api/ping/', ping),
]
