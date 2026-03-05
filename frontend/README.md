# Frontend - Ethic Companion

Next.js 14 frontend for Ethic Companion.

## Philosophy: Trust over Engagement

This frontend is built with ethical principles:
- ✅ No dark patterns - Clear, honest UI
- ✅ User control - Easy access to settings and boundaries
- ✅ Transparency - Show all ESL decisions
- ✅ Mindful design - No addictive mechanics

## Getting Started

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.local.example .env.local
```

Edit `.env.local` with your backend API URL:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Project Structure

```
frontend/
├── app/
│   ├── page.tsx              # Landing page (redirects to dashboard)
│   └── dashboard/            # Main application area
│       ├── layout.tsx        # Dashboard navigation
│       ├── page.tsx          # Dashboard home
│       ├── chat/            # Chat interface (TODO)
│       ├── values/          # User values management (TODO)
│       ├── goals/           # Goals management (TODO)
│       └── transparency/    # ESL transparency (TODO)
├── lib/
│   └── api.ts               # Backend API client
```

## API Integration

```typescript
import api from '@/lib/api'

// Send chat message
const response = await api.chat.send('What should I focus on?')

// Get ESL transparency report
const report = await api.transparency.report(7)
```

## Next Steps

- [ ] Chat interface
- [ ] Values management UI
- [ ] Transparency dashboard
- [ ] Goals management

---

*Built with Trust over Engagement*

