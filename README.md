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
   git clone <repository-url>
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
   *Note: To test WebSockets locally, you might need to run via Daphne:*
   ```bash
   daphne -p 8000 config.asgi:application
   ```

8. **Start Celery Worker (in a separate terminal):**
   ```bash
   celery -A config worker -l info
   ```

## 📡 API Endpoints Reference

Here is a quick overview of the currently running REST API endpoints provided by the backend:

### Authentication (`/api/v1/auth/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/register/` | Register new user |
| `POST` | `/login/` | Obtain JWT tokens |
| `POST` | `/logout/` | Blacklist refresh token |
| `POST` | `/token/refresh/` | Refresh access token |
| `POST` | `/token/verify/` | Verify token validity |
| `POST` | `/password/change/` | Change password |
| `POST` | `/password/reset/` | Request password reset |
| `POST` | `/password/reset/confirm/` | Confirm password reset |
| `GET/PATCH` | `/me/` | Current user profile |

### Clinics (`/api/v1/clinics/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST` | `/` | List/Create clinics (SuperAdmin) |
| `GET/PUT/DELETE`| `/{id}/` | Clinic detail/update/soft-delete |
| `GET` | `/{id}/stats/` | Clinic statistics |
| `POST` | `/{id}/subscription/`| Update subscription |

### Patients (`/api/v1/patients/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST` | `/` | List/Register new patient |
| `GET/PUT/DELETE`| `/{id}/` | Patient detail/update/soft-delete |
| `GET` | `/{id}/history/` | Visit history timeline |
| `GET/POST` | `/{id}/attachments/` | List/Upload attachments |

### Appointments (`/api/v1/appointments/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST` | `/` | List/Book appointment |
| `GET/PUT` | `/{id}/` | Appointment detail/update |
| `POST` | `/{id}/reschedule/` | Reschedule appointment |
| `POST` | `/{id}/cancel/` | Cancel appointment |
| `POST` | `/{id}/complete/` | Mark complete |
| `GET` | `/queue/` | Today's queue |
| `POST` | `/queue/next/` | Call next patient |
| `GET` | `/slots/` | Available slots by doctor/date |

### Prescriptions (`/api/v1/prescriptions/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST` | `/` | List/Create prescriptions |
| `GET/PUT` | `/{id}/` | Prescription detail/update |
| `GET` | `/{id}/pdf/` | Download PDF |
| `POST/DELETE` | `/{id}/remedies/` | Add/Remove remedy |

### Staff (`/api/v1/staff/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST` | `/` | List/Add staff |
| `GET/PUT/DELETE`| `/{id}/` | Staff detail/update/deactivate |
| `GET` | `/{id}/activity/` | Activity log for staff |
| `POST` | `/{id}/roles/` | Assign roles |
| `GET` | `/doctors/` | Doctors list (for scheduling) |

### Billing (`/api/v1/billing/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST` | `/invoices/` | List/Create invoice |
| `GET` | `/invoices/{id}/` | Invoice detail |
| `POST` | `/invoices/{id}/pay/` | Record payment |
| `GET` | `/invoices/{id}/pdf/` | Download invoice PDF |
| `GET` | `/payments/` | Payment history |

### Notifications & Logs (`/api/v1/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/notifications/` | User notifications |
| `POST` | `/notifications/send/` | Send manual notification |
| `GET` | `/activity-logs/` | List logs |
| `GET` | `/activity-logs/export/` | Export as CSV |

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
