# Expense Notion Record Agent

영수증/지출 파이프라인 중 `Notion 기록`만 담당하는 모듈이다.

`notion_api.py`는 FastAPI 테스트용 진입점이고, 실제 Notion payload 생성과 API 호출은 아래 파일들로 분리되어 있다.

- `notion_models.py`: Notion 기록에 사용할 `ExpenseRecord` 모델
- `notion_payload.py`: `ExpenseRecord`를 Notion database payload로 변환
- `notion_client.py`: Notion API 호출
- `notion_config.py`: `.env`에서 실행 설정 로드
- `env_healthcheck.py`: OpenAI / Notion 키 검증

## 1. 백엔드 폴더로 이동

반드시 `ReceiptMngAgentProject/backend` 폴더에서 실행한다.

```bash
cd /Users/shinsaebom/EDA/LangGraph/GITHUB/ReceiptMngAgentProject/backend
```

## 2. 가상환경 활성화

팀 공통 Anaconda 환경을 사용하는 경우:

```bash
conda activate ml_env
```

가상환경이 없다면 아래처럼 `backend/.venv`를 만들어 사용할 수도 있다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

`python -m notion...` 명령이 어느 폴더에서든 동작하게 하려면 한 번은 editable 설치를 실행한다.

```bash
python -m pip install -e .
```

## 3. 환경변수 확인

`ReceiptMngAgentProject/backend/.env` 또는 `ReceiptMngAgentProject/.env`에 아래 값이 있어야 한다.

```env
OPENAI_API_KEY=...
NOTION_TOKEN=...
NOTION_DATABASE_URL=https://...notion.site/...
```

`NOTION_DATABASE_URL` 대신 `NOTION_DATABASE_ID`를 직접 넣어도 된다.

Notion database는 Notion Integration에 공유되어 있어야 한다. 공유가 안 되어 있으면 토큰이 맞아도 기록이 실패한다.

## 4. 키 검증

서버를 띄우기 전에 OpenAI / Notion 키와 database id를 먼저 확인한다.

```bash
python -m notion.env_healthcheck
```

정상 예시:

```text
[OK] OpenAI API key가 유효합니다.
[OK] Notion token이 유효합니다.
[OK] NOTION_DATABASE_URL/ID에서 database_id를 확인했습니다.
```

## 5. FastAPI 서버 실행

Swagger UI로 테스트하려면 서버를 실행한다.

```bash
python -m uvicorn notion_api:app --reload
```

브라우저에서 접속:

```text
http://127.0.0.1:8000/docs
```

만약 `Address already in use`가 나오면 8000번 포트를 이미 다른 서버가 쓰는 상태다. 이때는 다른 포트로 실행한다.

```bash
python -m uvicorn notion_api:app --reload --port 8001
```

브라우저 접속 주소도 포트에 맞춰 바꾼다.

```text
http://127.0.0.1:8001/docs
```

## 6. Swagger에서 기록 테스트

Swagger 화면에서 아래 순서대로 실행한다.

1. `GET /health/keys`
   - OpenAI / Notion 키가 정상인지 확인한다.
2. `POST /notion/test-record`
   - 샘플 지출 데이터 1건을 실제 Notion database에 기록한다.

성공하면 응답에 `ok: true`, `message: "Notion 페이지 생성 완료"`, `page_url`이 나온다.

## 7. 터미널에서 바로 기록 테스트

FastAPI를 띄우지 않고 샘플 데이터 1건만 바로 기록하려면 아래 명령을 실행한다.

```bash
python -m notion_record_agent
```

성공 예시:

```text
'ok': True
'message': 'Notion 페이지 생성 완료'
'page_url': 'https://app.notion.com/...'
```

## 입력 데이터 구조

`ExpenseRecord`에 아래 값이 들어온다.

- `id`: 지출 항목 고유 식별자
- `user_id`: 사용자 식별자
- `spent_at`: 지출일자
- `merchant`: 상점명
- `amount`: 지출금액
- `payment_method`: 결제수단
- `category`: 소비 카테고리
- `memo`: 사용자 메모 또는 OCR 요약
- `source`: 입력 경로
- `budget_status`: 예산평가결과
- `notion_sync_status`: 노션기록결과
- `addr`: 주소
- `tel`: 전화번호
- `reg_date`: 등록일시
- 'user_id' : notion url 매핑 id

## Notion DB 매핑

현재 Notion database 속성명 기준으로 기록한다.

| 코드 필드 | Notion 속성명 | Notion 타입 |
|---|---|---|
| `id` | `지출 항목 고유 식별자` | `title` |
| `spent_at` | `지출날짜` | `date` |
| `merchant` | `상점명` | `rich_text` |
| `amount` | `지출 금액` | `number` |
| `payment_method` | `결제수단` | `select` |
| `category` | `소비 카테고리` | `select` |
| `source` | `입력 경로` | `rich_text` |
| `budget_status` | `예산 평가 결과` | `multi_select` |
| `notion_sync_status` | `Notion 기록 결과` | `multi_select` |
| `addr` | `주소` | `rich_text` |
| `tel` | `전화번호` | `rich_text` |
| `reg_date` | `등록일시` | `rich_text` |
| `memo` 기반 요약 | `OCR 원문 요약` | `rich_text` |

## 자주 나는 에러

### `ModuleNotFoundError: No module named 'notion'`

`backend` 폴더 밖에서 실행했거나 editable 설치가 안 된 경우다.

```bash
cd /Users/shinsaebom/EDA/LangGraph/GITHUB/ReceiptMngAgentProject/backend
python -m pip install -e .
python -m notion.env_healthcheck
```

### `Address already in use`

8000번 포트를 이미 다른 서버가 쓰는 상태다.

```bash
python -m uvicorn notion.notion_api:app --reload --port 8001
```

### Notion 기록 실패

아래 항목을 확인한다.

- `.env`에 `NOTION_TOKEN`이 있는지
- `.env`에 `NOTION_DATABASE_URL` 또는 `NOTION_DATABASE_ID`가 있는지
- Notion database가 Integration에 공유되어 있는지
- Notion database 속성명이 README의 매핑표와 정확히 같은지

## 비고

- 이 폴더는 Notion 기록 전용 모듈이다.
- OCR, 텍스트 분석, 카테고리 분류, 예산평가 코드는 `ExpenseGraph` 또는 backend main pipeline에서 담당한다.
