# Fubog Trigger - WhatsApp Message Broadcasting System

Asynchronous Django application for bulk WhatsApp messaging using UazAPI integration.

## Features

- **Asynchronous Processing**: Non-blocking message sending via Celery
- **Windows Compatible**: Uses SQL database as message broker (no Redis required)
- **Rate Limiting**: Built-in protection against WhatsApp API bans
- **Error Handling**: Comprehensive retry logic and error recovery
- **Security**: Environment-based configuration management
- **Monitoring**: Real-time task status tracking

## Architecture

- **Django 5.2.8**: Web framework
- **Celery**: Asynchronous task queue
- **django-celery-results**: SQL-based task storage (Windows compatible)
- **PostgreSQL/SQLite**: Database backend
- **UazAPI**: WhatsApp service provider

## Installation

### 1. Prerequisites

- Python 3.8+
- PostgreSQL (recommended) or SQLite
- Windows 10/11 (for Windows-specific configuration)

### 2. Setup

```bash
# Clone repository
git clone <repository-url>
cd fubog_wpp_trigger

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env

# Edit .env with your configuration
notepad .env
```

### 3. Environment Configuration

Edit `.env` file with your settings:

```env
# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DATABASE_URL=sqlite:///db.sqlite3

# UazAPI Configuration (Required)
UAZAPI_URL=https://servidoruazapidisparo.uazapi.com
UAZAPI_INSTANCE=your-instance-id-here
UAZAPI_TOKEN=your-api-token-here

# Celery Configuration (SQL-based)
CELERY_BROKER_URL=django://
CELERY_RESULT_BACKEND=django-db
```

### 4. Database Setup

```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic
```

## Running on Windows

### **CRITICAL: Windows-Specific Configuration**

Windows requires special Celery configuration to avoid process forking issues:

```bash
# Start Django development server
python manage.py runserver

# Start Celery worker (Windows specific - REQUIRED)
celery -A core worker -l info --pool=solo

# Start Celery beat scheduler (optional, for periodic tasks)
celery -A core beat -l info --pool=solo
```

### **Why `--pool=solo` is Required**

Windows doesn't support process forking like Unix systems. The `--pool=solo` flag:
- Uses threads instead of processes
- Prevents `WinError 10054` connection issues
- Ensures compatibility with Windows threading model
- Maintains task isolation without process overhead

### **Alternative Windows Setup**

For better performance on Windows, you can also use:

```bash
# Using eventlet pool (requires eventlet installation)
pip install eventlet
celery -A core worker -l info --pool=eventlet
```

## Usage

### 1. Start the Application

Open **three separate terminal windows**:

```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Celery worker
celery -A core worker -l info --pool=solo

# Terminal 3: Celery beat (optional)
celery -A core beat -l info --pool=solo
```

### 2. Access the Application

- Open browser: `http://localhost:8000`
- Login with Django admin credentials
- Connect WhatsApp via QR code
- Add contacts and send bulk messages

### 3. Monitor Tasks

- Task status is displayed in the dashboard
- Check logs for detailed information
- Use Django admin to monitor dispatch records

## Development

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific test module
python manage.py test trigger.tests

# Run with coverage (requires coverage.py)
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

### Code Structure

```
trigger/
├── models.py          # Django models (Contato, Disparo, InstanciaZap)
├── views.py           # Django views (web interface)
├── tasks.py           # Celery tasks (async processing)
├── services/
│   └── uazapi_client.py  # WhatsApp API client
├── forms.py           # Django forms
├── tests.py           # Test suite
└── celery.py          # Celery configuration
```

## Production Deployment

### Environment Variables

For production, set these environment variables:

```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgres://user:pass@host:port/dbname
UAZAPI_URL=https://your-uazapi-server.com
UAZAPI_INSTANCE=production-instance
UAZAPI_TOKEN=production-token
```

### Security Considerations

- Never commit `.env` files to version control
- Use strong `SECRET_KEY` in production
- Enable HTTPS with proper SSL certificates
- Configure firewall rules for database access
- Monitor Celery logs for errors

### Performance Tuning

- Adjust `CELERY_WORKER_CONCURRENCY` based on CPU cores
- Configure `CELERY_TASK_RATE_LIMIT` based on API limits
- Use PostgreSQL for better performance under load
- Monitor database connection pooling

## Troubleshooting

### Common Windows Issues

1. **`WinError 10054` Connection Reset**
   - Solution: Use `--pool=solo` flag
   - Alternative: Install and use `eventlet` pool

2. **Celery Worker Not Starting**
   - Check database connection in `.env`
   - Ensure Django migrations are applied
   - Verify `django-celery-results` is installed

3. **Tasks Not Processing**
   - Confirm Celery worker is running
   - Check task queue in Django admin
   - Review Celery logs for errors

### Database Issues

```bash
# Reset database (development only)
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### API Connection Issues

- Verify UazAPI credentials in `.env`
- Check network connectivity to UazAPI server
- Review API rate limits and quotas
- Monitor WhatsApp connection status

## Monitoring

### Logs

- Django logs: `logs/django.log`
- Celery logs: Console output (can be redirected to file)

### Django Admin

Access `/admin/` to monitor:
- Dispatch records (`Disparo` model)
- Contact list (`Contato` model)
- WhatsApp instances (`InstanciaZap` model)
- Celery task results (`django_celery_results`)

## API Reference

### UazApiClient Methods

- `verificar_status()`: Check WhatsApp connection
- `obter_qr_code()`: Get QR code for connection
- `enviar_texto(numero, mensagem)`: Send text message
- `desconectar_instancia()`: Disconnect WhatsApp

### Celery Tasks

- `send_bulk_messages`: Process bulk message sending
- `enviar_mensagem_broadcast`: Send individual message
- `check_connection_status`: Monitor WhatsApp status
- `cleanup_old_disparos`: Database maintenance

## License

Private project - All rights reserved.

## Support

For technical support:
1. Check the troubleshooting section
2. Review application logs
3. Verify environment configuration
4. Test with development settings first
