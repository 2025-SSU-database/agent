#!/bin/bash

# 테스트 실행 스크립트
# 사용법: ./run_tests.sh [옵션]

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 스크립트 디렉토리로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 기본값 설정
TEST_CASES_FILE="test_cases.json"
OUTPUT_FILE=""
QUIET=false
PYTHON_CMD="python3"

# 도움말 함수
show_help() {
    echo -e "${BLUE}테스트 실행 스크립트${NC}"
    echo ""
    echo "사용법: $0 [옵션]"
    echo ""
    echo "옵션:"
    echo "  -f, --file FILE        테스트 케이스 JSON 파일 경로 (기본값: test_cases.json)"
    echo "  -o, --output FILE      테스트 결과를 저장할 JSON 파일 경로"
    echo "  -q, --quiet            상세 출력 비활성화"
    echo "  -p, --python CMD       Python 명령어 (기본값: python3)"
    echo "  -h, --help             이 도움말 표시"
    echo ""
    echo "예시:"
    echo "  $0                                    # 기본 테스트 실행"
    echo "  $0 -f my_tests.json                  # 특정 테스트 파일 사용"
    echo "  $0 -o results.json                   # 결과 저장"
    echo "  $0 -f my_tests.json -o results.json  # 테스트 파일 지정 및 결과 저장"
    echo "  $0 -q                                 # 조용한 모드"
    echo ""
}

# 인자 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--file)
            TEST_CASES_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        -p|--python)
            PYTHON_CMD="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}알 수 없는 옵션: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Python 명령어 확인
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo -e "${RED}오류: $PYTHON_CMD 명령어를 찾을 수 없습니다.${NC}"
    echo "Python이 설치되어 있는지 확인하세요."
    exit 1
fi

# Python 버전 확인
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "${BLUE}Python 버전: $PYTHON_VERSION${NC}"

# 테스트 케이스 파일 확인
if [ ! -f "$TEST_CASES_FILE" ]; then
    echo -e "${RED}오류: 테스트 케이스 파일을 찾을 수 없습니다: $TEST_CASES_FILE${NC}"
    echo "test_cases.json 파일이 존재하는지 확인하세요."
    exit 1
fi

echo -e "${GREEN}테스트 케이스 파일: $TEST_CASES_FILE${NC}"

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}경고: .env 파일이 없습니다. 환경 변수가 설정되지 않았을 수 있습니다.${NC}"
fi

# 명령어 구성
CMD="$PYTHON_CMD test.py --test-cases \"$TEST_CASES_FILE\""

if [ -n "$OUTPUT_FILE" ]; then
    CMD="$CMD --output \"$OUTPUT_FILE\""
fi

if [ "$QUIET" = true ]; then
    CMD="$CMD --quiet"
fi

# 테스트 실행
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}테스트 실행 중...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

eval $CMD

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}테스트 완료!${NC}"
    echo -e "${GREEN}========================================${NC}"
    if [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
        echo -e "${GREEN}결과 파일: $OUTPUT_FILE${NC}"
    fi
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}테스트 실패 (종료 코드: $EXIT_CODE)${NC}"
    echo -e "${RED}========================================${NC}"
fi

exit $EXIT_CODE

