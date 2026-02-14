# Channel Diversity in Recommender — Design

## Overview
Ensure digest includes messages from multiple channels instead of being dominated by one. Quality-first approach: diverse candidate pool fed to LLM, quality gate drops non-relevant items.

## Current Flow
1. Single pgvector query → top 50 by cosine similarity (all channels mixed)
2. Dedup by content hash
3. LLM ranks → top 5

## New Flow

**Stage 1 — Diverse candidate pool:**
For each subscribed channel, fetch top `ceil(candidates_limit / len(channel_ids))` messages by cosine similarity. Merge all per-channel results into one pool. Dedup as before.

**Stage 2 — LLM ranking (higher limit):**
Send pool to LLM with `digest_size=30`. LLM returns ranked messages with scores.

**Stage 3 — Quality gate:**
Filter LLM results: only keep messages with `score >= 0.5`. Non-relevant messages dropped regardless of channel. No hard minimum per channel — if a channel's content isn't relevant, it doesn't appear.

## Result
- Diverse by construction: each channel gets fair representation in the candidate pool
- Quality-filtered: LLM + threshold drops irrelevant items
- Up to 30 items max, but typically fewer after quality gate
- Pagination already handles large digests via `split_digest_pages`

## Scope
- Modify: `core/recommender.py` — diverse pool query, `digest_size` 5→30, quality threshold
- No model/migration/formatter/frontend changes
