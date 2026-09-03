"""
Encontra a extração bruta mais recente e copia para dados_trabalho.

Critério, nesta ordem:
  1. maior data de operação encontrada no nome do arquivo
  2. maior número de versão, lida do sufixo _v2 no nome ou da pasta vN que o
     extrator cria em saida/DD-MM-AAAA/vN/
  3. formato mais confiável entre os que saem da mesma execução: xlsx, xlsm,
     csv, json, nessa ordem
  4. maior data de modificação, para desempatar

Arquivos auxiliares que casam com o mesmo prefixo, como o _descartados.csv,
são ignorados.

O arquivo original nunca é alterado. Só a cópia é usada.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import arquivos

EXTENSOES = (".xlsx", ".xlsm", ".xls", ".csv", ".json")

# 21-05-2026, 21_05_2026, 21052026, 2026-05-21
PADROES_DATA = [
    (re.compile(r"(\d{2})[-_.](\d{2})[-_.](\d{4})"), ("d", "m", "a")),
    (re.compile(r"(\d{4})[-_.](\d{2})[-_.](\d{2})"), ("a", "m", "d")),
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)"), ("d", "m", "a")),
]

PADRAO_VERSAO = re.compile(r"[_-]v(\d+)", re.IGNORECASE)

# O extrator grava em saida/DD-MM-AAAA/vN/, então a versão real está na pasta.
PADRAO_VERSAO_PASTA = re.compile(r"^v(\d+)$", re.IGNORECASE)

# Casam com o prefixo do relatório mas não são o relatório.
SUFIXOS_IGNORADOS = ("_descartados",)

# Mesma execução gera xlsx, csv e json com o mesmo nome. O xlsx é o canônico.
PRIORIDADE_FORMATO = {".xlsx": 4, ".xlsm": 3, ".xls": 2, ".csv": 1, ".json": 0}


@dataclass
class Extracao:
    caminho: Path
    data_operacao: datetime | None
    versao: int
    modificado_em: datetime

    @property
    def rotulo_data(self) -> str:
        if self.data_operacao:
            return self.data_operacao.strftime("%d/%m/%Y")
        return "data não identificada"

    def chave_ordem(self):
        # Arquivos sem data no nome ficam atrás dos que têm.
        data = self.data_operacao or datetime.min
        formato = PRIORIDADE_FORMATO.get(self.caminho.suffix.lower(), -1)
        return (data, self.versao, formato, self.modificado_em)


def _extrair_data(nome: str) -> datetime | None:
    for padrao, ordem in PADROES_DATA:
        achado = padrao.search(nome)
        if not achado:
            continue
        partes = dict(zip(ordem, achado.groups()))
        try:
            return datetime(int(partes["a"]), int(partes["m"]), int(partes["d"]))
        except ValueError:
            continue
    return None


def _extrair_versao(nome: str) -> int:
    achado = PADRAO_VERSAO.search(nome)
    return int(achado.group(1)) if achado else 1


def _versao_da_pasta(caminho: Path) -> int:
    """Lê a versão da pasta vN que o extrator cria acima do arquivo."""
    for pai in caminho.parents:
        achado = PADRAO_VERSAO_PASTA.match(pai.name)
        if achado:
            return int(achado.group(1))
    return 1


def _e_auxiliar(caminho: Path) -> bool:
    nome = caminho.stem.lower()
    return any(nome.endswith(sufixo) for sufixo in SUFIXOS_IGNORADOS)


def listar_extracoes(pasta: Path, prefixo: str = "") -> list[Extracao]:
    if not pasta.exists():
        raise FileNotFoundError(f"Pasta de extrações não encontrada: {pasta}")

    encontrados: list[Extracao] = []
    for caminho in pasta.rglob("*"):
        if not caminho.is_file() or caminho.suffix.lower() not in EXTENSOES:
            continue
        if caminho.name.startswith("~$"):  # temporário do Excel
            continue
        if prefixo and not caminho.name.lower().startswith(prefixo.lower()):
            continue
        if _e_auxiliar(caminho):
            continue
        encontrados.append(
            Extracao(
                caminho=caminho,
                data_operacao=_extrair_data(caminho.name),
                versao=max(_extrair_versao(caminho.name),
                           _versao_da_pasta(caminho)),
                modificado_em=datetime.fromtimestamp(caminho.stat().st_mtime),
            )
        )
    return encontrados


def escolher_mais_recente(pasta: Path, prefixo: str = "") -> Extracao:
    candidatos = listar_extracoes(pasta, prefixo)
    if not candidatos:
        raise FileNotFoundError(
            f"Nenhuma extração ({', '.join(EXTENSOES)}) encontrada em {pasta}"
        )
    return max(candidatos, key=lambda e: e.chave_ordem())


def copiar_para_trabalho(extracao: Extracao, pasta_trabalho: Path) -> Path:
    """Copia a extração escolhida preservando o original.

    Nome fixo, uma cópia por dia de operação, sobrescrita a cada execução. Era
    com carimbo de hora, e rodando a cada 10 minutos isso acumulava 144 cópias
    por dia de um arquivo de 5,6 MB dentro de uma pasta do OneDrive. A cópia
    passa por `arquivos.copiar`, que publica de forma atômica.
    """
    if extracao.data_operacao:
        subpasta = pasta_trabalho / extracao.data_operacao.strftime("%Y-%m-%d")
    else:
        subpasta = pasta_trabalho / "sem-data"

    return arquivos.copiar(extracao.caminho, subpasta / extracao.caminho.name)
