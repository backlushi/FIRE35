FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# Сначала ставим CPU-only torch (иначе pip тянет CUDA ~3GB)
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .

RUN mkdir -p /root/fire35

COPY start.sh .
RUN sed -i 's/\r//' start.sh && chmod +x start.sh

CMD ["./start.sh"]
