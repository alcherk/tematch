# Tematch Hardening — Design Spec

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deduplication, digest windowing, LLM cost protection, and collector resync to make Tematch production-ready.

**Existing code:** Tasks 1–7 implemented — models, LLM abstraction, recommender, collector, bot handlers, scheduler.

---

## 1. Deduplication — Store All, Filter on Output

### Problem
The same post can arrive from multiple channels via reposts/quotes. Current unique constraint `(channel_id, telegram_msg_id)` prevents duplicates within a channel but not across channels.

### Decision
Store every copy (preserves analytics on which channels repost what). Deduplicate at recommendation time by content hash.

### Changes

**Model: `Message.content_hash`**
- New column: `String(64)`, nullable, indexed
- SHA-256 of normalized text: `hashlib.sha256(re.sub(r'\s+', ' ', text.strip().lower()).encode()).hexdigest()`
- Computed and stored at insert time in `collector/handlers.py`

**Recommender: dedup filter**
- After pgvector similarity query, group by `content_hash`
- Keep the earliest instance (by `date`) for each hash
- Only deduplicated candidates go to LLM ranking

**Migration:** Add `content_hash` column + index, backfill existing rows.

---

## 2. Digest Window — Hybrid Since-Last + Max 72h

### Problem
Current recommender has no time window — queries all messages ever. This wastes LLM tokens on stale content and can resurface old posts.

### Decision
Hybrid window: since last digest, capped at 72h. Split into per-channel batches when volume is high.

### Changes

**Model: `User.last_digest_at`**
- New column: `DateTime`, nullable
- Updated after each successful digest delivery

**Window logic in Recommender:**
```
if user.last_digest_at is None:
    window_start = now - 24h          # first-time user
else:
    window_start = max(user.last_digest_at, now - 72h)
```
- Adds `.where(Message.date >= window_start)` to pgvector query

**Per-channel batching for large volumes:**
- After pgvector query, if total candidates > `CANDIDATES_LIMIT` (50): split by channel
- Each channel batch → separate LLM `rank_messages` call
- User receives digest grouped by channel with headers
- Prevents feeding thousands of posts into a single LLM call

**Config:** `DIGEST_WINDOW_MAX_HOURS = 72` (configurable)

---

## 3. LLM Spam Protection — Limits + Token Budget + Batching

### Problem
No rate limiting on `/digest`. A user can spam it. Embeddings are computed one-by-one per message. No visibility into LLM costs.

### Decision
Three layers: per-user digest limit, global token budget, embedding batching + interests caching.

### A. Per-User Digest Limit

**Config:** `MAX_DIGESTS_PER_DAY = 3`

**Check before `/digest`:**
- Count delivered recommendations today for this user
- Group by digest "session" (recommendations created within 1-minute window = one digest)
- If >= limit → refuse with message: "Лимит дайджестов на сегодня: 3/3"

### B. Global Token Budget

**New model: `LLMUsage`**
```
llm_usage:
  id: int (PK)
  date: Date (indexed)
  provider: String(20)  — "openai" / "claude" / "embedding"
  operation: String(50)  — "rank_messages" / "embed_text" / "embed_texts"
  tokens_in: int
  tokens_out: int
  cost_estimate: Float  — approximate USD
```

**Tracking:**
- After each API call, log usage from response metadata (both OpenAI and Anthropic return `usage` in responses)
- No tiktoken pre-counting needed

**Config:** `DAILY_TOKEN_BUDGET = 500000`

**Check before LLM calls:**
- `SELECT SUM(tokens_in + tokens_out) FROM llm_usage WHERE date = today`
- If exceeded → refuse digest, log warning

### C. Embedding Batching in Collector

**Current:** `embed_text()` per message = 1 API call per post.

**New:** Buffer incoming messages, flush batch:
- `EmbeddingBuffer` class in collector
- Accumulates `(message_id, text)` pairs
- Flushes when buffer >= `EMBEDDING_BATCH_SIZE` (default 20) or `EMBEDDING_FLUSH_INTERVAL` (default 30s)
- Flush calls `embed_texts()` → updates DB rows in batch
- ~20x fewer API calls during high-volume collection

**Store message first without embedding**, update embedding in batch. This means messages are available immediately (without embedding) and get their embedding shortly after.

### D. Interests Embedding Cache

**Model: `User.interests_embedding`**
- New column: `Vector(1536)`, nullable
- Recomputed only when `/interests` command updates `User.interests`
- Recommender reads cached vector instead of calling embedding API

---

## 4. Collector Resync — Catch-Up on Startup

### Problem
Current collector only listens to live `NewMessage` events. If the process restarts, all messages during downtime are lost.

### Decision
On startup, iterate active channels and fetch messages since `channel.last_fetched_at`, capped at 72h.

### Changes

**New function: `collector/resync.py :: resync_channels()`**
- Called once at collector startup, before registering event handlers
- For each active channel:
  1. Read `channel.last_fetched_at` (or `now - 72h` if None)
  2. Use Telethon `client.iter_messages(channel, offset_date=last_fetched_at)` to fetch missed messages
  3. Process each through existing `handle_new_message()` (dedup by `(channel_id, msg_id)` prevents re-inserts)
  4. Embeddings go through the new batching buffer
  5. Update `channel.last_fetched_at` after each channel completes

**Config:** `RESYNC_MAX_HOURS = 72`, `RESYNC_BATCH_SIZE = 100` (messages per Telethon iter)

**Rate limiting:** Small sleep between channels to avoid Telegram flood-wait.

---

## Summary of Model Changes

| Model | Change | Type |
|-------|--------|------|
| `Message` | Add `content_hash: String(64)` + index | New column |
| `User` | Add `last_digest_at: DateTime` | New column |
| `User` | Add `interests_embedding: Vector(1536)` | New column |
| `LLMUsage` | New table | New model |
| `Settings` | Add `DIGEST_WINDOW_MAX_HOURS`, `MAX_DIGESTS_PER_DAY`, `DAILY_TOKEN_BUDGET`, `EMBEDDING_BATCH_SIZE`, `EMBEDDING_FLUSH_INTERVAL`, `RESYNC_MAX_HOURS`, `RESYNC_BATCH_SIZE` | Config |

## File Changes

| Area | Files to modify/create |
|------|----------------------|
| Models | `core/models.py` (Message, User, LLMUsage) |
| Config | `core/config.py` (new settings) |
| Migration | `alembic/versions/xxx_hardening.py` |
| Collector | `collector/handlers.py` (content_hash), `collector/resync.py` (new), `collector/main.py` (resync on startup) |
| Embeddings | `core/embeddings.py` (usage tracking), `collector/embedding_buffer.py` (new) |
| Recommender | `core/recommender.py` (window, dedup, per-channel split) |
| LLM | `core/llm/base.py`, `openai_provider.py`, `claude_provider.py` (usage tracking) |
| Bot | `bot/handlers/digest.py` (rate limit check, update last_digest_at), `bot/handlers/settings.py` (recompute interests_embedding) |
| Tests | `tests/test_dedup.py`, `tests/test_digest_window.py`, `tests/test_llm_limits.py`, `tests/test_resync.py` |
