from django.contrib import admin
from .models import USBDevice, ClientPC, USBLog


@admin.register(ClientPC)
class ClientPCAdmin(admin.ModelAdmin):
    list_display  = ('pc_name', 'last_seen')
    search_fields = ('pc_name',)
    readonly_fields = ('last_seen',)


@admin.register(USBDevice)
class USBDeviceAdmin(admin.ModelAdmin):
    list_display   = ('caption', 'pc', 'status', 'first_seen', 'last_seen')
    list_filter    = ('status', 'pc')
    search_fields  = ('caption', 'pnp_id')
    readonly_fields = ('pnp_id', 'first_seen', 'last_seen')

    actions = ['make_allowed', 'make_blocked', 'make_pending']

    def make_allowed(self, request, queryset):
        queryset.update(status='allowed')
    make_allowed.short_description = "✅ Ruxsat berish"

    def make_blocked(self, request, queryset):
        queryset.update(status='blocked')
    make_blocked.short_description = "🚫 Bloklash"

    def make_pending(self, request, queryset):
        queryset.update(status='pending')
    make_pending.short_description = "⏳ Kutishga o'tkazish"


@admin.register(USBLog)
class USBLogAdmin(admin.ModelAdmin):
    list_display  = ('usb_caption', 'pc', 'action', 'timestamp')
    list_filter   = ('pc',)
    search_fields = ('usb_caption', 'pnp_id')
    readonly_fields = ('pc', 'usb_caption', 'pnp_id', 'action', 'timestamp')
