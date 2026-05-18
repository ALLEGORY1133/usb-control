from django.db import models


class ClientPC(models.Model):
    pc_name   = models.CharField(max_length=100, unique=True, verbose_name="Kompyuter nomi")
    last_seen = models.DateTimeField(auto_now=True, verbose_name="Oxirgi faollik")

    class Meta:
        verbose_name        = "Kompyuter"
        verbose_name_plural = "Kompyuterlar"
        ordering            = ['-last_seen']

    def __str__(self):
        return self.pc_name


class USBDevice(models.Model):
    STATUS_CHOICES = [
        ('allowed', 'Ruxsat berilgan'),
        ('blocked', 'Bloklangan'),
        ('pending', 'Kutilmoqda'),
    ]
    pnp_id     = models.CharField(max_length=255, unique=True, verbose_name="PNP ID")
    caption    = models.CharField(max_length=255, verbose_name="Qurilma nomi")
    pc         = models.ForeignKey(ClientPC, on_delete=models.SET_NULL, null=True,
                                   blank=True, verbose_name="Kompyuter")
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                  default='pending', verbose_name="Holat")
    first_seen = models.DateTimeField(auto_now_add=True, verbose_name="Birinchi ulangan")
    last_seen  = models.DateTimeField(auto_now=True, verbose_name="Oxirgi ulangan")

    class Meta:
        verbose_name        = "USB Qurilma"
        verbose_name_plural = "USB Qurilmalar"
        ordering            = ['-last_seen']

    def __str__(self):
        return f"{self.caption} [{self.status}]"


class USBLog(models.Model):
    pc          = models.ForeignKey(ClientPC, on_delete=models.CASCADE, verbose_name="Kompyuter")
    usb_caption = models.CharField(max_length=255, verbose_name="Qurilma nomi")
    pnp_id      = models.CharField(max_length=255, verbose_name="PNP ID")
    action      = models.CharField(max_length=100, verbose_name="Harakat")
    timestamp   = models.DateTimeField(auto_now_add=True, verbose_name="Vaqt")

    class Meta:
        verbose_name        = "USB Log"
        verbose_name_plural = "USB Loglar"
        ordering            = ['-timestamp']

    def __str__(self):
        return f"{self.usb_caption} — {self.action} ({self.timestamp:%d.%m.%Y %H:%M})"
