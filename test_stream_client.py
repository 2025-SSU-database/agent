"""
FastAPI 스트리밍 엔드포인트 테스트 클라이언트
"""
import requests
import json


def test_streaming_endpoint():
    """스트리밍 엔드포인트 테스트"""
    url = "http://localhost:8000/agent/stream"
    
    # 테스트 메시지들
    test_messages = [
        "스포티파이 클론 프로젝트, 팀원: 1, 5, 기간: 오늘부터 3개월",
        "마케팅 캠페인 프로젝트, 팀원: 영업팀, 디자인팀, 기간: 2주",
        "안녕하세요, 파이썬에 대해 설명해주세요"
    ]
    
    for test_message in test_messages:
        print(f"\n{'='*80}")
        print(f"테스트 메시지: {test_message}")
        print(f"{'='*80}\n")
        
        # POST 요청 (스트리밍)
        response = requests.post(
            url,
            json={"message": test_message},
            stream=True,  # 스트리밍 모드
            headers={"Content-Type": "application/json"}
        )
        
        # 스트림 데이터 읽기
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # SSE 형식 파싱
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # 'data: ' 제거
                    
                    if data_str == '[DONE]':
                        print("\n✅ [스트림 종료]")
                        break
                    
                    try:
                        data = json.loads(data_str)
                        
                        # 이벤트 타입별 처리
                        if data.get('event_type') == 'error':
                            print(f"❌ [ERROR]: {data.get('error')}")
                            if 'traceback' in data:
                                print(f"Traceback:\n{data['traceback']}")
                        elif data.get('event_type') == 'node_update':
                            print(f"\n🔄 [노드 실행: {data.get('node')}]")
                            if 'request_type' in data:
                                print(f"  📋 분류: {data['request_type']}")
                            if 'message' in data:
                                msg = data['message']
                                print(f"  💬 [{msg.get('type')}]: {msg.get('content')}")
                        else:
                            # 레거시 형식
                            print(f"[{data.get('type', 'Unknown')}]: {data.get('content', data)}")
                    except json.JSONDecodeError:
                        print(f"❌ 파싱 실패: {data_str}")
        
        print("\n")


def test_normal_endpoint():
    """일반 엔드포인트 테스트 (스트리밍 없음)"""
    url = "http://localhost:8000/agent"
    
    test_message = "안녕하세요, 파이썬에 대해 설명해주세요"
    
    print(f"\n{'='*80}")
    print(f"일반 엔드포인트 테스트")
    print(f"메시지: {test_message}")
    print(f"{'='*80}\n")
    
    response = requests.post(
        url,
        json={"message": test_message},
        headers={"Content-Type": "application/json"}
    )
    
    result = response.json()
    print(f"[{result.get('type', 'Unknown')}]: {result.get('content', result)}")
    print("\n")


if __name__ == "__main__":
    print("\n🚀 FastAPI 스트리밍 클라이언트 테스트\n")
    
    # 서버가 실행 중인지 확인
    try:
        requests.get("http://localhost:8000/")
    except requests.exceptions.ConnectionError:
        print("❌ 서버가 실행 중이지 않습니다.")
        print("다음 명령으로 서버를 시작하세요:")
        print("  python src/main.py")
        exit(1)
    
    print("✅ 서버 연결 확인\n")
    
    # 테스트 실행
    choice = input("테스트 선택 (1: 스트리밍, 2: 일반, 3: 둘 다): ")
    
    if choice == "1":
        test_streaming_endpoint()
    elif choice == "2":
        test_normal_endpoint()
    elif choice == "3":
        test_streaming_endpoint()
        test_normal_endpoint()
    else:
        print("잘못된 선택입니다.")

