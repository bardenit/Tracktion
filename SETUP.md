# Quick Setup Guide

## What's Been Built (Phase 1 Foundation)

✅ **Backend (FastAPI)**
- User authentication (JWT)
- Vehicle management (CRUD + VIN auto-decode from NHTSA)
- Fuel tracking with auto MPG calculation
- Maintenance logging with customizable reminders
- Expense tracking by category
- Document storage (local filesystem, Phase 1)
- All API endpoints with proper auth/permissions
- Database models (SQLAlchemy + PostgreSQL)

✅ **Frontend (React + TypeScript)**
- Login page with auth
- Basic routing structure
- API client (Axios) with token management
- Auth store (Zustand)
- Placeholder pages for expansion
- Tailwind CSS dark theme (teal accent #1D9E75)
- Responsive layout setup

✅ **Infrastructure**
- Docker Compose setup for all services
- PostgreSQL container
- API container
- Frontend container
- Environment configuration (.env)

---

## Step 1: Get the Files (You have this already)

The entire project is in `/home/claude/vehicle-tracker/`

```
cd /home/claude/vehicle-tracker
```

---

## Step 2: Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit for your setup (nano or your preferred editor)
nano .env
```

**Key values to update:**
```
DATABASE_PASSWORD=change_this_to_something_secure
JWT_SECRET_KEY=generate_a_random_32_char_string
# Use: openssl rand -base64 32
```

---

## Step 3: Start Everything with Docker

**First time:**
```bash
# Build and start all services
docker-compose up -d

# Initialize the database
docker-compose exec api python -m alembic upgrade head

# Check if running
docker-compose ps
```

**Subsequent times:**
```bash
# Just start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f api
docker-compose logs -f
```

---

## Step 4: Test Everything

**API is ready at:**
- Swagger Docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

**Frontend at:**
- http://localhost:3000

**Register & Login:**
1. Go to http://localhost:3000
2. Register an account (use email + password)
3. Login
4. You should see the dashboard

---

## Step 5 (Optional): Test Locally Without Docker

**Backend only:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up .env in backend/ directory
# DATABASE_URL=postgresql://localhost/vehicle_tracker
# JWT_SECRET_KEY=your_secret

uvicorn app.main:app --reload
# Runs on http://localhost:8000
```

**Frontend only:**
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

---

## Step 6: Add Test Data

Using the API docs (http://localhost:8000/docs):

1. Register a user via `/auth/register`
2. Login via `/auth/login` (copy the access_token)
3. Click "Authorize" button in Swagger, paste token
4. Create a vehicle via POST `/vehicles/`
   ```json
   {
     "make": "Cadillac",
     "model": "CT5",
     "year": 2024,
     "vin": "1G1FR6S78L4149837",
     "current_mileage": 5000,
     "fuel_type": "gasoline"
   }
   ```
5. The VIN will auto-decode from NHTSA API

---

## Step 7: Next - Expand the Frontend

The frontend has placeholder pages. You'll want to build out:

**Priority 1 (Core Experience):**
- Vehicle list & detail pages (fetch from API, display specs)
- Fuel entry form (POST to API)
- Fuel log view (GET from API, show stats)
- Maintenance entry form
- Basic dashboard with stats

**Priority 2 (Polish):**
- Document upload UI
- Maintenance reminders view
- Expense tracking
- Analytics charts (use Recharts - already in deps)

**Priority 3 (Phase 2):**
- OCR button (Claude Vision API integration)
- Plate-to-VIN lookup
- Better storage backends

---

## Step 8: Deploy to Proxmox

**Option A: Docker Compose (Simplest)**
1. Create Proxmox LXC for PostgreSQL (2-4 cores, 4-8GB RAM, 50-100GB storage)
2. Set up dedicated database
3. Copy project to Proxmox machine
4. Update `.env` with Proxmox PostgreSQL IP
5. Run `docker-compose up -d`

**Option B: Full Production Setup**
1. PostgreSQL on separate LXC
2. API + Frontend in Docker on another LXC
3. Cloudflare DNS pointing to Proxmox
4. Cloudflare handling HTTPS/SSL

---

## Useful Commands

```bash
# View all containers
docker-compose ps

# View logs for specific service
docker-compose logs api
docker-compose logs postgres
docker-compose logs -f frontend  # follow logs

# Stop everything
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Enter container shell
docker-compose exec api /bin/bash
docker-compose exec postgres psql -U vehicle_user -d vehicle_tracker

# Rebuild containers after code changes
docker-compose up -d --build

# Check database (if postgres running)
psql -h localhost -U vehicle_user -d vehicle_tracker
# Password: whatever you set in .env
```

---

## File Structure to Know

```
vehicle-tracker/
├── .env                          # Your configuration (edit this)
├── docker-compose.yml            # Container setup
├── README.md                      # Project overview
├── DEVELOPMENT.md                 # Detailed dev guide
├── SETUP.md                       # This file
│
├── backend/
│   ├── app/main.py              # FastAPI entry point
│   ├── app/routes/              # All API endpoints
│   ├── app/models.py            # Database schema
│   └── requirements.txt          # Python dependencies
│
└── frontend/
    ├── src/
    │   ├── pages/               # React pages (to expand)
    │   ├── services/api.ts      # API client
    │   └── App.tsx              # Main routing
    └── package.json             # Node dependencies
```

---

## Key API Endpoints (For Reference)

All require Authorization header with Bearer token.

**Vehicles:**
- `POST /api/vehicles/` - Create vehicle (auto-decodes VIN)
- `GET /api/vehicles/` - List all user vehicles
- `GET /api/vehicles/{id}` - Get one vehicle
- `PUT /api/vehicles/{id}` - Update vehicle
- `DELETE /api/vehicles/{id}` - Delete vehicle

**Fuel:**
- `POST /api/fuel/{vehicle_id}/entries` - Log fuel (calculates MPG)
- `GET /api/fuel/{vehicle_id}/entries` - List fuel logs
- `GET /api/fuel/{vehicle_id}/stats` - Get fuel statistics

**Maintenance:**
- `POST /api/maintenance/{vehicle_id}/entries` - Log service
- `GET /api/maintenance/{vehicle_id}/entries` - List services
- `POST /api/maintenance/{vehicle_id}/reminders` - Create reminder
- `GET /api/maintenance/{vehicle_id}/reminders` - List reminders

**Expenses:**
- `POST /api/expenses/{vehicle_id}/entries` - Log expense
- `GET /api/expenses/{vehicle_id}/entries` - List expenses
- `GET /api/expenses/{vehicle_id}/stats` - Get stats

**Documents:**
- `POST /api/documents/{vehicle_id}/documents` - Upload file
- `GET /api/documents/{vehicle_id}/documents` - List documents

Full API docs at: http://localhost:8000/docs (when running)

---

## Troubleshooting

**Port 8000 already in use?**
```bash
lsof -ti:8000 | xargs kill -9
```

**Port 3000 already in use?**
```bash
lsof -ti:3000 | xargs kill -9
```

**Can't connect to database?**
- Check DATABASE_URL in .env
- Ensure PostgreSQL service is running
- Verify credentials

**Frontend shows blank page?**
- Check browser console for errors
- Ensure backend is running (http://localhost:8000/docs should work)
- Check CORS_ORIGINS in .env includes frontend URL

**Docker build fails?**
```bash
# Clean up and rebuild
docker-compose down
docker system prune -a
docker-compose up -d --build
```

---

## You're Ready to Go!

1. **Start the app:** `docker-compose up -d`
2. **Test it:** http://localhost:3000
3. **Expand frontend:** Build out the pages
4. **Add Phase 2 features:** OCR, better storage, etc.
5. **Deploy:** Move to Proxmox when ready

Questions? Check:
- README.md (overview)
- DEVELOPMENT.md (detailed guide)
- API docs (http://localhost:8000/docs)

Good luck!
