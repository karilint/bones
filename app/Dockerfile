FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/user/.local/bin:$PATH

WORKDIR /src/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gcc g++ gnupg unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home user \
    && mkdir -p /vol/web/static /vol/web/media \
    && chown -R user:user /vol /src/app \
    && chmod 755 /vol/web /vol/web/static \
    && chmod 750 /vol/web/media

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

COPY --chown=user:user . /src/app

USER user

CMD ["sh", "./scripts/entrypoint.sh"]
