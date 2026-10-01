# Deep Research - Frontend Implementation Plan

## Overview
Full-stack AI research chat interface styled after **Linear.app** — a dark-mode-first, precision-engineered UI optimized for displaying agent thinking, evidence streams, audit trails, and final reports.

## Architecture

```
frontend/
├── src/
│   ├── main.tsx             # React 19 + TanStack Router entry
│   ├── App.tsx              # Root layout with session provider
│   ├── routes/
│   │   ├── __root.tsx       # Base HTML + Theme Provider
│   │   ├── index.tsx        # Home: New Research / History
│   │   ├── research.$id.tsx # Single research session view (chat UI)
│   │   └── settings.tsx     # API keys + model configuration
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   └── Sidebar.tsx
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   └── PersonaPanel.tsx  # Shows real-time agent thoughts
│   │   ├── research/
│   │   │   ├── BriefingCard.tsx  # 5-point draft approval/editor
│   │   │   ├── EvidenceStream.tsx
│   │   │   ├── AuditTrail.tsx
│   │   │   └── ReportViewer.tsx
│   │   └── ui/
│   │       ├── Button.tsx
│   │       ├── Card.tsx
│   │       ├── Input.tsx
│   │       ├── Badge.tsx
│   │       └── ThemeToggle.tsx
│   ├── stores/
│   │   ├── research.store.ts  # Zustand: active research state
│   │   └── settings.store.ts  # Zustand: API keys & model mappings
│   ├── lib/
│   │   ├── api.ts        # Typed fetch wrappers
│   │   ├── theme.ts      # Linear color tokens
│   │   └── utils.ts      # Helpers
│   └── styles/
│       ├── app.css       # Base reset + variables
│       └── linear.css    # Component-level Linear tokens
├── package.json
├── vite.config.ts        # Vite + React 19 + SWC
└── tsconfig.json
```

## Tech Stack
- **Framework:** React 19 (server components optional)
- **Routing:** TanStack Router (file-based)
- **State:** Zustand
- **Styling:** Tailwind CSS + custom Linear tokens
- **Build:** Vite
- **UI Primitives:** Custom (Linear-style)
- **API Client:** fetch + Zod validation

## Real-time UX
- Live markdown renderer for agent thoughts
- Collapsible per-persona evidence panels
- Audit decision badges (`#7170ff`)
- Final report rendered with full markdown + copy-to-clipboard

## Configuration Page Fields
| Field | Type | Notes |
|-------|------|-------|
| Jina API Key | text | optional (free fallback exists) |
| Apify API Token | text | optional |
| SerpAPI API Key | text | optional |
| OpenAI API Key | text | primary LLM provider |
| Anthropic API Key | text | optional |
| Gemini API Key | text | optional |
| Scout Model | select | e.g., gpt-4o, claude-3-5-sonnet-20241022 |
| Historian Model | select | |
| Skeptic Model | select | |
| Pragmatist Model | select | |
| Futurist Model | select | |
| Auditor Model | select | |
| Writer Model | select | |

All settings saved to localStorage and passed to backend in research payloads.
