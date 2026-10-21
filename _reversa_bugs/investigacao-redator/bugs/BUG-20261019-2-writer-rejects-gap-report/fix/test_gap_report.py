"""Teste de reprodução e regressão para BUG-20261019-2 (rejeição incondicional de gap report)."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.pipeline.writer import _write_report, validate_report_quality
from app.models import Research, ResearchPoint, Evidence, ResearchStatus


@pytest.fixture
def mock_research():
    research = MagicMock(spec=Research)
    research.id = "test-research-id"
    research.theme = "Tema de teste"
    return research


@pytest.fixture
def mock_points():
    point = MagicMock(spec=ResearchPoint)
    point.id = "point-1"
    point.title = "Ponto 1"
    point.status = "blocked"
    point.audit = "Bloqueado"
    return [point]


class TestGapReport:
    """Testes para relatório de lacuna sem evidence."""

    @pytest.mark.asyncio
    async def test_gap_report_sem_evidence_persiste(self, mock_research, mock_points, monkeypatch):
        """Gap report sem evidence deve persistir com report_type=gap, não RuntimeError."""
        async def fake_complete(role, system, user, db):
            if role == "writer":
                return (
                    "# Relatório de Lacuna\n\n"
                    "## Visão Geral\n"
                    "Nenhuma evidência foi coletada para esta pesquisa. "
                    "Os pontos de pesquisa foram bloqueados pela auditoria. "
                    "Este relatório documenta a ausência de dados disponíveis."
                )
            return ""

        monkeypatch.setattr("app.services.pipeline.writer.complete", fake_complete)

        # Mock DB session
        mock_db = AsyncMock()
        mock_db.scalars.return_value.all.return_value = []  # evidence vazia
        mock_db.get.return_value = mock_research
        mock_research.status = ResearchStatus.DONE.value

        # Deve persistir sem erro
        await _write_report(mock_research, mock_points)

        # Verificar que report foi adicionado com gap flag
        added_report = None
        for call in mock_db.add.call_args_list:
            if hasattr(call[0][0], '__class__') and 'Report' in str(call[0][0].__class__):
                added_report = call[0][0]
                break

        assert added_report is not None, "Report deve ser persistido"
        assert added_report.citation_metrics.get("report_type") == "gap"

    @pytest.mark.asyncio
    async def test_gap_report_sem_evidence_rejeitado_por_stub(self, mock_research, mock_points, monkeypatch):
        """Gap report muito curto continua rejeitado por validate_report_quality."""
        async def fake_complete(role, system, user, db):
            if role == "writer":
                return "# Relatório\nCurto."  # < 200 palavras
            return ""

        monkeypatch.setattr("app.services.pipeline.writer.complete", fake_complete)

        mock_db = AsyncMock()
        mock_db.scalars.return_value.all.return_value = []

        with pytest.raises(ValueError, match="incomplete"):
            await _write_report(mock_research, mock_points)

    @pytest.mark.asyncio
    async def test_report_com_evidence_sem_links_sinalizado(self, mock_research, mock_points, monkeypatch):
        """Com evidence mas sem links no texto -> gap flag, não RuntimeError."""
        async def fake_complete(role, system, user, db):
            if role == "writer":
                return (
                    "# Relatório\n\n"
                    "## Ponto 1\n"
                    "O texto discute o tema mas não cita fontes."
                )  # sem links markdown
            return ""

        monkeypatch.setattr("app.services.pipeline.writer.complete", fake_complete)

        # Mock evidence não-vazia
        mock_evidence = MagicMock(spec=Evidence)
        mock_evidence.research_point_id = "point-1"
        mock_evidence.persona = "historian"
        mock_evidence.claim = "Claim test"
        mock_evidence.excerpt = "Excerpt test"
        mock_evidence.source_url = "https://example.com/source"
        mock_evidence.analysis = "Analysis test"

        mock_db = AsyncMock()
        mock_db.scalars.return_value.all.return_value = [mock_evidence]
        mock_db.get.return_value = mock_research
        mock_research.status = ResearchStatus.DONE.value

        await _write_report(mock_research, mock_points)

        added_report = None
        for call in mock_db.add.call_args_list:
            if hasattr(call[0][0], '__class__') and 'Report' in str(call[0][0].__class__):
                added_report = call[0][0]
                break

        assert added_report is not None
        # Deve ter gap flag, não erro
        assert added_report.citation_metrics.get("gap_report") is True


class TestUnlinkedUrlsStillRejected:
    """URLs não pertencentes à evidence continuam rejeitadas."""

    @pytest.mark.asyncio
    async def test_unlinked_urls_still_rejected(self, mock_research, mock_points, monkeypatch):
        """URL no texto que não está em evidence -> RuntimeError mantido."""
        async def fake_complete(role, system, user, db):
            if role == "writer":
                return (
                    "# Relatório\n\n"
                    "## Ponto 1\n"
                    "Fato inventado [fonte falsa](https://fake.com/inventado)."
                )
            return ""

        monkeypatch.setattr("app.services.pipeline.writer.complete", fake_complete)

        mock_evidence = MagicMock(spec=Evidence)
        mock_evidence.research_point_id = "point-1"
        mock_evidence.persona = "historian"
        mock_evidence.claim = "Claim test"
        mock_evidence.excerpt = "Excerpt test"
        mock_evidence.source_url = "https://example.com/real"
        mock_evidence.analysis = "Analysis test"

        mock_db = AsyncMock()
        mock_db.scalars.return_value.all.return_value = [mock_evidence]
        mock_db.get.return_value = mock_research

        with pytest.raises(RuntimeError, match="uncollected citation URLs"):
            await _write_report(mock_research, mock_points)