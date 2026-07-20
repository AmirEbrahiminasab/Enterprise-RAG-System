FROM python:3.12-slim


WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN pip install python-multipart pypdf

RUN pip install "passlib[bcrypt]" "python-jose[cryptography]" python-multipart "pydantic[email]"

COPY . .

EXPOSE 8585