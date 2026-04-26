# MCU-Plus-Backend
серверная часть проекта для управления расписанием учебных занятий и предоставления данных мобильному приложению MCU Plus

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Сайт будет доступен по адресу http://127.0.0.1:8000/.
