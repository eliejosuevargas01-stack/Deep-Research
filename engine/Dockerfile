# Motor Hermes isolado: perfil deep-research + plugin por_papel + API interna.
# Base :latest porque a tag 0.22.5 nao existe no registry (verificado via
# `docker image inspect`, que retorna "No such image").
# fastapi/uvicorn/ruamel ja vem na imagem; service.py usa shim yaml->ruamel.
FROM nousresearch/hermes-agent:latest

USER root
COPY --chown=hermes:hermes hermes_home/profiles/deep-research /opt/data/profiles/deep-research
COPY --chown=hermes:hermes hermes_home/plugins/delegation/por_papel /opt/data/plugins/delegation/por_papel
COPY --chown=hermes:hermes hermes_home/plugins/delegation/por_papel /opt/data/plugins/por_papel
COPY --chown=hermes:hermes hermes_home/plugins/delegation/por_papel /opt/hermes/plugins/delegation/por_papel
COPY engine/service.py engine/entrypoint.sh /app/engine/
# Semente para volumes vazios (o entrypoint copia se faltar).
COPY hermes_home/profiles/deep-research /app/seed/profile
COPY hermes_home/plugins/delegation/por_papel /app/seed/plugin
RUN chmod +x /app/engine/entrypoint.sh \
 && mkdir -p /workspaces \
 && chown -R hermes:hermes /app/engine /app/seed /workspaces /opt/data/profiles /opt/data/plugins

USER hermes
EXPOSE 8100
ENTRYPOINT ["/app/engine/entrypoint.sh"]
