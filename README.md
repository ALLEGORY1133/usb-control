# USB Nazorat Tizimi — Server

## Loyiha tuzilmasi
```
usb_server/          ← GitHub ga yuklanadigan qism (server branch)
├── core/            ← Django sozlamalari
├── api/             ← USB API va modellar
├── templates/       ← HTML shablonlar
├── static/          ← CSS, JS fayllar
├── manage.py
├── requirements.txt ← Faqat server kutubxonalari
├── Procfile         ← Render uchun
└── .gitignore

usb_agent/           ← GitHub ga yuklanmaydi! Har bir PC ga alohida beriladi
└── usb_agent.pyw    ← Windows agent
```

## GitHub ga yuklash (faqat server)
```bash
cd usb_server
git init
git add .
git commit -m "server init"
git remote add origin https://github.com/USERNAME/usb-server.git
git push -u origin main
```

## Render sozlamalari
- **Root Directory:** bo'sh (yoki `.`)
- **Build Command:** `pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput && python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@gmail.com', 'Admin1234!')"`
- **Start Command:** `gunicorn core.wsgi:application`

## Environment Variables (Render da)
```
DATABASE_URL=postgresql://...
SECRET_KEY=...
DEBUG=False
```
