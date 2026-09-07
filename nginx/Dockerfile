FROM nginx:alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3

COPY ./default.conf /etc/nginx/templates/default.conf.template
COPY ./certs /certs

RUN mkdir -p /vol/static && \
    chmod 755 /vol/static && \
    mkdir -p /vol/media && \
    chmod 755 /vol/media
