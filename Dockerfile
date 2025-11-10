FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget && \
    rm -rf /var/lib/apt/lists/*

# 전체 소스 코드 복사
COPY pyproject.toml .
COPY src/ ./src/

# 의존성 설치
RUN pip install --no-cache-dir -e .

EXPOSE 8000

# 환경 변수로 OpenAI API 키 전달받음
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]