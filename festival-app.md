# SarciApp — Festival App Plan

## Festival: Sarcitopia
- ~100 attendees
- French festival, bohemian/psychedelic/nature vibe
- "La Prairie des Merveilles"

---

## Brand & Design Identity (from Instagram)
- **Color palette**: Warm earthy tones + vibrant pops
  - Deep orange/coral, sky blue, purple, bright yellow, leafy green, cherry red
  - Backgrounds: lush grass green, warm sand, deep warm black
- **Typography**: Bold, retro/vintage display fonts. Playful, not corporate.
- **Aesthetic**: Bohemian, psychedelic, nature-meets-festival. Vinyl records, tropical leaves, flowers, surreal/quirky imagery.
- **Feel**: Warm, organic, artsy, indie French festival. Community and togetherness.

---

## Features

### 1. Ticketing Platform
- Landing page to buy a ticket (name, email, payment)
- Real online payment (Stripe)
- After purchase: account auto-created, confirmation email with QR code
- Login page to access account and view QR code again
- QR code is unique per ticket, scannable by admin
- Admin scan view: shows if ticket is valid, marks it as "used" (one-scan protection)

### 2. Beer Payment Platform
- Attendee can load money onto their account at any time (Stripe)
- Bartender view (admin role): selects drinks ordered, scans attendee QR code → deducts from balance
- Attendee can check their balance from their account
- Admin can see transaction history

---

## Tech Stack

### Frontend (PWA)
- **Next.js** (React framework) — works as PWA, mobile-friendly
- **Tailwind CSS** — fast styling, easy to theme with festival colors
- Deployed on **Vercel** (free tier, very easy)

### Backend
- **Next.js API routes** — no separate backend needed for this scale
- **Supabase** — free PostgreSQL database + authentication (email/password login)
- **Stripe** — real payments (tickets + balance top-up)
- **QR code**: `qrcode` npm library to generate, `html5-qrcode` for scanning in browser

### Hosting
- **Vercel** for the app (free)
- **Supabase** for DB + auth (free tier)
- **Stripe** for payments (pay per transaction only)

---

## Data Model

### Users
- id, email, name, role (attendee | admin | bartender)
- balance (in euros/cents)
- ticket_purchased (bool)
- ticket_used (bool)

### Transactions
- id, user_id, amount, type (top_up | drink_purchase | ticket)
- created_at, bartender_id (if drink), items (JSON)

### Drinks Menu
- id, name, price

---

## Pages / Screens

1. `/` — Landing page (festival info + buy ticket CTA)
2. `/buy` — Ticket purchase form + Stripe payment
3. `/login` — Login page
4. `/account` — My ticket QR code + balance + top-up button
5. `/admin/scan` — Admin: scan QR to validate ticket entry
6. `/bartender` — Bartender: select drinks + scan QR to charge
7. `/admin` — Admin dashboard (transactions, attendees)
