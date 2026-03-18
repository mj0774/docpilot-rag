# DocPilot-RAG

PDF 문서를 업로드하면 텍스트를 추출하고, 임베딩 기반 검색을 통해 질문에 답변하는 RAG(Retrieval-Augmented Generation) 프로젝트입니다.

단순 챗봇이 아니라 문서 업로드 -> 검색 -> 답변 생성 -> 출처 제공까지 이어지는 RAG 파이프라인을 end-to-end로 직접 구현했습니다.

또한 retrieval 품질 개선을 위해 Similarity Search와 MMR(Maximal Marginal Relevance)를 비교하는 실험을 수행했습니다.

## 핵심 기능

- PDF 업로드 및 저장
- PyMuPDF 기반 텍스트 추출
- 슬라이딩 윈도우 청킹 (800 / 160)
- OpenAI Embedding 생성
- ChromaDB 벡터 저장
- 질문 기반 Retrieval
- GPT 기반 답변 생성
- 답변과 함께 출처 snippet / 페이지 제공

## 시스템 아키텍처

```text
PDF Upload
   ↓
Text Extraction (PyMuPDF)
   ↓
Chunking (800 / 160)
   ↓
Embedding (text-embedding-3-small)
   ↓
ChromaDB

User Question
   ↓
Query Embedding
   ↓
Retrieval (MMR, k=5)
   ↓
GPT Answer Generation (gpt-4o-mini)
   ↓
Answer + Sources
```

## 기술 스택

### Backend
- FastAPI

### Frontend
- React
- TypeScript
- Vite
- Tailwind

### AI
- OpenAI API
- ChromaDB
- PyMuPDF

## Retrieval 개선 실험

단순 구현에 그치지 않고 retrieval 품질을 비교하기 위해 고정 질문셋 기반 실험 스크립트를 구현했습니다.

### 비교 방식

| 방식 | 설정 |
|---|---|
| Before | similarity search (k=3) |
| After | MMR retrieval (k=5) |

### 실행

```bash
cd backend
python scripts/compare_retrieval.py
```

### 결과

관찰된 변화:

- page 1 반복 출처 감소
- retrieval 결과 출처 다양성 증가

하지만:

- 정답률 개선은 제한적

이를 통해 retrieval 품질은 단순 검색 알고리즘 변경만으로 해결되지 않는다는 점을 확인했습니다.

## 트러블슈팅

### 1. 표지 / 목차 페이지 과매칭

문서 표지나 목차는 핵심 키워드를 많이 포함하기 때문에 실제 본문보다 retrieval 상위에 노출되는 문제가 발생했습니다.

### 2. Retrieval 다양성과 정확도의 Trade-off

MMR을 적용하면 중복 chunk는 줄지만 항상 정답률이 개선되는 것은 아니었습니다.

배운 점:

Retrieval은 아래 요소를 함께 고려해야 합니다.

- 검색 전략
- chunk 전략
- 문서 구조
- 문서 필터링

### 3. 다문서 환경에서의 Chunk 혼합 문제

현재 retrieval이 특정 문서 범위로 제한되지 않으면 여러 문서 chunk가 섞일 수 있습니다.

개선 계획:

- `/ask` 요청에 `file_id` 기반 retrieval 필터 적용

## 폴더 구조

```text
docpilot-rag/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ services/
│  │  ├─ schemas/
│  │  └─ main.py
│  ├─ data/
│  │  ├─ uploads/
│  │  └─ chroma/
│  ├─ scripts/
│  └─ requirements.txt
└─ frontend/
```

## 실행 방법

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 포트폴리오 포인트

이 프로젝트에서 중점적으로 구현한 부분:

- RAG 파이프라인 end-to-end 구현
- 문서 기반 QA 시스템 구조 설계
- Retrieval 품질 비교 실험 구성
- 답변 + 출처 제공 UX 구현

단순히 LLM 호출이 아니라 문서 처리 -> 검색 -> 생성 -> 근거 제공까지 이어지는 실제 서비스 구조를 구현했습니다.

## 향후 개선

- `file_id` 기반 retrieval 필터
- chunk 전략 개선
- 평가셋 확장
- citation UX 개선
