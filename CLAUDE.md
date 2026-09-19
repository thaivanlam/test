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
docker compose up -d --build    # frontend :3000, backend :8000, docs :8000/docs
docker compose exec backend python -m app.db.seed
```

Demo: demo@test.com / Demo@123

LƯU Ý: Docker Desktop phải đang chạy. Máy local chỉ có Python 3.14
(dự án target 3.12) nên LUÔN chạy backend và pytest trong container.

Hành vi hiện tại của `docker-compose.yml` (từ Tier 3B):

- **Secret lấy từ môi trường.** Compose đọc `REDIS_PASSWORD` và `JWT_SECRET`
  từ `.env` ở thư mục gốc. Thiếu một trong hai thì `docker compose` dừng ngay
  với lỗi `required variable ... is missing a value`. Không có giá trị secret
  nào viết trong `docker-compose.yml`.
- **Healthcheck + thứ tự khởi động.** Postgres (`pg_isready -h localhost`) và
  Redis (`redis-cli ping`) có healthcheck; backend chỉ start khi cả hai
  `service_healthy`. Cold boot không còn crash — KHÔNG cần restart backend thủ
  công nữa.
- **Redis có mật khẩu** (`--requirepass`) và chỉ bind `127.0.0.1:6379`. Từ máy
  host: `docker compose exec redis redis-cli ...` (đã có `REDISCLI_AUTH` sẵn
  trong container). Backend kết nối qua `REDIS_URL` có kèm mật khẩu.
- **Frontend chạy bằng nginx:alpine**, vẫn ở port 3000, có SPA fallback về
  `index.html`. `VITE_API_URL` được nướng vào bundle LÚC BUILD (đọc từ
  `frontend/.env`) — khối `environment:` của frontend trong compose KHÔNG có
  tác dụng lúc runtime. Đổi URL API = phải build lại image.

## Chạy test

```bash
# Backend — hai cách, khác nhau ở chỗ lấy code từ đâu:
docker compose exec backend pytest tests/ -v     # dùng code ĐÃ BUILD trong image
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \
  -v "D:/Project/Fabbi_Developer_Assessment/backend:/app" \
  backend pytest tests/ -v                       # dùng source hiện tại (mount)
cd backend && pytest tests/ -v                   # chỉ khi có venv Python 3.12

# E2E — cần stack đang chạy; Playwright KHÔNG tự start stack
cd e2e && npm install && npx playwright install chromium   # lần đầu
cd e2e && npx playwright test                    # headless
cd e2e && npx playwright test --headed           # headed
```

Sửa code backend rồi test bằng `exec` sẽ chạy code CŨ cho tới khi build lại
image — dùng cách mount khi đang sửa code.

Test backend dùng SQLite (sqlite+aiosqlite) và `FakeRedis` (dict có trạng thái,
giữ dữ liệu giữa các request) trong tests/conftest.py — không đụng Redis thật.

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
- `.env` vẫn đang bị Git track (dòng `# .env` trong .gitignore bị comment) — SEC-08,
  CHƯA fix. Từ Tier 3B file này còn chứa thêm placeholder `REDIS_PASSWORD` (chủ ý,
  để stack chạy bằng một lệnh). Mật khẩu Postgres vẫn viết thẳng trong
  `docker-compose.yml`. KHÔNG `git rm --cached .env` khi chưa được yêu cầu.
- `.dockerignore` đã có (Tier 3B). Backend cố ý GIỮ `tests/` trong image (để
  `docker compose exec backend pytest` chạy được); frontend cố ý GIỮ `.env`
  (build cần `VITE_API_URL`).
- Redis image khai báo `VOLUME /data` → anonymous volume, Compose DÙNG LẠI khi
  recreate container. Key cũ có thể sống sót qua restart — đừng dùng "đếm số
  key" làm bằng chứng; kiểm tra đúng key cụ thể.
- Cold boot chỉ lỗi khi Postgres khởi động chậm (rõ nhất: volume mới, phải
  initdb). Muốn test lại cold boot thì dùng project tạm
  `docker compose -p <tên-tạm> ...` với volume riêng — KHÔNG `down -v` stack thật.
- KHÔNG chạy `docker volume prune`: máy này còn project Docker khác (techzone-*).
