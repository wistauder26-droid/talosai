FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY talos ./talos
RUN pip install --no-cache-dir .
VOLUME /app/data
CMD ["talos-telegram"]
