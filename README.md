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

## 🔐 Role-Based Access Control (RBAC)

The system enforces strict access control based on user roles. A user can have a global role and different roles across multiple clinics.

| Role | Access Level | Key Permissions |
| :--- | :--- | :--- |
| **Super Admin** | System-Wide | Manage clinics, global settings, and other super admins. |
| **Clinic Admin** | Clinic-Wide | Manage staff, view audit logs, manage billing, and clinic settings. |
| **Doctor** | Clinical | Create prescriptions, view patient history, manage own appointments. |
| **Receptionist** | Operational | Register patients, book appointments, collect payments, manage queue. |
| **Patient** | Personal | View own profile, appointments, and prescriptions (via Patient Portal). |

---

## 📡 API Endpoints Reference

All endpoints (except Auth and Clinic creation) require a `clinic_id`. This can be provided via the `X-Clinic-ID` header or is automatically extracted from the JWT token claims.

### 🔑 Authentication (`/api/v1/auth/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/register/` | Register new user account |
| `POST` | `/login/` | Obtain JWT tokens (Access/Refresh) |
| `POST` | `/logout/` | Blacklist refresh token |
| `POST` | `/token/refresh/` | Get new access token |
| `POST` | `/token/verify/` | Verify token validity |
| `POST` | `/password/change/` | Update password (Authenticated) |
| `GET` | `/me/` | Get current profile & clinics |
| `PATCH` | `/me/` | Update own profile |

### 🏥 Clinics (`/api/v1/clinics/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | List accessible clinics |
| `POST` | `/` | Create new clinic (SuperAdmin) |
| `GET` | `/{id}/` | Clinic configuration & details |
| `PUT/PATCH` | `/{id}/` | Update clinic settings |
| `DELETE` | `/{id}/` | Deactivate/Delete clinic |
| `GET` | `/{id}/stats/` | Usage & billing statistics |

### 👥 Patients (`/api/v1/patients/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | List patients (Filter/Search) |
| `POST` | `/` | Register new patient |
| `GET` | `/{id}/` | Detailed patient record |
| `PUT/PATCH` | `/{id}/` | Update demographics |
| `DELETE` | `/{id}/` | Archive patient |
| `GET` | `/{id}/history/` | Full medical history timeline |
| `POST` | `/{id}/attachments/` | Upload medical reports/docs |

### 📅 Appointments (`/api/v1/appointments/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | List all appointments |
| `POST` | `/` | Book a new slot |
| `GET` | `/queue/` | Live today's patient queue |
| `POST` | `/queue/next/` | Advance the queue (Call next) |
| `GET` | `/slots/` | Query availability by doctor/date |
| `POST` | `/{id}/cancel/` | Cancel appointment |
| `POST` | `/{id}/complete/`| Mark as finished |

### 📜 Prescriptions (`/api/v1/prescriptions/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | List clinical records |
| `POST` | `/` | Create new prescription |
| `GET` | `/{id}/` | Prescription detail |
| `GET` | `/{id}/pdf/` | Generate & Download PDF |
| `POST` | `/{id}/remedies/` | Add homeopathic remedy line |
| `GET` | `/remedies/` | Remedy Materia Medica database |

### 💳 Billing (`/api/v1/billing/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/invoices/` | List all clinic invoices |
| `POST` | `/invoices/` | Generate new invoice |
| `GET` | `/invoices/{id}/` | Invoice detail & breakdown |
| `POST` | `/invoices/{id}/pay/`| Record payment (Full/Partial) |
| `GET` | `/payments/` | Global payment history |
| `GET` | `/subscriptions/` | Available SaaS plans |

### 👨‍⚕️ Staff (`/api/v1/staff/`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | List clinic staff members |
| `POST` | `/invite/` | Invite doctor/receptionist |
| `PATCH` | `/{id}/update-role/`| Change permissions or status |
| `GET` | `/doctors/` | List available clinicians |

### 🛡️ Activity Logs & Notifications
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/activity-logs/` | Immutable audit trails (Admin only) |
| `GET` | `/notifications/` | Unread system notifications |
| `POST` | `/notifications/read-all/`| Clear all notifications |
| `GET` | `/notifications/logs/`| History of sent SMS/Emails |


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
