# SQL Swarm Production Backend

Production-ready FastAPI backend for Natural Language to SQL system with real-time WebSocket streaming.

## Features

- ✅ **Real-time WebSocket streaming** - See each agent's progress live
- ✅ **Production-ready** - FastAPI with async/await, error handling, health monitoring
- ✅ **Modular architecture** - Easy to maintain and extend
- ✅ **Easy configuration** - Just replace `db_schema.json` + `.env` for new schemas
- ✅ **Improved accuracy** - 60-line SQL limit, window function guidance, timeout protection
- ✅ **Fast performance** - Embedding-based retrieval, optimized prompts

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database and API credentials
```

### 3. Add Your Schema

Replace `db_schema.json` with your database schema.

### 4. Run the Server

```bash
# Development mode
uvicorn main:app --host 0.0.0.0 --port 8020 --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8020 --workers 4
```

The API will be available at: `http://localhost:8020`

## API Endpoints

### POST /api/query
Submit a natural language query.

**Request:**
```json
{
  "query": "What items have had the biggest change in value?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "success": true,
  "query_id": "uuid",
  "metadata": {
    "message": "Query accepted",
    "websocket_url": "/ws/query/{query_id}"
  }
}
```

### WebSocket /ws/query/{query_id}
Connect to receive real-time logs and results.

**Send:**
```json
{
  "query": "Your natural language question"
}
```

**Receive:**
```json
{
  "type": "log",
  "phase": "PLANNER",
  "message": "Creating logical execution plan...",
  "data": {...},
  "timestamp": "2026-01-16T07:00:00Z"
}
```

### GET /api/health
Health check endpoint.

## Configuration

### Environment Variables (.env)

```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=cgh

# LLM API
NOVITA_API_KEY=your_api_key
NOVITA_BASE_URL=https://api.novita.ai/v3/openai

# Models
PLANNER_MODEL=meta-llama/llama-3.3-70b-instruct
SYNTHESIZER_MODEL=meta-llama/llama-3.3-70b-instruct
FIXER_MODEL=meta-llama/llama-3.3-70b-instruct
RESPONSE_MODEL=meta-llama/llama-3.1-8b-instruct

# Server
PORT=8020
HOST=0.0.0.0
CORS_ORIGINS=https://dev.lumydigital.com,http://localhost:3000
```

### Schema Configuration (db_schema.json)

The schema file should follow this format:

```json
[
  {
    "name": "table_name",
    "purpose": "Table description",
    "columns": [
      {
        "name": "column_name",
        "type": "varchar(255)",
        "description": "Column description",
        "examples": ["value1", "value2"]
      }
    ]
  }
]
```

## Architecture

```
backend/
├── main.py                 # FastAPI application
├── config.py               # Configuration management
├── db_schema.json          # Database schema (replaceable)
├── agents/                 # Agent modules
│   ├── router.py
│   ├── embedding_retriever.py
│   ├── planner.py
│   ├── synthesizer.py
│   ├── validator.py
│   ├── fixer.py
│   └── response_generator.py
├── core/                   # Core utilities
│   ├── database.py
│   ├── llm_client.py
│   └── logger.py
└── api/                    # API routes (future)
```

## WebSocket Message Types

- `start` - Query processing started
- `log` - Agent phase log (ROUTER, RETRIEVER, PLANNER, SYNTHESIZER, VALIDATOR, FIXER, EXECUTOR, RESPONSE)
- `result` - Final result with SQL and data
- `error` - Error occurred

## Deployment

### Development
```bash
uvicorn main:app --host 0.0.0.0 --port 8020 --reload
```

### Production
```bash
uvicorn main:app --host 0.0.0.0 --port 8020 --workers 4
```

### With Nginx (Reverse Proxy)
```nginx
location /api/ {
    proxy_pass http://localhost:8020/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

## Switching to a New Schema

1. Replace `db_schema.json` with your new schema file
2. Update `.env` with new database credentials:
   ```env
   DB_HOST=your_host
   DB_NAME=your_database
   DB_USER=your_user
   DB_PASSWORD=your_password
   ```
3. Restart the server
4. Done! No code changes needed.

## Performance

- **Query time**: ~20-30s total
- **SQL generation**: ~6-10s
- **Success rate**: 90%+
- **SQL complexity**: <60 lines (simple, readable)

## Troubleshooting

### Database Connection Failed
- Check `.env` credentials
- Ensure MySQL is running
- Test connection: `mysql -h HOST -u USER -p DATABASE`

### LLM API Errors
- Verify `NOVITA_API_KEY` in `.env`
- Check API quota/limits
- Test endpoint: `curl https://api.novita.ai/v3/openai/models`

### Schema Not Loading
- Verify `db_schema.json` exists
- Check JSON format is valid
- Review logs for errors

## License

Proprietary - Haystek Technologies
