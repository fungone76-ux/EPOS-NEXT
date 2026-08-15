"""SQLite exact/semantic LLM cache and deterministic image cache."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import sqlite3
from pathlib import Path

from epos.application.diagnostics import CacheStats
from epos.application.visual.bridge import RenderRequestSnapshot
from epos.application.visual.canonical import CanonicalVST
from epos.application.visual.prompt import RenderPromptContract
from epos.infrastructure.cache.models import CachedLLMResponse, ImageCacheRecord
from epos.infrastructure.cache.ports import TextEmbeddingPort


def _exact_key(namespace: str, request_json: str) -> str:
    return hashlib.sha256(f"{namespace}\0{request_json}".encode()).hexdigest()


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or len(left) != len(right):
        return -1.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return -1.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


class SQLiteLLMCache:
    """Exact SHA lookup plus genuine embedding-vector semantic lookup."""

    def __init__(
        self,
        path: Path,
        *,
        embeddings: TextEmbeddingPort,
        semantic_threshold: float = 0.92,
    ) -> None:
        if not -1.0 <= semantic_threshold <= 1.0:
            raise ValueError("semantic threshold must be between -1 and 1")
        self._path = path
        self._embeddings = embeddings
        self._semantic_threshold = semantic_threshold
        self._exact_hits = 0
        self._semantic_hits = 0
        self._misses = 0
        self._writes = 0
        self._initialize()

    @property
    def stats(self) -> CacheStats:
        return CacheStats(
            exact_hits=self._exact_hits,
            semantic_hits=self._semantic_hits,
            misses=self._misses,
            writes=self._writes,
        )

    async def get(
        self,
        *,
        namespace: str,
        request_json: str,
    ) -> CachedLLMResponse | None:
        exact = await asyncio.to_thread(self._get_exact, namespace, request_json)
        if exact is not None:
            self._exact_hits += 1
            return CachedLLMResponse(response_json=exact, kind="exact", similarity=1.0)

        vector = await self._embeddings.embed(request_json)
        rows = await asyncio.to_thread(self._semantic_rows, namespace)
        best_response: str | None = None
        best_score = -1.0
        for embedding_json, response_json in rows:
            candidate = tuple(float(value) for value in json.loads(embedding_json))
            score = _cosine(vector, candidate)
            if score > best_score:
                best_score = score
                best_response = response_json
        if best_response is not None and best_score >= self._semantic_threshold:
            self._semantic_hits += 1
            return CachedLLMResponse(
                response_json=best_response,
                kind="semantic",
                similarity=best_score,
            )
        self._misses += 1
        return None

    async def put(
        self,
        *,
        namespace: str,
        request_json: str,
        response_json: str,
    ) -> None:
        vector = await self._embeddings.embed(request_json)
        if not vector:
            raise ValueError("semantic embedding must not be empty")
        await asyncio.to_thread(
            self._put,
            namespace,
            request_json,
            response_json,
            json.dumps(vector, separators=(",", ":")),
        )
        self._writes += 1

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS llm_exact_cache (
                    cache_key TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS llm_semantic_cache (
                    namespace TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    PRIMARY KEY (namespace, request_json)
                );
                """
            )

    def _get_exact(self, namespace: str, request_json: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT response_json FROM llm_exact_cache WHERE cache_key = ?",
                (_exact_key(namespace, request_json),),
            ).fetchone()
        return None if row is None else str(row[0])

    def _semantic_rows(self, namespace: str) -> list[tuple[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT embedding_json, response_json FROM llm_semantic_cache "
                "WHERE namespace = ?",
                (namespace,),
            ).fetchall()
        return [(str(row[0]), str(row[1])) for row in rows]

    def _put(
        self,
        namespace: str,
        request_json: str,
        response_json: str,
        embedding_json: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO llm_exact_cache "
                "(cache_key, namespace, request_json, response_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET response_json=excluded.response_json",
                (_exact_key(namespace, request_json), namespace, request_json, response_json),
            )
            connection.execute(
                "INSERT INTO llm_semantic_cache "
                "(namespace, request_json, embedding_json, response_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(namespace, request_json) DO UPDATE SET "
                "embedding_json=excluded.embedding_json, response_json=excluded.response_json",
                (namespace, request_json, embedding_json, response_json),
            )


def image_cache_fingerprint(
    *,
    canonical_vst: CanonicalVST,
    prompt_contract: RenderPromptContract,
    render_request: RenderRequestSnapshot,
) -> str:
    payload = {
        "canonical_vst": canonical_vst.model_dump(mode="json"),
        "prompt_contract": prompt_contract.model_dump(mode="json"),
        "render_request": render_request.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class SQLiteImageCache:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS image_cache ("
                "fingerprint TEXT PRIMARY KEY, image_path TEXT NOT NULL, "
                "backend TEXT NOT NULL, prompt_id TEXT NOT NULL)"
            )

    async def get(self, fingerprint: str) -> ImageCacheRecord | None:
        return await asyncio.to_thread(self._get, fingerprint)

    async def put(self, record: ImageCacheRecord) -> None:
        await asyncio.to_thread(self._put, record)

    def _get(self, fingerprint: str) -> ImageCacheRecord | None:
        with sqlite3.connect(self._path) as connection:
            row = connection.execute(
                "SELECT image_path, backend, prompt_id FROM image_cache WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        return ImageCacheRecord(
            fingerprint=fingerprint,
            image_path=str(row[0]),
            backend=str(row[1]),
            prompt_id=str(row[2]),
        )

    def _put(self, record: ImageCacheRecord) -> None:
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "INSERT INTO image_cache (fingerprint, image_path, backend, prompt_id) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(fingerprint) DO UPDATE SET "
                "image_path=excluded.image_path, backend=excluded.backend, "
                "prompt_id=excluded.prompt_id",
                (
                    record.fingerprint,
                    record.image_path,
                    record.backend,
                    record.prompt_id,
                ),
            )
