"""Estado do pipeline precisa refletir a etapa em curso, não só o fim dela."""
import pytest

from app.core import hermes_adapter


class RepoFake:
    def __init__(self, falhar=False):
        self.chamadas = []
        self.falhar = falhar

    async def update_pipeline_status(self, id_pesquisa, status):
        if self.falhar:
            raise RuntimeError("banco indisponível")
        self.chamadas.append((id_pesquisa, status))


@pytest.mark.asyncio
@pytest.mark.parametrize("etapa", ["buscando", "auditando", "redigindo"])
async def test_marca_etapa_em_curso(etapa):
    repo = RepoFake()
    await hermes_adapter.marcar_inicio_etapa(repo, "pesq-1", etapa)
    assert repo.chamadas == [("pesq-1", etapa)]


@pytest.mark.asyncio
async def test_etapa_invalida_nao_persiste():
    repo = RepoFake()
    with pytest.raises(ValueError):
        await hermes_adapter.marcar_inicio_etapa(repo, "pesq-1", "concluido")
    assert repo.chamadas == []


@pytest.mark.asyncio
async def test_falha_de_banco_nao_interrompe_etapa():
    repo = RepoFake(falhar=True)
    await hermes_adapter.marcar_inicio_etapa(repo, "pesq-1", "buscando")
    assert repo.chamadas == []
