# Hero Nexus AI backend

The Marvel chatbot and Comic Vine API proxy run from `C:\IA\marvel`. The Android app calls this local FastAPI service; provider credentials stay on the backend.

## Configuration

The backend reads `COMIC_VINE_API_KEY`, `GROQ_API_KEY`, and `AI_HOST` from the Android project's `local.properties` and this directory's `.env` (also accepted as the existing `,env` filename). `AI_HOST` sets the local chatbot server port; `GROQ_API_KEY` authenticates the model request to Groq. No secret values are copied into the Android app.

By default, the Android properties file is resolved at `%USERPROFILE%\AndroidStudioProjects\MarvelBattle\local.properties`. If the project is elsewhere, set `ANDROID_LOCAL_PROPERTIES` to its full path before starting the server.

The backend listens on the port in `AI_HOST` (currently 8080). Groq uses its OpenAI-compatible API URL, `https://api.groq.com/openai/v1`. `AI_MODEL` is optional; the default is `openai/gpt-oss-120b`.

## Run locally (PowerShell)

```powershell
cd C:\IA\marvel
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Check `http://localhost:8080/health`. The Android emulator reaches the computer at `http://10.0.2.2:8080/`.

## Deploy on Render

This repository contains only the chatbot backend. Create a Render Blueprint from the repository and Render will use `render.yaml`. Add `COMIC_VINE_API_KEY` and `GROQ_API_KEY` when prompted or in the service's Environment settings. The service binds to Render's assigned `$PORT`; its `/health` endpoint is the health check. Set the Android release base URL to the HTTPS URL Render assigns after deployment.

The local `.env`, `,env`, and Android `local.properties` are ignored by Git and must not be committed. `AI_HOST` is used for the local development port; Render supplies its own port.

## API

- `GET /api/characters?q=&limit=20&offset=0`
- `GET /api/characters/{id}`
- `POST /api/chat` with `message`, optional `history`, and `spoiler_level` (`NONE`, `LOW`, `MEDIUM`, `HIGH`)

The character API normalizes Comic Vine fields and pagination. Chat tools query Comic Vine for character, team, story arc, issue, power, and movie information. `/health` reports configuration status without exposing credentials.

## Tests

```powershell
cd C:\IA\marvel
.\.venv\Scripts\python.exe -m pytest
```


