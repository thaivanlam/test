# Database Performance & Indexing

**Tier 3C.** Measured on branch `assessment/thai-van-lam`. The index is added by
migration `a5ac6aec37c4` in commit `7716d12`.

Every figure below comes from an executed `EXPLAIN (ANALYZE, BUFFERS)`. None is
estimated. Every run is reported; none was discarded as an outlier.

---

## 1. Dataset and environment

| Item | Value |
|---|---|
| Users | **10,000** |
| Todos | **1,000,000** |
| Users that own todos | 9,942 (see note below) |
| Todos per user | min 66 · p25 94 · **median 100** · mean 100.6 · p75 107 · max 145 |
| `todos` heap | 213 MB (250 MB with indexes and TOAST at seed time) |
| PostgreSQL | 16.15, `postgres:16-alpine`, Docker Desktop on Windows |
| `shared_buffers` | 128 MB — smaller than the table, which matters for the seq-scan figures |
| `max_parallel_workers_per_gather` | 2 |
| JIT | on, but not triggered by any measured query |

**Benchmark user:** `00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab`, with **100 todos**.
The rule used to pick it was: take the users whose todo count equals the median
(100 — there are 397 of them), then the one with the lowest `user_id`. The same
user was used in every measurement.

**How the dataset was produced.** The seed script skips todo seeding if the
table already holds any rows. The development database had 58 users and 41
todos. The 41 todos were exported with `pg_dump --data-only -t todos` to a file
outside the repository, and then `TRUNCATE TABLE todos` was run. **Only
`todos` was cleared; users were not touched.** The seed then ran:

```bash
docker compose exec -e SEED_USERS=10000 -e SEED_TODOS=1000000 -e DB_ECHO=false \
  backend python -m app.db.seed
```

It created the demo user, bringing the total to 59, and then 9,941 more users
to reach 10,000. It then spread the 1,000,000 todos across the demo user and
the new users: 9,942 users in all. The 58 users that already existed got no
seeded todos, because the script only assigns todos to users it creates
itself. The seed took 38.8 s. `DB_ECHO=false` is an environment override;
without it the default configuration logs every insert.

`VACUUM ANALYZE todos` was run after seeding, and again before each
measurement pass, so that planner statistics and the visibility map were
current.

---

## 2. Query shapes

These match the SQL the application emits for `todo_service.get_todos`, where
the select list is every column of `Todo`:

| ID | Rubric category | SQL |
|---|---|---|
| **A** | user-filtered | `SELECT <cols> FROM todos WHERE user_id = $1` |
| **B** | ordered by `created_at` | `SELECT <cols> FROM todos WHERE user_id = $1 ORDER BY created_at DESC` |
| **C** | counting | `SELECT count(*) FROM todos WHERE user_id = $1` |
| **D** | *the application's actual list query* | `SELECT <cols> FROM todos WHERE user_id = $1 LIMIT 20 OFFSET 0` |
| *E* | *supplementary, not sent by the app* | `SELECT <cols> FROM todos WHERE user_id = $1 ORDER BY created_at DESC LIMIT 20` |

`<cols>` = `id, title, description, completed, user_id, created_at, updated_at`.

**D** is what the application actually runs: page 1 with the default size.
**C** is the count that follows it. The application's list query has **no
`ORDER BY`** (SEC-13). **E** was measured only to judge the composite-index
alternative (§6), and is not part of the before/after comparison.

**Method.** Each query was run 7 times in a row with
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, through `psql` inside the Postgres
container. The tables report the median, min and max of `Execution Time`, and
separately the median `Planning Time`. Buffers are the top node's
`shared hit + read`. Postgres counts buffers inclusively of child nodes, so the
top node covers the whole plan.

---

## 3. BEFORE — no index on `user_id`

The only index on `todos` was `todos_pkey (id)`.

Representative plans, one run of each, taken after the timed runs:

**A — filter**
```
Gather  (cost=1000.00..33476.43 rows=101 width=188) (actual time=1.384..39.492 rows=100 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=11946 read=15312
  ->  Parallel Seq Scan on todos  (cost=0.00..32466.33 rows=42 width=188) (actual time=0.922..33.233 rows=33 loops=3)
        Filter: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
        Rows Removed by Filter: 333300
        Buffers: shared hit=11946 read=15312
Planning Time: 0.738 ms
Execution Time: 39.577 ms
```

**B — filter + order**
```
Gather Merge  (cost=33467.49..33477.29 rows=84 width=188) (actual time=42.269..44.620 rows=100 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  Buffers: shared hit=12828 read=14544
  ->  Sort  (cost=32467.47..32467.57 rows=42 width=188) (actual time=39.191..39.194 rows=33 loops=3)
        Sort Key: created_at DESC
        Sort Method: quicksort  Memory: 30kB
        ->  Parallel Seq Scan on todos  (cost=0.00..32466.33 rows=42 width=188) (actual time=1.913..38.760 rows=33 loops=3)
              Filter: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
              Rows Removed by Filter: 333300
Planning Time: 0.701 ms
Execution Time: 44.718 ms
```

**C — count**
```
Finalize Aggregate  (cost=33466.65..33466.66 rows=1 width=8) (actual time=41.542..44.382 rows=1 loops=1)
  Buffers: shared hit=13482 read=13776
  ->  Gather  (cost=33466.44..33466.65 rows=2 width=8) (actual time=41.358..44.297 rows=3 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        ->  Partial Aggregate  (cost=32466.44..32466.45 rows=1 width=8) (actual time=38.339..38.340 rows=1 loops=3)
              ->  Parallel Seq Scan on todos  (cost=0.00..32466.33 rows=42 width=0) (actual time=1.655..38.301 rows=33 loops=3)
                    Filter: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
                    Rows Removed by Filter: 333300
Planning Time: 0.339 ms
Execution Time: 44.467 ms
```

**D — application page**
```
Limit  (cost=1000.00..7430.98 rows=20 width=188) (actual time=0.412..12.631 rows=20 loops=1)
  Buffers: shared hit=6070 read=4498
  ->  Gather  (cost=1000.00..33476.43 rows=101 width=188) (actual time=0.410..12.622 rows=20 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        ->  Parallel Seq Scan on todos  (cost=0.00..32466.33 rows=42 width=188) (actual time=1.329..8.739 rows=14 loops=3)
              Filter: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
              Rows Removed by Filter: 129206
Planning Time: 0.554 ms
Execution Time: 12.687 ms
```

**Reading these plans.** A, B and C each read the **whole table**, about 27,300
pages, which is the full 213 MB heap. They discard 999,900 rows to return 100.
Because the table is larger than `shared_buffers`, between 13,872 and 15,984
of those pages came in as `read` on every run instead of `hit`. `read` means the
page was not in Postgres's own buffer cache. It may still have come from the
operating system's cache rather than from disk; that was not distinguished.

**D** is noticeably faster and less stable than the others. Without an
`ORDER BY`, the scan can stop as soon as it has 20 matching rows. How far it
has to go depends on where this user's rows sit in the heap, and on how the
work is split across the parallel workers. Over the 7 runs it touched between
9,515 and 15,077 pages.

---

## 4. AFTER — `ix_todos_user_id`

Migration `a5ac6aec37c4` created
`CREATE INDEX CONCURRENTLY ix_todos_user_id ON todos (user_id)`. It was applied
with `alembic upgrade head` and followed by `VACUUM ANALYZE`. The index is
**7,096 kB**, `indisvalid = true`.

**A — filter**
```
Bitmap Heap Scan on todos  (cost=5.20..388.28 rows=100 width=188) (actual time=0.033..0.135 rows=100 loops=1)
  Recheck Cond: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
  Heap Blocks: exact=100
  Buffers: shared hit=103
  ->  Bitmap Index Scan on ix_todos_user_id  (cost=0.00..5.17 rows=100 width=0) (actual time=0.021..0.022 rows=100 loops=1)
        Index Cond: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
        Buffers: shared hit=3
Planning Time: 0.636 ms
Execution Time: 0.194 ms
```

**B — filter + order**
```
Sort  (cost=391.60..391.85 rows=100 width=188) (actual time=0.218..0.222 rows=100 loops=1)
  Sort Key: created_at DESC
  Sort Method: quicksort  Memory: 46kB
  Buffers: shared hit=106
  ->  Bitmap Heap Scan on todos  (cost=5.20..388.28 rows=100 width=188) (actual time=0.026..0.180 rows=100 loops=1)
        Recheck Cond: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
        Heap Blocks: exact=100
        ->  Bitmap Index Scan on ix_todos_user_id  (cost=0.00..5.17 rows=100 width=0) (actual time=0.016..0.017 rows=100 loops=1)
              Index Cond: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
Planning Time: 0.642 ms
Execution Time: 0.276 ms
```

**C — count**
```
Aggregate  (cost=6.42..6.43 rows=1 width=8) (actual time=0.041..0.042 rows=1 loops=1)
  Buffers: shared hit=4
  ->  Index Only Scan using ix_todos_user_id on todos  (cost=0.42..6.17 rows=100 width=0) (actual time=0.031..0.036 rows=100 loops=1)
        Index Cond: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
        Heap Fetches: 0
        Buffers: shared hit=4
Planning Time: 0.639 ms
Execution Time: 0.077 ms
```

**D — application page**
```
Limit  (cost=0.42..81.57 rows=20 width=188) (actual time=0.015..0.035 rows=20 loops=1)
  Buffers: shared hit=23
  ->  Index Scan using ix_todos_user_id on todos  (cost=0.42..406.17 rows=100 width=188) (actual time=0.014..0.033 rows=20 loops=1)
        Index Cond: (user_id = '00ab4b2f-5fe5-4f3f-9e51-07a58d1e1aab'::uuid)
        Buffers: shared hit=23
Planning Time: 0.628 ms
Execution Time: 0.075 ms
```

The count now runs as an **Index Only Scan** with `Heap Fetches: 0`. The
visibility map is current after `VACUUM`, so Postgres answers from the index
alone and reads 4 pages.

---

## 5. Before vs after

Execution time over 7 runs of each query. The medians use every run.

| Query | BEFORE median | BEFORE min–max | AFTER median | AFTER min–max | Speed-up (median) | Plan before → after | Buffers before → after |
|---|---|---|---|---|---|---|---|
| **A** filter | 30.258 ms | 26.404–52.240 | **0.247 ms** | 0.193–0.563 | **~122×** | Parallel Seq Scan → Bitmap Index + Heap Scan | ~27,260 → 103 |
| **B** filter + order | 32.023 ms | 26.320–34.136 | **0.253 ms** | 0.224–0.495 | **~127×** | Parallel Seq Scan + Sort → Bitmap scan + Sort | ~27,370 → 106 |
| **C** count | 35.032 ms | 26.668–56.221 | **0.071 ms** | 0.069–0.109 | **~493×** | Parallel Seq Scan → Index Only Scan | ~27,260 → 4 |
| **D** app page | 20.201 ms | 12.996–31.393 | **0.084 ms** | 0.082–0.111 | **~240×** | Parallel Seq Scan → Index Scan | 9,515–15,077 → 23 |

**Where the gain is smallest, and why.**

- **B still sorts.** With 100 rows the planner fetches them by bitmap and sorts
  them in memory (46 kB). In the plan shown, the sort accounts for about
  0.04 ms of 0.28 ms (0.222 ms at the Sort node against 0.180 ms at its input). The index
  removes the full-table read, not the sort. §6 shows that removing the sort
  as well would need a different index, and that it would make no measurable
  difference to this query.
- **Planning time now exceeds execution time.** Median planning time is
  0.40–0.65 ms before and 0.57–0.78 ms after. It is reported separately and is
  not included in `Execution Time`. After indexing, planning is the larger
  share of each query's database cost. The application's driver, asyncpg,
  uses prepared statements, which can let planning be reused, but that was not
  measured.
- **Variability.** The AFTER maxima (0.563 ms for A, 0.495 ms for B) are single
  slower runs. A's slow run was the first after `VACUUM`, and read 99 pages
  from outside shared buffers. They are included in the figures, not dropped.

---

## 6. Choice of index

### What the BEFORE plans showed

Every query filters on `user_id = $1`, and every plan was a parallel sequential
scan of the entire table, because no index had `user_id` as a leading column.
PostgreSQL does not index foreign-key columns automatically. The bottleneck was
therefore reading 213 MB to find about 100 rows. Any index that leads with
`user_id` removes it.

### Candidates measured

Two candidates were measured on the same data and the same user. Each was
created by hand, measured, then dropped; only the chosen one became a
migration.

| | `(user_id)` — **chosen** | `(user_id, created_at DESC)` |
|---|---|---|
| Size | **7,096 kB** | **39 MB** |
| A filter | 0.377 ms | 0.443 ms |
| B filter + order | 0.467 ms — Sort | 0.473 ms — **still Sort** |
| C count | 0.069 ms — Index Only Scan | 0.082 ms — Index Only Scan |
| D app page | 0.102 ms | 0.155 ms |
| *E ordered page (`LIMIT 20`)* | *0.416 ms — Sort* | ***0.131 ms — no Sort, 23 buffers*** |
| Build time (plain `CREATE INDEX`) | 325 ms | 479 ms |

These are the medians from the experiment runs. The official AFTER figures in
§5 were measured separately with the migration's index. They differ from the
`(user_id)` column here by run-to-run variance: for example, A was 0.377 ms in
the experiment and 0.247 ms after the migration, with the same index.

**The composite index was no faster on A, B, C or D.** For query B the planner
still used a bitmap scan and a sort. With only 100 matching rows, that is
cheaper than walking the index in order, which visits the heap in random
order. So the benefit usually claimed for the composite — returning rows
already ordered, without a sort — did not appear for the rubric's ordered
query.

**The composite's size comes from its keys being unique.** All 1,000,000
`(user_id, created_at)` pairs are distinct, so B-tree deduplication (Postgres
13 and later) has nothing to compress. The single-column index repeats each
`user_id` about 100 times, and deduplication stores those as compact posting
lists. That is the reason for 7 MB against 39 MB.

**Its only win was E**, ordered pagination with `LIMIT`: 0.131 ms against
0.416 ms, with no sort. The application does not send that query, because it
has no `ORDER BY` (SEC-13).

### Why `(user_id)`

- It matches the predicate every current query shares, `user_id = $1`, and
  removes the measured bottleneck on all four.
- It also serves the count as an index-only scan, through its only column.
- It is about 5.6× smaller than the composite (7,096 kB against 39 MB), and
  costs less on every write (§7).
- The composite offered nothing measurable on the queries the application
  sends or the rubric names.

### Why no further indexes

- **`completed`**, as in the rubric's example `(user_id, completed, created_at)`:
  the application never filters on `completed`. A status filter arrives only
  in Tier 4. Adding it now would be indexing a query that does not exist.
- **`created_at`** as a second column: measured above, no benefit for the
  current queries.
- **`users.email`**: login looks users up by email, but that belongs to SEC-10,
  a correctness issue with a unique constraint, and not to these per-user todo
  queries. It is left out of this change.

**When to revisit.** If SEC-13 is fixed and the list query gains
`ORDER BY created_at DESC` with `LIMIT`, it becomes query E. The composite
index then earns its size, and should replace `ix_todos_user_id` rather than
be added next to it. The composite also serves `user_id = $1` through its
leading column, so keeping both would only double the write cost.

---

## 7. Trade-offs

### Write latency — measured

A 100,000-row `INSERT ... SELECT` was run inside a transaction and rolled
back, 3 times for each state. `todos_pkey` was present in every state.

| Indexes on `todos` besides the primary key | Runs (ms) | Median | vs none |
|---|---|---|---|
| none | 1944.0 · 1969.9 · 2175.9 | 1969.9 ms | — |
| `(user_id)` | 2107.1 · 2147.8 · 2212.9 | 2147.8 ms | **+9.0%** |
| `(user_id, created_at DESC)` | 2318.7 · 2407.3 · 2593.0 | 2407.3 ms | +22.2% |

Every insert, and every update that changes `user_id`, now also maintains this
index. For this workload that costs about 9% on bulk inserts. A single-row
insert pays the same per-row maintenance, too small to see against network and
application latency. Updates that do not touch `user_id` can often avoid the
index entirely through heap-only tuple updates, but that was not measured.

The rolled-back inserts left about 900,000 dead tuples. `VACUUM` truncated the
heap back to 213 MB, but `todos_pkey` had grown from 37 MB to 72 MB, and was
restored with `REINDEX INDEX todos_pkey` (now 30 MB). The primary key is not
used by any benchmarked query.

### Storage

`ix_todos_user_id` is **7,096 kB** on 1,000,000 rows, about 3% of the 213 MB
heap, and about 7 bytes per row thanks to deduplication. It grows roughly
linearly with row count. It stays small only while each user owns many rows.
If most users had one todo each, deduplication would have little to compress.

### Read performance

Per-user reads went from a full-table scan to reading only the pages that hold
that user's rows. The cost now scales with the user's own todo count, not with
the size of the table. That is the property that matters as the table grows.
The before/after table in §5 has the figures.

### Migration safety on a large table

- **`CONCURRENTLY` is used.** A plain `CREATE INDEX` holds a `SHARE` lock, which
  blocks every `INSERT`, `UPDATE` and `DELETE` on `todos` for the whole build.
  `CREATE INDEX CONCURRENTLY` takes a `SHARE UPDATE EXCLUSIVE` lock instead,
  and writes continue. It costs more total work — two passes over the table and
  a wait for in-flight transactions — so it takes longer than a plain build.
  The plain build took 325 ms here; the concurrent build was not timed
  separately.
- **It cannot run inside a transaction.** `alembic/env.py` runs migrations in
  one, so the statement is wrapped in `op.get_context().autocommit_block()`.
  The generated SQL, from `alembic upgrade --sql`, confirms the placement:
  ```
  BEGIN;  -- Running upgrade a0790c76a129 -> a5ac6aec37c4
  COMMIT;
  CREATE INDEX CONCURRENTLY ix_todos_user_id ON todos (user_id);
  BEGIN;  UPDATE alembic_version SET version_num='a5ac6aec37c4' ...;  COMMIT;
  ```
- **A failed concurrent build leaves an `INVALID` index behind.** The fix is
  `DROP INDEX CONCURRENTLY ix_todos_user_id`, then a retry. The migration file
  says so. After this migration, `pg_index` showed no invalid indexes.
- **The backend runs `alembic upgrade head` at startup** (`backend/Dockerfile`).
  On a large production table, a long index build at startup delays the
  backend becoming ready. For a real deployment this migration is better run
  as a separate, supervised step before the new version starts.
- **The image must contain the migration.** Startup runs the migrations that
  are baked into the image. The image built before this change did not
  contain revision `a5ac6aec37c4`, and would have failed to start against the
  migrated database. It was rebuilt.
- **The downgrade was exercised.** `alembic downgrade -1` dropped the index
  concurrently, and `alembic upgrade head` recreated it. Both succeeded
  against the 1M-row table.

---

## 8. Reproduction

```bash
# 1. Stack up (reads REDIS_PASSWORD and JWT_SECRET from .env)
docker compose up -d

# 2. The seed refuses to add todos if any exist. Clear todos only.
docker compose exec -T postgres psql -U fabbi -d postgres -c "TRUNCATE TABLE todos;"

# 3. Seed
docker compose exec -e SEED_USERS=10000 -e SEED_TODOS=1000000 -e DB_ECHO=false \
  backend python -m app.db.seed

# 4. Fresh statistics and visibility map
docker compose exec -T postgres psql -U fabbi -d postgres -c "VACUUM ANALYZE todos;"

# 5. Pick the benchmark user: the lowest user_id among users with the median count
docker compose exec -T postgres psql -U fabbi -d postgres -tA -c "
  WITH c AS (SELECT user_id, count(*) n FROM todos GROUP BY user_id)
  SELECT user_id FROM c
  WHERE n = (SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY n) FROM c)
  ORDER BY user_id LIMIT 1;"

# 6. Measure. Repeat each query 7 times; this is query C.
U=<user_id from step 5>
for i in 1 2 3 4 5 6 7; do
  docker compose exec -T postgres psql -U fabbi -d postgres -c \
    "EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM todos WHERE user_id = '$U';" \
    | grep -E "Execution Time|Planning Time"
done

# 7. Apply the index, refresh statistics, and repeat step 6
docker compose exec backend alembic upgrade head
docker compose exec -T postgres psql -U fabbi -d postgres -c "VACUUM ANALYZE todos;"
```

The seed uses random data, so a fresh run produces a different dataset and a
different benchmark user. The shape of the results is what should reproduce;
the exact figures will not. The runs above were collected by a small script
that looped step 6 for all queries and saved each `FORMAT JSON` plan. It was
not committed.

---

## 9. Scope notes

- **SEC-13 was deliberately not changed.** The application's list query still
  has no `ORDER BY`. Query B was benchmarked as an analysis query, as the
  rubric asks, not because the application sends it. Adding an `ORDER BY`
  changes what users see, and it is its own change.
- **No application behaviour changed.** The only application-code change is
  `index=True` on `Todo.user_id`, so the model matches the migrated schema.
  That flag affects DDL only; queries are unchanged.
- **Every measurement ran on exactly 10,000 users and 1,000,000 todos.** The
  counts were confirmed before the BEFORE runs; the write-overhead inserts
  were rolled back; the downgrade and re-upgrade changed no rows.
- **The development database no longer matches those counts exactly.** The
  Playwright regression run after the benchmark registered 3 users and created
  2 todos, leaving 10,003 and 1,000,002. The benchmark user still has 100
  todos. The earlier 41 todos were backed up before truncation, and are not
  in the database.
