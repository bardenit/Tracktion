\# Vehicle Maintenance Tracker - Frontend Specification



\## Document Overview



This specification provides detailed UI/UX requirements, API integration points, component structure, and development roadmap for the Vehicle Maintenance Tracker frontend. Use this to guide frontend development with Claude Code or any developer.



\---



\## 1. Design System



\### Color Palette

\- \*\*Primary Accent:\*\* Teal (#1D9E75)

\- \*\*Background Dark:\*\* Slate-900 (#0f172a)

\- \*\*Background Secondary:\*\* Slate-800 (#1e293b)

\- \*\*Text Primary:\*\* Slate-100 (#f1f5f9)

\- \*\*Text Secondary:\*\* Slate-400 (#cbd5e1)

\- \*\*Border:\*\* Slate-700 (#334155)

\- \*\*Error:\*\* Red-600 (#dc2626)

\- \*\*Success:\*\* Green-600 (#16a34a)

\- \*\*Warning:\*\* Amber-500 (#f59e0b)



\### Typography

\- \*\*Headlines:\*\* System font stack, Bold, 24-32px

\- \*\*Body:\*\* System font stack, Regular, 14-16px

\- \*\*Small:\*\* System font stack, Regular, 12px



\### Spacing

\- Standard: 4px, 8px, 16px, 24px, 32px, 48px

\- Use Tailwind's default scale



\---



\## 2. Page Specifications



\### 2.1 Login Page (`/login`)



\*\*Purpose:\*\* User authentication



\*\*Layout:\*\*

┌─────────────────────────────────────┐

│                                     │

│  Vehicle Maintenance Tracker        │

│  Sign in to manage your vehicles    │

│                                     │

│  \[Email input]                      │

│  \[Password input]                   │

│  \[Sign In button]                   │

│                                     │

│  Note: Manual registration...       │

│                                     │

└─────────────────────────────────────┘



\*\*Components:\*\*

\- Logo/Title (text-based or SVG)

\- Email input field

\- Password input field

\- "Sign In" button (teal, full width)

\- Error message display (red background)

\- Loading spinner on button during submission



\*\*API Integration:\*\*

POST /api/auth/login

Body: {

email: "user@example.com",

password: "password123"

}

Response: {

access\_token: "eyJ...",

refresh\_token: "eyJ...",

token\_type: "bearer"

}



\*\*Behavior:\*\*

\- Store tokens in localStorage

\- On success, redirect to Dashboard

\- Show error message if credentials invalid

\- Validate email format client-side

\- Disable button during submission



\*\*Mobile:\*\* Center card, full-width padding



\---



\## 2.2 Dashboard Page (`/`)



\*\*Purpose:\*\* Overview of all vehicles and quick actions



\*\*Layout (Desktop):\*\*

┌──────────────────────────────────────────────────────────────┐

│ Dashboard                          \[User] \[Settings] \[Logout] │

├──────────────────────────────────────────────────────────────┤

│                                                                │

│ ┌─ Vehicle Selector ─────────────────────────────────────┐   │

│ │ \[2024 Cadillac CT5] ▼  \[Add Vehicle +]                 │   │

│ └────────────────────────────────────────────────────────┘   │

│                                                                │

│ ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐   │

│ │ Current Mileage  │  │ Avg Fuel Economy │  │ Total Cost │   │

│ │ 15,250 miles     │  │ 22.5 MPG         │  │ $1,250.45  │   │

│ └──────────────────┘  └──────────────────┘  └────────────┘   │

│                                                                │

│ ┌─ Quick Actions ────────────────────────────────────────┐   │

│ │ \[Log Fuel]  \[Log Service]  \[Upload Doc]  \[Analytics]  │   │

│ └────────────────────────────────────────────────────────┘   │

│                                                                │

│ ┌─ Recent Activity ──────────────────────────────────────┐   │

│ │ May 20 - Filled up 15.2 gal @ $59.28 (Meijer)         │   │

│ │ May 18 - Oil change, $65.00 (Jiffy Lube)              │   │

│ │ May 15 - Tire rotation, $80.00 (Discount Tire)        │   │

│ └────────────────────────────────────────────────────────┘   │

│                                                                │

└──────────────────────────────────────────────────────────────┘



\*\*Components:\*\*

\- Top navigation bar (user menu, logout)

\- Vehicle selector dropdown

\- Add vehicle button

\- Stat cards (4-column on desktop, stacked on mobile)

\- Quick action buttons (grid)

\- Recent activity list

\- Bottom navigation (mobile only)



\*\*Data to Fetch:\*\*

GET /api/vehicles/

GET /api/fuel/{vehicle\_id}/stats

GET /api/maintenance/{vehicle\_id}/stats

GET /api/expenses/{vehicle\_id}/stats



\*\*Behavior:\*\*

\- Load vehicle list on mount

\- Show first vehicle by default

\- Allow switching vehicles via dropdown

\- Update stats when vehicle changes

\- Quick action buttons navigate to respective forms

\- Recent activity shows last 5 entries sorted by date



\---



\## 2.3 Vehicles Page (`/vehicles`)



\*\*Purpose:\*\* List, add, and manage vehicles



\*\*Layout:\*\*

┌──────────────────────────────────────────────────────────────┐

│ Vehicles                                    \[+ Add Vehicle]   │

├──────────────────────────────────────────────────────────────┤

│                                                                │

│ ┌─ 2024 Cadillac CT5 ────────────────────────────────────┐   │

│ │ VIN: 1G1FR6S78L4149837                                 │   │

│ │ Mileage: 15,250 miles                                  │   │

│ │ Fuel Type: Gasoline                                    │   │

│ │                                                         │   │

│ │ \[View] \[Edit] \[Delete]                                 │   │

│ └─────────────────────────────────────────────────────────┘   │

│                                                                │

└──────────────────────────────────────────────────────────────┘



\*\*API Integration:\*\*



Create Vehicle:

POST /api/vehicles/

Body: {

"make": "Cadillac",

"model": "CT5",

"year": 2024,

"vin": "1G1FR6S78L4149837",

"current\_mileage": 0,

"fuel\_type": "gasoline"

}

Response: { id, make, model, year, vin, current\_mileage, fuel\_type, created\_at }



\---



\## 2.4 Vehicle Detail Page (`/vehicles/:vehicleId`)



\*\*Purpose:\*\* Detailed view with tabs for Fuel, Maintenance, Documents, Expenses



\*\*Tabs:\*\*

\- Summary (specs, quick stats)

\- Fuel (fuel entries, MPG tracking)

\- Maintenance (service logs, reminders)

\- Expenses (cost tracking by category)

\- Documents (registration, insurance, receipts)



\*\*Each tab should have:\*\*

\- List of entries with edit/delete buttons

\- "Add" button to create new entry

\- Stats summary at top



\---



\## 2.5 Forms \& Modals



\### Fuel Entry Form

Date: \[date picker]

Mileage: \[input] miles

Amount: \[input] gallons

Cost: $\[input]

Location: \[input] (optional)

Notes: \[textarea] (optional)



Validation:

\- Mileage >= previous entry's mileage

\- Gallons > 0

\- Cost > 0



\### Maintenance Entry Form

Service Type: \[dropdown with custom option]

Date: \[date picker]

Mileage: \[input]

Cost: $\[input]

Service Provider: \[input] (optional)

Notes: \[textarea] (optional)



\### Maintenance Reminders

Service Type: \[dropdown]

Interval: \[input] miles OR \[input] days



Show status indicators:

\- ✓ Green (not due yet)

\- ⚠ Amber (within 500 miles)

\- ⚠⚠ Red (overdue)



\### Expense Form

Category: \[dropdown: insurance, registration, repair, fuel, other]

Amount: $\[input]

Date: \[date picker]

Description: \[input]



\### Document Upload

Document Type: \[dropdown: registration, insurance, receipt, service, warranty, other]

\[File picker]



\---



\## 3. Component Hierarchy

App

├── Router

│   ├── LoginPage

│   ├── DashboardPage

│   │   ├── VehicleSelector

│   │   ├── StatCards (x4)

│   │   ├── QuickActionButtons

│   │   └── RecentActivityList

│   ├── VehiclesPage

│   │   ├── VehicleGrid

│   │   └── AddVehicleModal

│   ├── VehicleDetailPage

│   │   ├── TabNavigation

│   │   ├── SummaryTab

│   │   ├── FuelTab (with list + add form)

│   │   ├── MaintenanceTab (with list + reminders)

│   │   ├── ExpenseTab (with list)

│   │   └── DocumentsTab (with gallery + upload)

│   └── SettingsPage

│

├── TopNav (shared)

│   ├── UserMenu

│   └── Logout

│

└── Common Components

├── Modal

├── Form

├── InputField

├── Button

├── Table

├── Card

└── Tabs



\---



\## 4. API Response Examples



\*\*Vehicles:\*\*

```json

\[

&#x20; {

&#x20;   "id": 1,

&#x20;   "make": "Cadillac",

&#x20;   "model": "CT5",

&#x20;   "year": 2024,

&#x20;   "vin": "1G1FR6S78L4149837",

&#x20;   "current\_mileage": 15250,

&#x20;   "fuel\_type": "gasoline",

&#x20;   "nhtsa\_data": { engine details... }

&#x20; }

]

```



\*\*Fuel Entries:\*\*

```json

\[

&#x20; {

&#x20;   "id": 1,

&#x20;   "date": "2026-05-20",

&#x20;   "mileage": 15250,

&#x20;   "gallons": 15.2,

&#x20;   "cost": 59.28,

&#x20;   "location": "Meijer",

&#x20;   "mpg": 22.5,

&#x20;   "cost\_per\_mile": 0.0039

&#x20; }

]

```



\*\*Maintenance Entries:\*\*

```json

\[

&#x20; {

&#x20;   "id": 1,

&#x20;   "date": "2026-05-18",

&#x20;   "mileage": 15100,

&#x20;   "type": "Oil Change",

&#x20;   "cost": 65.00,

&#x20;   "service\_provider": "Jiffy Lube"

&#x20; }

]

```



\*\*Maintenance Reminders:\*\*

```json

\[

&#x20; {

&#x20;   "id": 1,

&#x20;   "service\_type": "Oil Change",

&#x20;   "interval\_miles": 5000,

&#x20;   "next\_due\_mileage": 20100,

&#x20;   "is\_overdue": false

&#x20; }

]

```



\*\*Expenses:\*\*

```json

\[

&#x20; {

&#x20;   "id": 1,

&#x20;   "category": "insurance",

&#x20;   "amount": 150.00,

&#x20;   "date": "2026-05-20",

&#x20;   "description": "Monthly auto insurance"

&#x20; }

]

```



\---



\## 5. Development Priority



\### Phase 1A: Foundation

\- \[ ] Authentication (LoginPage, token handling)

\- \[ ] Top navigation \& routing

\- \[ ] All pages resolve with placeholders



\### Phase 1B: Core Features

\- \[ ] Dashboard with vehicle selector \& stats

\- \[ ] Vehicles list \& add vehicle modal

\- \[ ] Vehicle detail page (all tabs)

\- \[ ] Fuel logging \& history

\- \[ ] Maintenance logging \& reminders

\- \[ ] Expense tracking

\- \[ ] Document upload



\### Phase 1C: Polish

\- \[ ] Form validation \& error messages

\- \[ ] Toast notifications

\- \[ ] Loading states

\- \[ ] Mobile responsiveness

\- \[ ] Empty states for lists



\---



\## 6. Mobile Design



\*\*Breakpoints:\*\*

\- Small: < 640px (mobile)

\- Medium: 640-1024px (tablet)

\- Large: > 1024px (desktop)



\*\*Key Changes for Mobile:\*\*

\- All modals full-screen

\- Tables scroll horizontally

\- Bottom navigation instead of sidebar

\- Stack stat cards vertically

\- Touch-friendly button sizes (44x44px minimum)



\---



\## 7. Design Tokens (Tailwind)

Primary button: bg-teal-600 hover:bg-teal-700

Secondary button: bg-slate-700 hover:bg-slate-600

Text: text-slate-100 (primary), text-slate-400 (secondary)

Border: border-slate-700

Background: bg-slate-900 or bg-slate-800

Error: text-red-600



\---



\## 8. Error Handling



\- 400: Show field-specific errors

\- 401: Redirect to login

\- 403: Show "Access denied"

\- 404: Show "Not found"

\- 500: Show "Server error"

\- Network error: Show retry button



\---



\## 9. Future Phases



\*\*Phase 2:\*\*

\- \[ ] OCR for receipts/fuel pumps/VINs (Claude Vision)

\- \[ ] License plate to VIN lookup

\- \[ ] Better storage backends (S3, B2, MinIO)

\- \[ ] Theme toggle

\- \[ ] User color preferences

\- \[ ] Advanced analytics charts



\*\*Phase 3:\*\*

\- \[ ] Collaborate/share vehicles

\- \[ ] Notifications

\- \[ ] Export/CSV

\- \[ ] Mobile app sync



\---

