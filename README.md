# 🤖 Senior Agent - Multi-Agent System with FastAPI

LangGraph 기반의 멀티 에이전트 시스템을 FastAPI와 스트리밍 방식으로 연결한 프로젝트입니다.

## 🚀 빠른 시작

### 로컬 실행

```bash
# 1. 의존성 설치
uv sync
# 또는
pip install -e .

# 2. 환경 변수 설정
echo "OPENAI_API_KEY=your_key_here" > .env

# 3. 서버 실행
python src/main.py

# 4. 테스트 (별도 터미널)
python test_stream_client.py
# 또는 브라우저에서 test_stream_client.html 열기
```

### Docker 실행

```bash
# 1. 환경 변수 설정 (.env 파일 필요)
echo "OPENAI_API_KEY=your_key_here" > .env

# 2. Docker Compose로 실행
docker-compose up --build

# 3. 테스트 (로컬 머신에서)
python test_stream_client.py
# 또는 브라우저에서 test_stream_client.html 열기
```

**✅ Docker로 실행해도 테스트 클라이언트는 로컬에서 사용 가능합니다!**

Docker는 API 서버만 실행하고, 로컬 머신의 8000번 포트로 매핑되므로 `http://localhost:8000`으로 접근할 수 있습니다.

---

## 📡 API 엔드포인트

### 스트리밍 (권장)
```bash
POST http://localhost:8000/agent/stream
{
  "message": "스포티파이 클론 프로젝트, 팀원: 1, 5, 기간: 오늘부터 3개월"
}
```

### 일반 응답
```bash
POST http://localhost:8000/agent
{
  "message": "안녕하세요"
}
```

---

## 🏗️ 시스템 구조

```
사용자 요청
    ↓
Classifier (분류)
    ├─→ IT Scrum Agent (IT 프로젝트 백로그)
    ├─→ General Scrum Agent (일반 프로젝트 백로그)
    └─→ Assistant Agent (일반 대화)
    ↓
스트리밍 응답
```

---

## 📚 문서

- **[API 사용 가이드](./API_USAGE.md)**: 상세한 API 문서 및 클라이언트 예제
- **[Docker 가이드](./DOCKER_GUIDE.md)**: Docker 실행 및 네트워크 설정

---

## 🧪 테스트 도구

1. **`test_stream_client.py`**: Python 기반 CLI 테스트 클라이언트
2. **`test_stream_client.html`**: 웹 브라우저 기반 UI 테스트 클라이언트
3. **cURL**: 커맨드라인 테스트

---

## 🔧 기술 스택

- **FastAPI**: 고성능 웹 프레임워크
- **LangGraph**: 멀티 에이전트 오케스트레이션
- **LangChain**: LLM 애플리케이션 프레임워크
- **OpenAI GPT-4**: 언어 모델
- **Server-Sent Events (SSE)**: 실시간 스트리밍

---

## 📂 프로젝트 구조

```
agent/
├── src/
│   ├── main.py                  # FastAPI 서버 & 스트리밍 엔드포인트
│   ├── agents/
│   │   ├── main.py              # LangGraph 메인 그래프
│   │   ├── classifier.py        # 요청 분류 에이전트
│   │   ├── assistant/           # 일반 어시스턴트
│   │   └── scrum/
│   │       ├── it/              # IT 스크럼 에이전트
│   │       └── general/         # 일반 스크럼 에이전트
│   └── models/
│       └── state.py             # 상태 모델
├── test_stream_client.py        # Python 테스트 클라이언트
├── test_stream_client.html      # HTML 테스트 클라이언트
├── Dockerfile                   # Docker 이미지 정의
├── docker-compose.yml           # Docker Compose 설정
└── pyproject.toml               # 프로젝트 의존성
```

---

## ⚙️ 환경 변수

`.env` 파일에 다음 환경 변수를 설정하세요:

```bash
OPENAI_API_KEY=your_openai_api_key
```

---

## 📝 사용 예시

### Python

```python
import requests
import json

def stream_agent(message):
    response = requests.post(
        "http://localhost:8000/agent/stream",
        json={"message": message},
        stream=True
    )
    
    for line in response.iter_lines():
        if line and line.startswith(b'data: '):
            data = json.loads(line[6:].decode('utf-8'))
            print(data)
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/agent/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: '안녕하세요' })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  console.log(chunk);
}
```

---

## 🤝 기여

프로젝트에 기여하시려면 Pull Request를 보내주세요!

---

## 📄 라이선스

MIT License

