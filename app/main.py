import json
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .agent import create_marvel_agent, normalize_spoiler_level
from .comic_vine import ComicVineClient, ComicVineError
from .config import get_settings
from .schemas import ApiError, Character, CharacterPage, ChatRequest, ChatResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = get_settings()
    yield


app = FastAPI(title="Hero Nexus API", version="1.0.0", lifespan=lifespan)
logger = logging.getLogger("hero_nexus.api")


def comic_vine_client() -> ComicVineClient:
    settings = get_settings()
    return ComicVineClient(settings.comic_vine_api_key)


def error_response(error: ComicVineError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


def character_fallback(message: str, client: ComicVineClient) -> ChatResponse | None:
    """Return a short, source-backed profile if the model provider is unavailable."""
    match = re.search(
        r"\b(?:sobre|quem\s+é|quem\s+e|fale\s+(?:mais\s+)?(?:sobre|de)|me\s+conte\s+(?:mais\s+)?(?:sobre|de))\s+(.+?)\s*[?.!]*$",
        message.strip(), re.IGNORECASE,
    )
    if not match:
        return None
    query = re.sub(r"^(?:o|a|os|as)\s+", "", match.group(1).strip(), flags=re.IGNORECASE)
    if not query:
        return None
    page = client.search_characters(query, limit=8, offset=0)
    results = page.get("results", [])
    if not results:
        return None
    normalized = query.casefold()
    character = next((item for item in results if item.get("name", "").casefold() == normalized), results[0])
    name = character.get("name", "Esse personagem")
    facts = []
    if character.get("real_name"):
        facts.append(f"Identidade: {character['real_name']}.")
    if character.get("deck"):
        facts.append(str(character["deck"]).strip())
    powers = [power.get("name") for power in character.get("powers", []) if power.get("name")]
    if powers:
        facts.append("Poderes registrados: " + ", ".join(powers[:6]) + ".")
    teams = [team.get("name") for team in character.get("teams", []) if team.get("name")]
    if teams:
        facts.append("Equipes: " + ", ".join(teams[:4]) + ".")
    if not facts:
        facts.append("Encontrei o personagem na base da Comic Vine, mas ela não retornou uma descrição curta.")
    answer = f"{name}\n\n" + "\n\n".join(facts)
    source = character.get("api_detail_url") or "https://comicvine.gamespot.com/"
    return ChatResponse(answer=answer, sources=[source])


@app.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "comic_vine_configured": bool(settings.comic_vine_api_key),
            "ai_configured": bool(settings.ai_api_key and settings.ai_model)}


@app.get("/api/characters", response_model=CharacterPage)
def characters(q: str = Query(default="", max_length=120), limit: int = Query(default=20, ge=1, le=50), offset: int = Query(default=0, ge=0)):
    client = comic_vine_client()
    try:
        return client.search_characters(q.strip(), limit, offset)
    except ComicVineError as exc:
        raise error_response(exc) from exc
    finally:
        client.close()


@app.get("/api/characters/{character_id}", response_model=Character)
def character(character_id: int):
    client = comic_vine_client()
    try:
        return client.get_character(character_id)
    except ComicVineError as exc:
        raise error_response(exc) from exc
    finally:
        client.close()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    settings = get_settings()
    client = comic_vine_client()
    try:
        level = normalize_spoiler_level(request.spoiler_level)
        agent = create_marvel_agent(settings, client, level)
    except RuntimeError as exc:
        client.close()
        if str(exc) == "AI_NOT_CONFIGURED":
            raise HTTPException(status_code=503, detail={"code": "ai_not_configured", "message": "The AI service is not configured."}) from exc
        raise HTTPException(status_code=503, detail={"code": "ai_provider_unsupported", "message": "The configured AI provider is not supported."}) from exc

    messages = []
    for item in request.history[-10:]:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content[:2000]})
    messages.append({"role": "user", "content": request.message.strip()})
    try:
        result = await agent.ainvoke({"messages": messages})
        final_message = result["messages"][-1]
        answer = final_message.content
        if isinstance(answer, list):
            answer = "\n".join(str(block.get("text", "")) for block in answer if isinstance(block, dict))
        sources = []
        for message in result["messages"]:
            if getattr(message, "type", "") == "tool":
                try:
                    tool_data = json.loads(message.content)
                    url = tool_data.get("source_url")
                    if url and url not in sources:
                        sources.append(url)
                    result_data = tool_data.get("result")
                    if isinstance(result_data, dict):
                        detail_url = result_data.get("api_detail_url")
                        if detail_url and detail_url not in sources: sources.append(detail_url)
                    for item in tool_data.get("results", []):
                        if isinstance(item, dict) and item.get("api_detail_url") and item["api_detail_url"] not in sources:
                            sources.append(item["api_detail_url"])
                except (TypeError, ValueError):
                    continue
        return ChatResponse(answer=str(answer), sources=sources)
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        logger.warning("AI completion failed (%s, status=%s)", type(exc).__name__, status)
        try:
            fallback = character_fallback(request.message.strip(), client)
            if fallback is not None:
                return fallback
        except Exception as fallback_error:
            logger.warning("Character fallback failed (%s)", type(fallback_error).__name__)
        raise HTTPException(status_code=502, detail={"code": "ai_request_failed", "message": "The AI could not complete the request."}) from exc
    finally:
        client.close()


@app.exception_handler(HTTPException)
async def structured_http_error(request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_failed", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})
