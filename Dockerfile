# 1. Base image
FROM python:3.12-slim

# 2. Environment metadata (required values, no defaults)
ENV OCTOPUSAPIKEY=""
ENV OCTOPUSAPIURL=""
ENV PORT="5000"
ENV OCTOPUSCACHE_TTL="300"

LABEL org.opencontainers.image.title="Octopus Agile Flask App"
LABEL org.opencontainers.image.description="Fetches Octopus Agile electricity rates and exposes slot-based endpoints. Requires OCTOPUSAPIKEY and OCTOPUSAPIURL. Optional PORT (default 5000) and OCTOPUSCACHE_TTL (default 300)."

# 3. Copy files
COPY ./app/ /src

# 4. Install dependencies
RUN pip install --upgrade pip
RUN pip install -r /src/requirements.txt

# 5. Expose port
EXPOSE 5000

# 6. Run the app
CMD ["python", "/src/octopusagile.py"]
