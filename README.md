# Vehicle Maintenance Tracker

A self-hosted vehicle maintenance tracking application with fuel economy monitoring, maintenance logging, expense tracking, and document storage.

## Features

- **Multi-vehicle support** with collaborative sharing
- **Fuel tracking** with automatic MPG calculation
- **Maintenance logging** with customizable service intervals
- **Expense tracking** by category
- **Document storage** (registration, insurance, receipts)
- **Maintenance schedule** with reminders
- **Analytics** (fuel trends, cost breakdown)
- **VIN auto-decode** from NHTSA API
- **Mobile-first** responsive design

## Tech Stack

- **Backend:** FastAPI + Python
- **Database:** PostgreSQL
- **Frontend:** React + TypeScript + Tailwind CSS
- **Storage:** Local filesystem (pluggable to S3/B2/MinIO)
- **Deployment:** Docker Compose
- **Reverse Proxy:** Behind Cloudflare

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)
- PostgreSQL 15+ (or use Docker)

### Setup with Docker

```bash
# Clone/setup project
cd vehicle-tracker

# Create .env file
cp .env.example .env

# Edit .env with your configuration
nano .env

# Start all services
docker-compose up -d

# Access the app
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run `python -m app.migrations` before local startup and after upgrading. Container
startup runs this command automatically and exits instead of serving traffic if
schema fingerprinting or an Alembic upgrade fails. Unknown legacy schema drift is
never stamped automatically; back up the database and resolve it explicitly.

**Frontend:**
```bash
cd frontend
npm install
npm start
```

## Project Structure

```
vehicle-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app entry
│   │   ├── config.py         # Configuration
│   │   ├── database.py       # Database setup
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── auth.py           # JWT authentication
│   │   ├── routes/           # API endpoints
│   │   │   ├── vehicles.py
│   │   │   ├── fuel.py
│   │   │   ├── maintenance.py
│   │   │   ├── expenses.py
│   │   │   ├── documents.py
│   │   │   └── auth.py
│   │   └── services/         # Business logic
│   │       ├── vin_decoder.py
│   │       ├── storage.py
│   │       └── ocr.py
│   ├── alembic/              # Database migrations
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API client
│   │   ├── utils/           # Utility functions
│   │   ├── styles/          # Global styles
│   │   ├── App.tsx
│   │   └── index.tsx
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Environment Variables

See `.env.example` for all required variables.

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive Swagger documentation.

## Database Schema

### Users
- id, email, password_hash, created_at, updated_at

### Vehicles
- id, user_id, make, model, year, vin, current_mileage, fuel_type, created_at, updated_at

### Fuel Entries
- id, vehicle_id, date, mileage, gallons, cost, location, notes, created_at

### Maintenance Entries
- id, vehicle_id, date, mileage, type, cost, service_provider, notes, created_at

### Expenses
- id, vehicle_id, category, amount, date, description, created_at

### Documents
- id, vehicle_id, filename, storage_path, ocr_text, type, uploaded_at

### Maintenance Reminders
- id, vehicle_id, service_type, interval_miles, interval_days, last_performed_mileage, last_performed_date

### Vehicle Collaborators
- id, vehicle_id, user_id, role, created_at

## Deployment

### Docker Compose (Development)

```bash
docker-compose up -d
```

### Production (Proxmox)

1. Set up dedicated PostgreSQL LXC container
2. Configure Cloudflare DNS to your Proxmox IP
3. Update `.env` with production values
4. Deploy using Docker Compose or Kubernetes

### Cloudflare Setup

1. Add A record pointing to your Proxmox IP
2. Enable "Full" or "Full (Strict)" SSL mode
3. Enable WAF rules for protection
4. Configure rate limiting

## OCR

Photo extraction for fuel pumps and receipts, vehicle documents, and VINs. The provider is
configurable in Settings → Integrations and defaults to a local Ollama host, so images stay on
your own network. Anthropic and any OpenAI-compatible endpoint are also supported; if the active
provider is unreachable, the app offers to retry with another rather than sending anything
elsewhere silently.

Extracted values always land in the form as an editable pre-fill for you to confirm — they are
never saved automatically. See `CHANGES_OLLAMA_MIGRATION.md` for the measured accuracy behind the
prompt and validation design.

## Phase 2 Features (Roadmap)

- License plate to VIN lookup
- Better storage backends (S3, B2, MinIO)
- User color preferences
- Maintenance reminders & notifications

## Contributing

This is a personal project, but feel free to fork and extend.

## License

MIT
