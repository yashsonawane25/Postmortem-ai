FROM python:3.11-alpine

WORKDIR /app

# psutil needs gcc and python3-dev to compile on alpine
RUN apk add --no-cache gcc musl-dev python3-dev linux-headers

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

CMD ["python", "-u", "agent.py"]
