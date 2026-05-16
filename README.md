# Homeopathy CMS - Backend API

A comprehensive, robust, and scalable multi-tenant REST API backend designed specifically for managing homeopathic clinics. Built with **Django** and **Django REST Framework (DRF)**, it provides advanced functionality for patient management, appointment scheduling, billing, prescriptions, and real-time notifications.

## 🌟 Key Features

* **Multi-Tenant Architecture:** Securely manage multiple clinics from a single backend instance. Data isolation is enforced via a custom `TenantMiddleware`.
* **Role-Based Access Control (RBAC):** Granular permissions for Super Admins, Clinic Admins, Doctors, and Receptionists.
* **Patient Management:** Full EHR support with visit history, medical records, and attachments.
* **Smart Appointments:** Queue management, slot booking, and real-time status updates via WebSockets.
* **Digital Prescriptions:** Generate professional PDF prescriptions with homeopathic remedy repertorisation.
* **Billing & Invoicing:** Automated invoice generation, partial payments tracking, and subscription management.
* **Audit Logging:** Immutable audit trails for all data-modifying requests, ensuring compliance and security.
* **Dockerized Environment:** One-command setup for production and development.

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Framework** | Django 4.2+, Django REST Framework 3.15+ |
| **Database** | PostgreSQL, dj-database-url |
| **Caching** | Redis, django-redis |
| **Task Queue** | Celery, django-celery-beat |
| **Authentication** | JWT (SimpleJWT) |
| **WebSockets** | Django Channels, Daphne |
| **PDF Engine** | WeasyPrint |
| **Deployment** | Docker, Nginx, Gunicorn |

## 📁 Project Structure

```text
homeopathy_cms/
├── apps/
│   ├── accounts/         # Auth, RBAC, User Profiles
│   ├── activity_logs/    # Immutable Audit Trails
│   ├── appointments/     # Scheduling & Queue Management
│   ├── billing/          # Invoices, Payments, Subscriptions
│   ├── clinics/          # Clinic Entities & Settings
│   ├── notifications/    # SMS/Email/In-app Notifications
│   ├── patients/         # Electronic Health Records (EHR)
│   ├── prescriptions/    # E-Prescriptions & PDF Logic
│   └── staff/            # Clinic Member Management
├── config/               # Settings & Root URLs
├── middleware/           # Tenant & Audit Middleware
├── utils/                # Mixins, Permissions, Helpers
└── docker-compose.yml    # Production Orchestration
```

## 🚀 Quick Start (Docker)

The fastest way to get the system running for testing:

1. **Clone & Enter:**
   ```bash
   git clone https://github.com/Mr-fuaaaadh/homeopathic_crm.git
   cd homeopathy_cms
   ```

2. **Run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

3. **Initialize Database:**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

4. **Access API:**
   - API Root: `http://localhost:8000/api/v1/`
   - Admin: `http://localhost:8000/admin/`

## 📡 API Endpoints Reference

All endpoints (except Auth and Clinic creation) require a `clinic_id`. This can be provided via the `X-Clinic-ID` header or is automatically extracted from the JWT token claims.

### 🔑 Authentication (`/api/v1/auth/`)
- `POST /login/`: Obtain access and refresh tokens. Returns user role and clinic context.
- `GET /me/`: Get current user profile and assigned clinics.
- `POST /register/`: Register a new account.

### 🏥 Clinics (`/api/v1/clinics/`)
- `GET /`: List clinics the user has access to.
- `POST /`: Create a new clinic (SuperAdmin only).

### 👥 Patients (`/api/v1/patients/`)
- `GET /`: Search and filter patients.
- `POST /`: Register a new patient.
- `GET /{id}/history/`: View patient medical history timeline.

### 📅 Appointments (`/api/v1/appointments/`)
- `GET /queue/`: View today's live patient queue.
- `POST /queue/next/`: (Receptionist/Doctor) Call the next patient in line.
- `GET /slots/`: Check available time slots for a specific doctor/date.

### 📜 Prescriptions (`/api/v1/prescriptions/`)
- `POST /`: Create a new prescription.
- `GET /{id}/pdf/`: Generate and download the PDF version of the prescription.
- `GET /remedies/`: Access the global and clinic-specific homeopathic remedy database.

### 💳 Billing (`/api/v1/billing/`)
- `GET /invoices/`: View clinic invoices.
- `POST /invoices/{id}/pay/`: Record a full or partial payment.

### 👨‍⚕️ Staff (`/api/v1/staff/`)
- `POST /invite/`: Invite a new doctor or receptionist to the clinic.
- `PATCH /{id}/update-role/`: Change a staff member's role or deactivate them.

### 🛡️ Activity Logs (`/api/v1/activity-logs/`)
- `GET /`: View audit logs (Clinic Admin only). Tracks WHO did WHAT to WHICH resource and WHEN.

## 🧪 Testing for Testers

1. **Authentication**: Use `/api/v1/auth/login/` to get a token. Include this token as `Authorization: Bearer <token>` in all subsequent requests.
2. **Tenant Isolation**: Try to access a patient from `Clinic A` while logged into `Clinic B`. The system should return a `404` or `403`.
3. **Audit Check**: Perform a sensitive action (e.g., delete a patient) and then check `/api/v1/activity-logs/` to verify the action was recorded.
4. **PDF Check**: Create a prescription and hit the `/pdf/` endpoint to verify the generated layout.

## 📜 Coding Standards
- **Formatting:** `black .`
- **Quality:** `flake8`
- **Tests:** `pytest`

---
*Proprietary Software. Developed for production-grade clinical management.*

## 📄 License

Proprietary Software. All rights reserved.
