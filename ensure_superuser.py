import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Admin1234!')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@usb.com')

user, created = User.objects.get_or_create(username=username)
user.set_password(password)
user.is_superuser = True
user.is_staff = True
user.email = email
user.save()

print(f"[OK] Superuser {'yaratildi' if created else 'yangilandi'}: {username}")
