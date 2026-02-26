# Account Management Services - Progress Report

**Date:** 25 February 2026  
**Project:** Transport for North West Application

---

## Executive Summary

The account management system is **substantially implemented** with core functionality in place. The backend provides a complete REST API with token-based authentication, while the frontend has basic integration for user login, registration, and account display. However, several areas require further development to meet production-readiness standards.

---

## Current Implementation Status

### ✅ Completed Features

#### Backend (Flask + SQLAlchemy)

| Feature | Status | Location |
|---------|--------|----------|
| User Registration | ✅ Complete | [backend/app.py](../../backend/app.py) - `/api/auth/register` |
| User Login | ✅ Complete | [backend/app.py](../../backend/app.py) - `/api/auth/login` |
| User Logout | ✅ Complete | [backend/app.py](../../backend/app.py) - `/api/auth/logout` |
| Token-based Authentication | ✅ Complete | Uses `itsdangerous.URLSafeTimedSerializer` |
| Password Hashing | ✅ Complete | Uses `werkzeug.security.generate_password_hash` |
| Get User Profile | ✅ Complete | `/api/account/me` |
| Update Profile | ✅ Complete | `/api/account/profile` (username, colorblind mode) |
| Change Password | ✅ Complete | `/api/account/password` |
| Delete Account | ✅ Complete | `/api/account` (DELETE) |
| Save Routes | ✅ Complete | `/api/account/saved-routes` (POST) |
| List Saved Routes | ✅ Complete | `/api/account/saved-routes` (GET) |
| Delete Saved Route | ✅ Complete | `/api/account/saved-routes/:id` (DELETE) |
| Notifications System | ✅ Complete | `/api/account/notifications` |
| Mark Notification Read | ✅ Complete | `/api/account/notifications/:id/read` |
| Weather Location Tracking | ✅ Complete | `/api/account/weather-locations` |
| Auth Required Decorator | ✅ Complete | `@auth_required` decorator for protected routes |

#### Database Schema

| Table | Status | Description |
|-------|--------|-------------|
| `User` | ✅ Complete | userID, email (unique), userName, password (hashed), colorblindmode |
| `Route` | ✅ Complete | routeID, routeName, routeStart, routeEnd, startTime, endTime, disruption |
| `Saves` | ✅ Complete | Many-to-many relationship (userID, routeID) |
| `Notification` | ✅ Complete | notificationID, userID, message, created_at, is_read |
| `UserWeather` | ✅ Complete | userID, location tracking |

Schema defined in: [backend/migrations/account_management_schema.sql](../../backend/migrations/account_management_schema.sql)

#### Frontend (JavaScript + HTML/CSS)

| Feature | Status | Location |
|---------|--------|----------|
| Auth State Management | ✅ Complete | [frontend/src/main.js](../../frontend/src/main.js) - `authState` object |
| Login Form | ✅ Complete | Auth modal with email/password inputs |
| Registration Form | ✅ Complete | Register form with username/email/password |
| Token Storage | ✅ Complete | `localStorage` for auth token |
| Account Modal | ✅ Complete | Display logged-in user info |
| Saved Routes Display | ✅ Complete | `renderSavedRoutes()` function |
| Notifications Display | ✅ Complete | `renderNotifications()` function |
| Logout Handler | ✅ Complete | `handleLogout()` function |
| Password Update | ✅ Complete | `handleUpdatePassword()` function |
| Account Deletion | ✅ Complete | `handleDeleteAccount()` function |
| API Request Helper | ✅ Complete | `apiRequest()` with auth headers |

#### Testing

| Test Suite | Status | Location |
|------------|--------|----------|
| Register/Login/Me Flow | ✅ Complete | [backend/tests/test_account.py](../../backend/tests/test_account.py) |
| Saved Route CRUD Flow | ✅ Complete | [backend/tests/test_account.py](../../backend/tests/test_account.py) |

---

## 🔶 Partially Implemented / In Progress

### Frontend UI Actions

| Feature | Status | Notes |
|---------|--------|-------|
| Profile Edit Controls | 🔶 Partial | Backend endpoint exists; UI controls not fully wired |
| Colorblind Mode Toggle | 🔶 Partial | Backend supports it; UI toggle needs implementation |
| Remove Saved Route Button | 🔶 Partial | Backend DELETE endpoint ready; UI button not wired |
| Mark Notification as Read | 🔶 Partial | Backend PATCH endpoint ready; UI interaction missing |

---

## ❌ Not Yet Implemented - Improvements Needed

### 1. Security Hardening (HIGH PRIORITY)

| Improvement | Current State | Recommended Action |
|-------------|---------------|-------------------|
| **Token Storage** | `localStorage` (vulnerable to XSS) | Move to `HttpOnly` cookies or implement access/refresh token rotation |
| **Rate Limiting** | Not implemented | Add rate limiting on `/api/auth/*` endpoints to prevent brute force attacks |
| **Password Policy** | Basic (8+ chars) | Implement stronger policy: uppercase, lowercase, numbers, special characters |
| **CSRF Protection** | Not implemented | Add CSRF tokens for state-changing requests |
| **Input Sanitization** | Basic | Add comprehensive input validation and sanitization |

### 2. Database & Migration Management (MEDIUM PRIORITY)

| Improvement | Current State | Recommended Action |
|-------------|---------------|-------------------|
| **Migration Tooling** | Ad-hoc `db.create_all()` | Implement Flask-Migrate/Alembic for versioned migrations |
| **Schema Versioning** | Manual SQL file | Automate schema evolution tracking |
| **Database Choice** | SQLite (development) | Use PostgreSQL/MySQL for production |

### 3. Testing Coverage (MEDIUM PRIORITY)

| Improvement | Current State | Recommended Action |
|-------------|---------------|-------------------|
| **Negative Tests** | Missing | Add tests for invalid tokens, duplicate emails, wrong passwords |
| **Security Tests** | Missing | Add tests for expired tokens, SQL injection, XSS attempts |
| **Frontend Tests** | Missing | Add automated tests for register/login/logout/delete flows |
| **Integration Tests** | Basic | Expand end-to-end testing coverage |

### 4. Frontend Enhancements (MEDIUM PRIORITY)

| Improvement | Current State | Recommended Action |
|-------------|---------------|-------------------|
| **Form Validation** | Browser defaults | Add client-side validation with user feedback |
| **Error Handling** | Basic alerts | Implement toast notifications or inline error messages |
| **Loading States** | Missing | Add spinners/disabled states during API calls |
| **Session Expiry** | Silent failure | Add graceful session expiry handling with re-login prompt |

### 5. Documentation & Operational Readiness (LOW PRIORITY)

| Improvement | Current State | Recommended Action |
|-------------|---------------|-------------------|
| **API Documentation** | Markdown docs | Consider OpenAPI/Swagger specification |
| **Runbook** | Incomplete | Add deployment, backup, and incident response procedures |
| **Environment Variables** | Documented | Ensure all secrets are externalized for production |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Auth Modal  │  │Account Modal│  │ Main App    │             │
│  │ (Login/Reg) │  │ (Profile)   │  │ (Map/Routes)│             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          │                                      │
│                   ┌──────▼──────┐                               │
│                   │ apiRequest()│ ← Bearer Token in Header      │
│                   └──────┬──────┘                               │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ Express     │ (Proxy)
                    │ server.js   │
                    └──────┬──────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                    BACKEND (Flask)                              │
│                          │                                      │
│  ┌───────────────────────▼───────────────────────────┐         │
│  │                  app.py                            │         │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │         │
│  │  │ Auth Routes │  │Account Rtes │  │ Transport │  │         │
│  │  │/api/auth/*  │  │/api/account*│  │ /api/*    │  │         │
│  │  └──────┬──────┘  └──────┬──────┘  └───────────┘  │         │
│  │         │                │                         │         │
│  │         └────────┬───────┘                         │         │
│  │                  │                                 │         │
│  │           ┌──────▼──────┐                          │         │
│  │           │@auth_required│ ← Token Validation      │         │
│  │           └──────┬──────┘                          │         │
│  │                  │                                 │         │
│  └──────────────────┼─────────────────────────────────┘         │
│                     │                                           │
│              ┌──────▼──────┐                                    │
│              │ SQLAlchemy  │                                    │
│              │   Models    │                                    │
│              └──────┬──────┘                                    │
│                     │                                           │
│              ┌──────▼──────┐                                    │
│              │   SQLite    │ ← (Use PostgreSQL for production)  │
│              │  Database   │                                    │
│              └─────────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoint Summary

### Authentication Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | ❌ | Create new account |
| POST | `/api/auth/login` | ❌ | Login and receive token |
| POST | `/api/auth/logout` | ❌ | Logout (client-side token removal) |

### Account Endpoints (Require Auth)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/account/me` | ✅ | Get current user profile |
| PATCH | `/api/account/profile` | ✅ | Update username/colorblind mode |
| PATCH | `/api/account/password` | ✅ | Change password |
| DELETE | `/api/account` | ✅ | Delete account |
| GET | `/api/account/saved-routes` | ✅ | List saved routes |
| POST | `/api/account/saved-routes` | ✅ | Save a route |
| DELETE | `/api/account/saved-routes/:id` | ✅ | Remove saved route |
| GET | `/api/account/notifications` | ✅ | Get notifications |
| PATCH | `/api/account/notifications/:id/read` | ✅ | Mark as read |
| GET | `/api/account/weather-locations` | ✅ | Get tracked weather locations |
| POST | `/api/account/weather-locations` | ✅ | Add weather location |
| DELETE | `/api/account/weather-locations/:loc` | ✅ | Remove weather location |

---

## Prioritized Action Items

### Phase 1: Critical Security (Week 1-2)
1. [ ] Implement rate limiting on authentication endpoints
2. [ ] Move token storage from `localStorage` to `HttpOnly` cookies
3. [ ] Add stronger password validation policy
4. [ ] Implement CSRF protection

### Phase 2: Database & Testing (Week 3-4)
1. [ ] Set up Flask-Migrate for database migrations
2. [ ] Add negative/security test cases
3. [ ] Add frontend integration tests
4. [ ] Migrate to PostgreSQL for production environment

### Phase 3: UI/UX Polish (Week 5-6)
1. [ ] Wire profile edit UI controls (username, colorblind mode)
2. [ ] Add saved route removal button in UI
3. [ ] Implement mark notification as read in UI
4. [ ] Add proper form validation and error feedback
5. [ ] Implement loading states and disabled buttons during API calls

### Phase 4: Documentation & Operations (Week 7)
1. [ ] Create OpenAPI/Swagger specification
2. [ ] Write production deployment runbook
3. [ ] Document environment variable requirements
4. [ ] Create database backup and recovery procedures

---

## Files Reference

| File | Purpose |
|------|---------|
| [backend/app.py](../../backend/app.py) | Main Flask application with all routes |
| [backend/services/account_management.py](../../backend/services/account_management.py) | Legacy in-memory account service (deprecated) |
| [backend/migrations/account_management_schema.sql](../../backend/migrations/account_management_schema.sql) | MySQL schema definition |
| [backend/tests/test_account.py](../../backend/tests/test_account.py) | Account management test suite |
| [frontend/src/main.js](../../frontend/src/main.js) | Frontend auth/account JavaScript |
| [frontend/src/index.html](../../frontend/src/index.html) | HTML with auth/account modals |
| [frontend/src/style.css](../../frontend/src/style.css) | Account modal styling |
| [docs/features/account-management.md](./account-management.md) | API documentation |
| [TODO.md](../../TODO.md) | Project-wide TODO list |

---

## Conclusion

The account management system has a solid foundation with **core authentication and account CRUD operations fully functional**. The primary areas requiring attention are:

1. **Security hardening** - Token storage, rate limiting, and input validation
2. **Testing expansion** - Negative cases and frontend tests
3. **UI completion** - Wiring remaining account actions to the frontend
4. **Operational readiness** - Migration tooling and production configuration

The backend API is well-structured and follows RESTful conventions. With the improvements outlined above, the system will be production-ready.
