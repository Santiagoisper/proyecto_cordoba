# Railway deploy — pasos manuales (requiere `railway login`)

## Prerrequisitos
1. `railway login` en terminal
2. Crear proyecto en Railway con root directory = `cordoba/`

## Variables de entorno en Railway
```
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<generar-string-largo>
DATABASE_URL=<neon-connection-string>
ALLOWED_HOSTS=*.railway.app,<tu-dominio>.up.railway.app
CSRF_TRUSTED_ORIGINS=https://<tu-dominio>.up.railway.app,https://proyecto-cordoba.vercel.app
CELERY_TASK_ALWAYS_EAGER=True
```

## Deploy y seed
```powershell
cd cordoba
railway link
railway up
railway run python manage.py migrate --noinput
railway run python manage.py collectstatic --noinput
railway run python manage.py seed_client_demo --password "Admin123!Cordoba" --reset-passwords
```

## Post-deploy
- Copiar URL pública Railway (ej. `https://xxx.up.railway.app`)
- Vercel: `VITE_CORDOBA_APP_URL=https://xxx.up.railway.app/accounts/login/`
- Smoke: `.\scripts\smoke-e2e-production.ps1 -BaseUrl https://xxx.up.railway.app`
