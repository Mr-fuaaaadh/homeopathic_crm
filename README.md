# Homeopathy CMS - Backend API

A comprehensive, robust, and scalable multi-tenant REST API backend designed specifically for managing homeopathic clinics. Built with **Django** and **Django REST Framework (DRF)**, it provides advanced functionality for patient management, appointment scheduling, billing, prescriptions, and real-time notifications.

## 🌟 Key Features

* **Multi-Tenant Architecture:** Securely manage multiple clinics from a single backend instance using the `clinics` app.
* **Role-Based Access Control (RBAC):** Granular permissions for Super Admins, Clinic Admins, Doctors, and Receptionists via the `accounts` and `staff` modules.
* **Patient Management:** Comprehensive electronic health records (EHR), tracking, and activity logging.
* **Smart Appointments:** Queue management, scheduling, and conflict resolution using the `appointments` module.
* **Digital Prescriptions:** Generate PDF prescriptions seamlessly using `weasyprint` and `reportlab`.
* **Billing & Invoicing:** Integrated billing system with automated invoice generation.
* **Real-time Capabilities:** WebSockets support via `Django Channels` and `Daphne` for real-time queue updates and notifications.
* **Asynchronous Tasks:** Celery and Redis integration for sending SMS (Twilio), emails (SendGrid), and Push Notifications (Firebase) in the background.
* **Security First:** Rate limiting, field-level encryption (`django-pgcrypto`), and brute-force protection (`django-axes`).

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Framework** | Django 4.2.13, Django REST Framework 3.15.1 |
| **Database** | PostgreSQL (`psycopg2`) |
| **Caching & Message Broker**| Redis, Celery, Django Celery Beat |
| **Authentication** | JWT (`djangorestframework-simplejwt`) |
| **Storage** | AWS S3 (`django-storages`, `boto3`) |
| **WebSockets** | Django Channels, Daphne |
| **Logging & Monitoring** | Structlog, Sentry SDK, Django Silk |

## 📁 Project Structure

The project follows a modular, app-based architecture:

```text
homeopathy_cms/
├── apps/
│   ├── accounts/         # User models, RBAC, and auth logic
│   ├── activity_logs/    # Audit trails and system logging
│   ├── appointments/     # Scheduling and queue management
│   ├── billing/          # Invoices and payment tracking
│   ├── clinics/          # Multi-tenant clinic entities and settings
│   ├── core/             # Shared mixins, abstract models, and base utils
│   ├── notifications/    # SMS, Email, and Push notification handling
│   ├── patients/         # Patient records and histories
│   ├── prescriptions/    # E-prescriptions and PDF generation
│   └── staff/            # Clinic staff profiles and permissions
├── config/               # Main Django settings and root URL routing
├── middleware/           # Custom request/response middleware
├── tasks/                # Global or shared asynchronous Celery tasks
├── tests/                # Pytest suites for the application
├── utils/                # Helper functions, formatters, and custom permissions
└── websockets/           # ASGI routing and WebSocket consumers
```

## 🚀 Getting Started

### Prerequisites

Ensure you have the following installed on your local machine:
* **Python** 3.10+
* **PostgreSQL** 14+
* **Redis** (running on default port 6379)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Mr-fuaaaadh/homeopathic_crm.git
   cd homeopathy_cms
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory. Use the `python-decouple` standard for configurations:
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   DATABASE_URL=postgres://user:password@localhost:5432/homeopathy_db
   REDIS_URL=redis://127.0.0.1:6379/1
   ```

5. **Run Migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Create a Superuser:**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the Development Server:**
   ```bash
   python manage.py runserver
   ```

8. **Start Celery Worker (in a separate terminal):**
   ```bash
   celery -A config worker -l info
   ```

## 📡 API Endpoints Reference (Active)

The full list of endpoints and their configurations can be found in [config/urls.py](config/urls.py).

### Authentication (`/api/v1/auth/`)
Source: [apps/accounts/urls.py](apps/accounts/urls.py)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/register/` | Register new user |
| `POST` | `/login/` | Obtain JWT tokens |
| `POST` | `/logout/` | Blacklist refresh token |
| `POST` | `/token/refresh/` | Refresh access token |
| `POST` | `/token/verify/` | Verify token validity (defined in root urls) |
| `GET` | `/me/` | Current user profile |
| `POST` | `/password/change/` | Change password |
| `GET` | `/sessions/` | List active sessions |

### Clinics (`/api/v1/clinics/`)
Source: [apps/clinics/urls.py](apps/clinics/urls.py)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | List clinics |
| `POST` | `/` | Create clinic (SuperAdmin only) |
| `GET` | `/{id}/` | Get clinic detail |
| `PUT/PATCH` | `/{id}/` | Update clinic |
| `DELETE` | `/{id}/` | Soft-delete clinic |
| `GET` | `/{id}/stats/` | Clinic usage statistics |
| `POST` | `/{id}/subscription/` | Update clinic subscription |

### System & Admin
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/admin/` | Django Admin Dashboard |
| `GET` | `/silk/` | Silk Profiling (Development only) |

> [!NOTE]
> Modules for Patients, Appointments, Prescriptions, Staff, Billing, Notifications, and Activity Logs are currently initialized with empty routes and are under active development.

## 🧪 Testing

The project uses `pytest`. To run the test suite:

```bash
pytest
```
To generate a coverage report:
```bash
pytest --cov=apps --cov-report=html
```

## 📜 Coding Standards

* **Formatting:** `black` is used for code formatting.
* **Linting:** `flake8` is used to enforce PEP-8 standards.
* Ensure all code is run through `black .` and `flake8` before committing.

## 📄 License

Proprietary Software. All rights reserved.
