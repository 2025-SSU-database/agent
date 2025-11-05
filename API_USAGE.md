# FastAPI 스트리밍 Agent API 사용 가이드

## 🚀 시작하기

### 1. 의존성 설치

```bash
uv sync
# 또는
pip install -e .
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 OpenAI API 키를 설정하세요:

```bash
OPENAI_API_KEY=your_api_key_here
```

### 3. 서버 실행

```bash
python src/main.py
```

서버는 `http://localhost:8000`에서 실행됩니다.

---

## 📡 API 엔드포인트

### 1. 스트리밍 엔드포인트 (권장)

**POST** `/agent/stream`

실시간으로 Agent 응답을 스트리밍합니다 (Server-Sent Events 방식).

#### 요청

```json
{
  "message": "스포티파이 클론 프로젝트, 팀원: 1, 5, 기간: 오늘부터 3개월"
}
```

#### 응답 (SSE 스트림)

각 노드가 실행될 때마다 실시간으로 업데이트를 받습니다:

```
data: {"event_type": "node_update", "node": "classifier", "message": {"type": "HumanMessage", "content": "..."}}

data: {"event_type": "node_update", "node": "it_scrum_agent", "request_type": "it_scrum", "message": {"type": "AIMessage", "content": "백로그 생성 중..."}}

data: {"event_type": "node_update", "node": "it_scrum_agent", "message": {"type": "AIMessage", "content": "완성된 백로그..."}}

data: [DONE]
```

**이벤트 구조:**
- `event_type`: `"node_update"` (노드 실행) 또는 `"error"` (에러)
- `node`: 실행된 노드 이름 (예: "classifier", "it_scrum_agent")
- `request_type`: 분류 결과 (있는 경우)
- `message`: 메시지 내용 (있는 경우)
  - `type`: 메시지 타입 (예: "HumanMessage", "AIMessage")
  - `content`: 메시지 내용

### 2. 일반 엔드포인트

**POST** `/agent`

전통적인 방식으로 완료된 응답만 반환합니다.

#### 요청

```json
{
  "message": "안녕하세요"
}
```

#### 응답

```json
{
  "type": "AIMessage",
  "content": "안녕하세요! 무엇을 도와드릴까요?"
}
```

---

## 🧪 테스트 방법

### Python 클라이언트

```bash
python test_stream_client.py
```

### 웹 브라우저

1. `test_stream_client.html`을 브라우저에서 엽니다
2. 메시지를 입력하고 "스트리밍 전송" 또는 "일반 전송" 버튼을 클릭합니다

### cURL

**스트리밍:**
```bash
curl -N -X POST http://localhost:8000/agent/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요"}'
```

**일반:**
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요"}'
```

---

## 💻 클라이언트 코드 예시

### JavaScript/TypeScript

```javascript
async function streamAgent(message) {
  const response = await fetch('http://localhost:8000/agent/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.substring(6);
        if (data === '[DONE]') {
          console.log('✅ 스트림 완료');
          continue;
        }
        
        const jsonData = JSON.parse(data);
        
        if (jsonData.event_type === 'node_update') {
          console.log(`🔄 노드: ${jsonData.node}`);
          if (jsonData.message) {
            console.log(`💬 ${jsonData.message.type}: ${jsonData.message.content}`);
          }
        } else if (jsonData.event_type === 'error') {
          console.error(`❌ 에러: ${jsonData.error}`);
        }
      }
    }
  }
}
```

### Python

```python
import requests
import json

def stream_agent(message):
    url = "http://localhost:8000/agent/stream"
    response = requests.post(
        url,
        json={"message": message},
        stream=True
    )
    
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data_str = line_str[6:]
                if data_str == '[DONE]':
                    print("✅ 스트림 완료")
                    break
                
                data = json.loads(data_str)
                
                if data.get('event_type') == 'node_update':
                    print(f"🔄 노드: {data['node']}")
                    if 'message' in data:
                        msg = data['message']
                        print(f"💬 [{msg['type']}]: {msg['content']}")
                elif data.get('event_type') == 'error':
                    print(f"❌ 에러: {data['error']}")
```

---

## 🏗️ 아키텍처

```
사용자 요청
    ↓
FastAPI (/agent/stream)
    ↓
LangGraph (classifier)
    ├─→ IT Scrum Agent
    ├─→ General Scrum Agent
    └─→ General Assistant Agent
    ↓
스트리밍 응답 (SSE)
```

### Agent 분류

- **IT Scrum**: IT/개발 프로젝트 관련 스크럼 백로그 생성
- **General Scrum**: 일반 프로젝트 스크럼 백로그 생성
- **General Assistant**: 일반적인 질문/대화 처리

---

## 🔧 설정

### CORS 설정

기본적으로 모든 origin에서 접근 가능합니다. 프로덕션 환경에서는 `src/main.py`의 CORS 설정을 수정하세요:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 스트림 모드 설정

현재 `stream_mode="updates"`로 설정되어 **각 노드가 실행될 때마다** 업데이트를 받습니다.

다른 스트림 모드 옵션:

- `"updates"`: 각 노드의 변경사항만 반환 (현재 설정, 권장) ✅
  - 노드별로 실시간 진행 상황 확인 가능
  - 툴 사용이나 에이전트 전환 시점을 정확히 알 수 있음
  
- `"values"`: 매 업데이트마다 전체 state를 반환
  - 전체 상태를 매번 받아야 할 때 유용
  
- `"messages"`: 메시지만 반환
  - 메시지 내용만 필요할 때 사용
  
- `"debug"`: 디버깅을 위한 상세한 정보 포함
  - 개발 중 문제 해결 시 유용

**변경하려면** `src/main.py`의 `stream_mode` 파라미터를 수정:

```python
async for event in graph.astream(
    {"messages": [{"role": "user", "content": request.message}]},
    stream_mode="updates"  # "values", "messages", "debug" 등으로 변경 가능
):
    # ...
```

**노드별 스트리밍의 장점:**
- 🔄 실시간으로 어느 노드가 실행 중인지 확인
- 🎯 분류 결과를 즉시 확인
- 📊 각 에이전트의 작업 진행 상황 추적
- ⚡ 더 나은 사용자 경험 (진행 상황 표시)

---

## 📝 참고 사항

- SSE(Server-Sent Events)는 단방향 스트리밍입니다
- 양방향 실시간 통신이 필요하면 WebSocket 사용을 고려하세요
- 스트리밍은 긴 응답에 더 나은 사용자 경험을 제공합니다
- 에러 발생 시에도 스트림을 통해 에러 메시지가 전송됩니다

