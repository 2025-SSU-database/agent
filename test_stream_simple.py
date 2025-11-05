"""
간단한 스트리밍 테스트 - 서버 로그와 함께 확인
"""
import requests
import json
import time

def test_stream():
    url = "http://localhost:8000/agent/stream"
    message = "안녕하세요, 간단한 인사입니다"
    
    print(f"🚀 테스트 시작: {message}")
    print(f"📡 요청 URL: {url}")
    print("-" * 80)
    
    start_time = time.time()
    
    try:
        response = requests.post(
            url,
            json={"message": message},
            stream=True,
            timeout=60
        )
        
        print(f"✅ 연결 성공 (응답 코드: {response.status_code})")
        print(f"📋 헤더: {dict(response.headers)}")
        print("-" * 80)
        print("\n🔄 스트림 수신 중...\n")
        
        event_count = 0
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                elapsed = time.time() - start_time
                
                print(f"[{elapsed:.2f}s] 수신: {line_str[:100]}")
                
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    
                    if data_str == '[DONE]':
                        print(f"\n✅ 스트림 완료 (총 {event_count}개 이벤트, {elapsed:.2f}초)")
                        break
                    
                    try:
                        data = json.loads(data_str)
                        event_count += 1
                        
                        print(f"  📦 이벤트 #{event_count}")
                        print(f"     타입: {data.get('event_type')}")
                        print(f"     노드: {data.get('node')}")
                        
                        if 'message' in data:
                            msg = data['message']
                            content = msg.get('content', '')[:100]
                            print(f"     메시지: [{msg.get('type')}] {content}")
                        
                        print()
                        
                    except json.JSONDecodeError as e:
                        print(f"  ❌ JSON 파싱 실패: {e}")
        
        if event_count == 0:
            print("\n⚠️  경고: 이벤트를 받지 못했습니다!")
            print("   서버 로그를 확인하세요.")
                        
    except requests.exceptions.Timeout:
        print("❌ 타임아웃 발생")
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다.")
        print("   python src/main.py 로 서버를 먼저 실행하세요.")
    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("스트리밍 테스트 (디버그 모드)")
    print("=" * 80 + "\n")
    
    test_stream()
    
    print("\n" + "=" * 80)
    print("💡 팁:")
    print("  - 서버 터미널에서 로그(🚀, 📦, 📤)를 확인하세요")
    print("  - 이벤트가 안 보이면 그래프 구조를 확인하세요")
    print("=" * 80 + "\n")

