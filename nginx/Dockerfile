FROM nginx:alpine@sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d

COPY ./default.conf /etc/nginx/templates/default.conf.template
COPY ./certs /certs

RUN mkdir -p /vol/static && \
    chmod 755 /vol/static && \
    mkdir -p /vol/media && \
    chmod 755 /vol/media
