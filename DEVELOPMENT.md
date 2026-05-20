# Development Guide

## Project Overview

This is a full-stack Vehicle Maintenance Tracker application:
- **Backend:** FastAPI (Python) + PostgreSQL
- **Frontend:** React + TypeScript + Tailwind CSS
- **Deployment:** Docker Compose (ready for Proxmox)

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Or: Python 3.11+, Node.js 18+, PostgreSQL 15+

### With Docker (Recommended)

```bash
# Clone/setup project
cd vehicle-tracker

# Copy and configure environment
cp .env.example .env

# Edit .env with your settings
nano .env

# Start all services
docker-compose up -d

# Initialize database (first time only)
docker-compose exec api python -m alembic upgrade head

# Access:
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env in backend/
DATABASE_URL=postgresql://localhost/vehicle_tracker
JWT_SECRET_KEY=your-secret-key

# Run
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
vehicle-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app
│   │   ├── config.py               # Configuration
│   │   ├── database.py             # DB setup
│   │   ├── models.py               # SQLAlchemy models
│   │   ├── schemas.py              # Pydantic schemas
│   │   ├── auth.py                 # JWT utils
│   │   ├── routes/                 # API endpoints
│   │   │   ├── auth.py             # Auth endpoints
│   │   │   ├── vehicles.py         # Vehicle CRUD + VIN decode
│   │   │   ├── fuel.py             # Fuel entries
│   │   │   ├── maintenance.py      # Maintenance entries + reminders
│   │   │   ├── expenses.py         # Expense tracking
│   │   │   └── documents.py        # Document storage
│   │   └── services/               # Business logic
│   │       ├── vin_decoder.py      # NHTSA VIN API
│   │       └── ocr.py              # Phase 2 - OCR service
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/             # React components (build out)
│   │   ├── pages/                  # Page components
│   │   │   ├── LoginPage.tsx       # Auth page
│   │   │   ├── DashboardPage.tsx   # Main dashboard
│   │   │   ├── VehiclesPage.tsx    # Vehicle list
│   │   │   ├── VehicleDetailPage.tsx # Vehicle detail
│   │   │   └── SettingsPage.tsx    # User settings
│   │   ├── services/               # API client
│   │   │   └── api.ts              # Axios client
│   │   ├── stores/                 # State management (Zustand)
│   │   │   └── authStore.ts        # Auth state
│   │   ├── styles/                 # CSS
│   │   │   └── index.css           # Global styles
│   │   ├── App.tsx                 # Main app + routing
│   │   └── index.tsx               # Entry point
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── tsconfig.json
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints (Phase 1)

### Authentication
- `POST /api/auth/register` - Register user
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user
- `POST /api/auth/refresh` - Refresh token

### Vehicles
- `POST /api/vehicles/` - Create vehicle (with auto VIN decode)
- `GET /api/vehicles/` - List user's vehicles
- `GET /api/vehicles/{id}` - Get vehicle detail
- `PUT /api/vehicles/{id}` - Update vehicle
- `DELETE /api/vehicles/{id}` - Delete vehicle
- `POST /api/vehicles/{id}/decode-vin` - Decode VIN

### Fuel Entries
- `POST /api/fuel/{vehicle_id}/entries` - Log fuel
- `GET /api/fuel/{vehicle_id}/entries` - List fuel entries
- `PUT /api/fuel/{vehicle_id}/entries/{id}` - Update entry
- `DELETE /api/fuel/{vehicle_id}/entries/{id}` - Delete entry
- `GET /api/fuel/{vehicle_id}/stats` - Fuel statistics

### Maintenance
- `POST /api/maintenance/{vehicle_id}/entries` - Log maintenance
- `GET /api/maintenance/{vehicle_id}/entries` - List entries
- `PUT /api/maintenance/{vehicle_id}/entries/{id}` - Update entry
- `POST /api/maintenance/{vehicle_id}/reminders` - Create reminder
- `GET /api/maintenance/{vehicle_id}/reminders` - List reminders
- `PUT /api/maintenance/{vehicle_id}/reminders/{id}` - Update reminder
- `GET /api/maintenance/{vehicle_id}/stats` - Maintenance stats

### Expenses
- `POST /api/expenses/{vehicle_id}/entries` - Log expense
- `GET /api/expenses/{vehicle_id}/entries` - List expenses
- `PUT /api/expenses/{vehicle_id}/entries/{id}` - Update expense
- `DELETE /api/expenses/{vehicle_id}/entries/{id}` - Delete expense
- `GET /api/expenses/{vehicle_id}/stats` - Expense stats

### Documents
- `POST /api/documents/{vehicle_id}/documents` - Upload document
- `GET /api/documents/{vehicle_id}/documents` - List documents
- `DELETE /api/documents/{vehicle_id}/documents/{id}` - Delete document

## Database Schema

### Users
```
id, email, password_hash, created_at, updated_at
```

### Vehicles
```
id, user_id, make, model, year, vin, current_mileage, 
fuel_type, nhtsa_data (JSON), created_at, updated_at
```

### Fuel Entries
```
id, vehicle_id, date, mileage, gallons, cost, location, notes,
mpg (calculated), cost_per_mile (calculated), created_at
```

### Maintenance Entries
```
id, vehicle_id, date, mileage, type, cost, service_provider, notes, created_at
```

### Maintenance Reminders
```
id, vehicle_id, service_type, interval_miles, interval_days,
last_performed_mileage, last_performed_date,
next_due_mileage, next_due_date, is_overdue, created_at, updated_at
```

### Expenses
```
id, vehicle_id, category, amount, date, description, created_at
```

### Documents
```
id, vehicle_id, filename, storage_path, ocr_text, document_type, uploaded_at
```

### Vehicle Collaborators
```
id, vehicle_id, user_id, role (viewer/editor), created_at
```

## Next Steps

### Phase 1 (MVP - Current Focus)
- [ ] Set up PostgreSQL on Proxmox LXC
- [ ] Test backend locally
- [ ] Build out React frontend components (Dashboard, Vehicle list, Forms)
- [ ] Test API endpoints
- [ ] Deploy to Docker on Proxmox
- [ ] Connect Cloudflare DNS

### Phase 2 (Polish)
- [ ] Implement OCR (Claude Vision API) for VIN/fuel/receipts
- [ ] License plate to VIN lookup
- [ ] Better storage backends (S3, B2, MinIO)
- [ ] Maintenance reminders & notifications
- [ ] User color preferences
- [ ] Advanced analytics charts

### Phase 3 (Advanced)
- [ ] Export/CSV
- [ ] Dark/light mode toggle
- [ ] Mobile app refinements
- [ ] Sync with other apps

## Testing API

Use Swagger docs: http://localhost:8000/docs

Or with curl:
```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pass123"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pass123"}'

# List vehicles (use token from login)
curl -X GET http://localhost:8000/api/vehicles/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Troubleshooting

### Database connection error
- Check `DATABASE_URL` in .env
- Ensure PostgreSQL is running
- Check database credentials

### Port already in use
- Change ports in `docker-compose.yml` or `.env`
- Or kill process: `lsof -ti:8000 | xargs kill -9`

### Frontend can't connect to API
- Check `REACT_APP_API_URL` environment variable
- Ensure backend is running
- Check browser console for CORS errors

## Environment Variables

See `.env.example` for all available options. Key ones:

```
DATABASE_URL=postgresql://user:pass@db:5432/vehicle_tracker
JWT_SECRET_KEY=your-secret-key-min-32-chars
STORAGE_TYPE=local  # or s3, b2, minio (Phase 2)
CORS_ORIGINS=http://localhost:3000
```

## Deployment to Proxmox

1. Set up PostgreSQL LXC on Proxmox
2. Configure `.env` with production values
3. Deploy using Docker Compose or Kubernetes
4. Set up Cloudflare DNS
5. Enable HTTPS (Cloudflare handles this)

## Support

For issues or questions, check:
- API docs: http://localhost:8000/docs
- Backend logs: `docker-compose logs api`
- Frontend logs: Browser console

Happy tracking!
