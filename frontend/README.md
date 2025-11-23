# Chat UI - React Frontend

React-based chat UI for testing the LangGraph Agent API using `assistant-ui`.

## Features

- 🎨 Modern dark theme with glassmorphism
- 💬 Real-time streaming chat interface
- 🔐 Bearer token authentication
- 🐳 Docker containerized with nginx
- 🔄 SSE (Server-Sent Events) support
- 📱 Responsive design

## Quick Start

### With Docker Compose (Recommended)

From the parent directory:

```bash
docker compose up --build
```

Access at: http://localhost:3000

### Local Development

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build
```

## Architecture

### Custom Runtime Adapter

The app uses a custom `LangGraphRuntime` adapter to connect `assistant-ui` with the LangGraph backend:

- **Thread Management**: Creates threads via `/threads` endpoint
- **Streaming**: Handles SSE streaming from `/threads/{id}/runs/stream`
- **Authentication**: Injects Bearer token in all requests
- **Message Parsing**: Converts between assistant-ui and LangGraph formats

### Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **assistant-ui** - Chat UI components
- **Radix UI** - Headless UI primitives
- **nginx** - Production server

## Usage

1. Open http://localhost:3000
2. Enter your Bearer token
3. Click "Connect"
4. Start chatting!

## Environment

The frontend proxies API requests to the backend:

- `/threads/*` → `http://agent:8000`
- `/health` → `http://agent:8000`

In development, Vite handles the proxy. In production, nginx handles it.

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/              # Reusable UI components
│   │   └── assistant-ui/    # Chat thread component
│   ├── lib/
│   │   ├── langGraphRuntime.ts  # Custom runtime adapter
│   │   └── utils.ts         # Utility functions
│   ├── App.tsx              # Main app component
│   ├── App.css              # App styles
│   ├── index.css            # Global styles
│   └── main.tsx             # Entry point
├── Dockerfile               # Multi-stage build
├── nginx.conf              # Production server config
└── package.json            # Dependencies
```

## Development

### API Testing

The backend must be running for the frontend to work. The API expects:

**Create Thread**
```http
POST /threads
Authorization: Bearer <token>
Content-Type: application/json
```

**Stream Messages**
```http
POST /threads/{thread_id}/runs/stream
Authorization: Bearer <token>
Content-Type: application/json

{
  "assistant_id": "default",
  "input": {
    "messages": [{"type": "human", "content": "Hello"}]
  },
  "stream_mode": "messages"
}
```

### SSE Format

The backend streams events in this format:

```
event: messages/partial
data: [{"type": "AIMessageChunk", "content": "...", "id": "..."}]

event: metadata
data: {"run_id": "...", "thread_id": "..."}
```

## Production Build

The Dockerfile creates a multi-stage build:

1. **Build Stage**: Installs deps and builds React app
2. **Production Stage**: Serves with nginx

Final image is optimized and includes:
- Compiled static assets
- nginx configuration
- API proxy setup
- SSE support

## Troubleshooting

**Can't connect to backend:**
- Ensure backend is running on port 8000
- Check docker network connectivity
- Verify token is valid

**Streaming not working:**
- Check browser console for errors
- Verify SSE connection in Network tab
- Ensure nginx buffering is disabled

**Build fails:**
- Clear `node_modules` and reinstall
- Check Node version (requires 20+)
- Verify all dependencies are installed
