"""Modelos ORM relacionais com SQLAlchemy 2.0.

Define as tabelas pesquisa, pontos, conteudo_coletado e credenciais,
com chaves estrangeiras com CASCADE, índices de desempenho e restrições de unicidade.
Atende a RF-02, RF-05, RF-12 e DT-02.
"""

from typing import List, Optional
from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Classe base declarativa para os modelos SQLAlchemy."""
    pass


class Pesquisa(Base):
    """Raiz do ciclo investigativo no pipeline."""

    __tablename__ = "pesquisa"

    id_pesquisa: Mapped[str] = mapped_column(String(36), primary_key=True)
    tema: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[str] = mapped_column(String(30), nullable=False)
    dossier_final: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning_dossier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    concluido_em: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    webhook_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    webhook_resposta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_pipeline: Mapped[str] = mapped_column(String(30), nullable=False, default="planejado", server_default="planejado")
    erro_pipeline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relacionamentos com deleção em cascata
    pontos: Mapped[List["Ponto"]] = relationship(
        "Ponto",
        back_populates="pesquisa",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    conteudos: Mapped[List["ConteudoColetado"]] = relationship(
        "ConteudoColetado",
        back_populates="pesquisa",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_pesquisa_criado_em", desc("criado_em")),
    )


class Ponto(Base):
    """Eixo focal de investigação gerado pelo planejador."""

    __tablename__ = "pontos"

    ponto_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_pesquisa: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pesquisa.id_pesquisa", ondelete="CASCADE"),
        nullable=False,
    )
    tema: Mapped[str] = mapped_column(Text, nullable=False)
    ponto_n: Mapped[int] = mapped_column(Integer, nullable=False)
    ponto: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    pontos_fracos: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning_planejamento: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning_auditoria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tentativas_auditoria: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criado_em: Mapped[str] = mapped_column(String(30), nullable=False)
    atualizado_em: Mapped[str] = mapped_column(String(30), nullable=False)

    pesquisa: Mapped["Pesquisa"] = relationship("Pesquisa", back_populates="pontos")
    conteudos: Mapped[List["ConteudoColetado"]] = relationship(
        "ConteudoColetado",
        back_populates="ponto_rel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("id_pesquisa", "ponto_n", name="uq_pesquisa_ponto_n"),
        Index("idx_pontos_id_pesquisa_status", "id_pesquisa", "status"),
    )


class ConteudoColetado(Base):
    """Conteúdo integral raspado na web pelas personas analíticas por rodada de investigação."""

    __tablename__ = "conteudo_coletado"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_pesquisa: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pesquisa.id_pesquisa", ondelete="CASCADE"),
        nullable=False,
    )
    ponto_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pontos.ponto_id", ondelete="CASCADE"),
        nullable=False,
    )
    rodada: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tema: Mapped[str] = mapped_column(Text, nullable=False)
    ponto: Mapped[str] = mapped_column(Text, nullable=False)
    conteudo_coletado: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_coleta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    urls_lidas: Mapped[str] = mapped_column(Text, nullable=False)
    urls_fonte: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[str] = mapped_column(String(30), nullable=False)

    pesquisa: Mapped["Pesquisa"] = relationship("Pesquisa", back_populates="conteudos")
    ponto_rel: Mapped["Ponto"] = relationship("Ponto", back_populates="conteudos")

    __table_args__ = (
        UniqueConstraint("id_pesquisa", "ponto_id", "rodada", name="uq_conteudo_ponto_rodada"),
        Index("idx_conteudo_id_pesquisa", "id_pesquisa"),
    )


class Credencial(Base):
    """Armazenamento de credenciais e parâmetros cifrados em repouso."""

    __tablename__ = "credenciais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    valor_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # llm, jina, webhook, parametro
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    atualizado_em: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        Index("idx_credenciais_chave", "chave"),
    )

# ponytail: campos de auditoria de usuário (created_by) podem ser adicionados se autenticação multiusuário for exigida
