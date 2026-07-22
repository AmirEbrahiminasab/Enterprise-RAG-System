FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cu124

RUN pip install elasticsearch==8.12.0

RUN pip install httpx[socks]

COPY PySocks-1.7.1.tar.gz .
RUN pip install ./PySocks-1.7.1.tar.gz

COPY . .

EXPOSE 8585