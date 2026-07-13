FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install UV
ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod +x /install.sh && /install.sh && rm /install.sh
ENV PATH="/root/.local/bin:${PATH}"

# --- CHANGEMENT MAJEUR ICI ---
# On définit où UV doit créer le venv (Hors du dossier projet)
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"

WORKDIR /project

COPY ../MS-Admin/pyproject.toml uv.lock .env ./

# UV va maintenant installer dans /opt/venv
RUN uv sync

COPY ../MS-Admin/app ./app

# On ajoute le nouveau chemin au PATH
ENV PATH="/opt/venv/bin:${PATH}"

EXPOSE 80

# On lance uvicorn simplement (il sera trouvé grâce au PATH)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]