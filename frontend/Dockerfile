FROM nginx:alpine

ARG HARBOR_GIT_SHA=unknown
ARG HARBOR_BUILD_TIME=unknown

LABEL org.opencontainers.image.title="Harbor Frontend" \
    org.opencontainers.image.version="0.1.0" \
    org.opencontainers.image.revision="${HARBOR_GIT_SHA}" \
    org.opencontainers.image.created="${HARBOR_BUILD_TIME}"

ENV HARBOR_GIT_SHA="${HARBOR_GIT_SHA}" \
    HARBOR_BUILD_TIME="${HARBOR_BUILD_TIME}"

COPY dist/ /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY docker-entrypoint.d/ /docker-entrypoint.d/
