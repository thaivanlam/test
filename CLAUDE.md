# CLAUDE.md — Fabbi Developer Assessment

## Bối cảnh

Đây là bài Developer Assessment. Yêu cầu đầy đủ nằm ở README.md (Tier 1-4).
Mục tiêu là đạt điểm theo rubric, không phải "làm cho code đẹp nhất có thể".

## Stack

- Backend: FastAPI + SQLAlchemy 2.0 async + asyncpg + PostgreSQL 16 + Redis 7
  + Alembic + Pydantic v2. Luồng: api/v1 -> services -> models.
- Frontend: React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui
  + TanStack Query v5 + react-hook-form + Zod + React Router v7 + axios.
- Lint backend: black (line-length 88), flake8 (max-line-length 120).
- Frontend theo cấu trúc feature-based: src/features/<feature>/{api,components,schemas,hooks}

## Chạy app

```bash
docker compose up --build       # frontend :3000, backend :8000, docs :8000/docs
docker compose exec backend python -m app.db.seed
```

Demo: demo@test.com / Demo@123

LƯU Ý: Docker Desktop phải đang chạy. Máy local chỉ có Python 3.14
(dự án target 3.12) nên LUÔN chạy backend và pytest trong container.

## Chạy test

```bash
docker compose exec backend pytest tests/ -v     # ưu tiên cách này
cd backend && pytest tests/ -v                   # chỉ khi có venv Python 3.12
cd e2e && npx playwright test                    # sau khi setup Tier 2B
```

Test backend dùng SQLite (sqlite+aiosqlite) và Redis mock trong tests/conftest.py.

## Quy ước commit

Conventional Commits, type thuộc: feat, fix, docs, style, refactor, perf,
test, build, ci, chore, revert.

Scope dùng trong repo này: auth, todos, cache, e2e, docker, db, docs.

Ví dụ: `fix(auth): enforce token expiration in verify_token`

LƯU Ý: chưa có husky hook nên commitlint không tự chạy — phải tự giữ đúng format.

## Quy tắc làm việc

1. Mỗi fix hoặc mỗi mục tiêu là MỘT commit riêng. Không gộp nhiều fix vào một commit.
2. Không sửa file nằm ngoài phạm vi được yêu cầu. Thấy vấn đề khác thì báo,
   không tự sửa.
3. Không tự ý làm sang Tier tiếp theo khi chưa được yêu cầu.
4. Không tự tạo commit khi chưa được yêu cầu rõ ràng.
5. Khi báo "đã xong", phải kèm output thật của lệnh đã chạy. Không ước lượng
   hay bịa số liệu benchmark / kết quả test.
6. Với Tier 1: viết test tái hiện lỗi (fail) TRƯỚC, rồi mới sửa.
7. Ghi lại prompt đã dùng vào docs/AI_USAGE.md (đề bài bắt buộc disclose AI).

## Bẫy đã biết trong repo

- .gitignore ban đầu từng ignore toàn bộ `docs/`. Trên branch assessment này rule đó
  ĐÃ ĐƯỢC GỠ để commit được các tài liệu bắt buộc (docs/TODO_SHARING_SPEC.md,
  docs/TEST_PLAN.md, docs/AI_USAGE.md).
- `docs/ANSWER_KEY.md` VẪN được ignore và phải giữ nguyên như vậy — đây là answer key
  của người chấm, không được commit.
- `.env` vẫn đang bị Git track (dòng `# .env` trong .gitignore bị comment) và CHƯA
  được xử lý. Để dành làm finding cho Tier 1 audit.
- Chưa có .dockerignore cho cả backend lẫn frontend (thuộc Tier 3B).
