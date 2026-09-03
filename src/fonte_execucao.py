"""
Adaptador do relatório execucao do SIGLA.

O SIGLA exporta a malha em texto, com uma linha por escala de motorista. Este
módulo transforma esse arquivo no mesmo formato de colunas que o normalizador
espera, fazendo três coisas que a fonte exige:

  1. Deduplicar. O grão é a escala do motorista, não a viagem. Rendição e dupla
     tripulação geram uma linha por motorista para a mesma viagem.
  2. Recortar a janela. O arquivo cobre do dia alvo menos três até o fim da
     malha publicada. Só interessam as viagens que cruzam a janela pedida, que
     quem chama define. Hoje é de 24 horas contadas da hora de corte, e não até
     23:59 do dia: assim a análise da madrugada olha para as 24 horas seguintes
     em vez de sobrar meia hora de malha.
  3. Descartar veículo que não é veículo. SIMULTANEO, TURISMO, CANCELAD.*,
     N ABRIR* e vazio são marcadores, não carros, e sem carro não dá para
     encadear trilho.

Horário: usa sempre as colunas Prevista. As colunas Realizada só vêm
preenchidas em cerca de um terço das linhas e descrevem o que aconteceu, não a
malha publicada, que é o que se quer conferir.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

# Colunas que identificam o formato. Todas precisam existir.
ASSINATURA = ("Data Operação", "Partida Prevista", "Chegada Prevista", "Tipo Serviço")

# Uma viagem é única por esta combinação. O que sobra é linha de motorista.
CHAVE_VIAGEM = [
    "Data Operação",
    "Serviço",
    "Veículo",
    "Partida Prevista",
    "Chegada Prevista",
    "Origem",
    "Destino",
]

# Marcadores que aparecem no lugar do número do carro, casados por igualdade.
VEICULOS_MARCADORES = {"", "SIMULTANEO", "TURISMO"}

# Estes variam no fim do texto, então casam por início. O sufixo do CANCELAD
# acompanha a empresa (CANCELAD.U, CANCELAD.R, CANCELAD.S, CANCELAD.F) e o
# N ABRIR traz um sequencial (N ABRIR01, N ABRIR72).
VEICULOS_PREFIXOS = ("CANCELAD", "N ABRIR")

# A coluna Frota é o sinal autoritativo destes dois. No arquivo de 02/09/2026 as
# 118 linhas com Frota CANCELADO e as 59 com NAO ABRIR são exatamente as que
# trazem o marcador no Veículo, e nenhum carro real usa essas frotas.
FROTAS_MARCADORAS = {"CANCELADO", "NAO ABRIR"}

# De -> para. O que não está aqui é ignorado pelo normalizador.
RENOMEAR = {
    "Veículo": "trilho",
    "Frota": "prefixo",
    "Serviço": "servico",
    "Tipo Serviço": "tipo",
    "Origem": "origem",
    "Destino": "destino",
    "Partida Prevista": "inicio",
    "Chegada Prevista": "fim",
    "Data Operação": "data",
    "Código Linha": "codigo_linha",
    "NOP": "empresa",
}


def _rotulo_marcador(veiculo: str, frota: str) -> str:
    """Nome do marcador para o resumo, agrupando as variações de sufixo."""
    for prefixo in VEICULOS_PREFIXOS:
        if veiculo.startswith(prefixo):
            return f"{prefixo}*"
    if frota in FROTAS_MARCADORAS:
        return frota
    return veiculo or "(vazio)"


def e_execucao(df: pd.DataFrame) -> bool:
    """Reconhece o relatório execucao pelas colunas."""
    return all(coluna in df.columns for coluna in ASSINATURA)


def _texto(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip()


def periodo(df: pd.DataFrame) -> tuple[datetime | None, datetime | None]:
    """Primeira e última partida prevista do arquivo."""
    partida = pd.to_datetime(df["Partida Prevista"], errors="coerce")
    if partida.notna().sum() == 0:
        return None, None
    return partida.min().to_pydatetime(), partida.max().to_pydatetime()


def preparar(df: pd.DataFrame, inicio_janela: datetime,
             fim_janela: datetime) -> tuple[pd.DataFrame, dict]:
    """Devolve (tabela pronta para o normalizador, relatório do que foi cortado).

    A janela é fechada no início e aberta no fim: `[inicio_janela, fim_janela)`.
    """
    bruto = df.copy()
    for coluna in bruto.columns:
        bruto[coluna] = _texto(bruto[coluna])

    total = len(bruto)

    viagens = bruto.drop_duplicates(subset=CHAVE_VIAGEM)
    linhas_de_motorista = total - len(viagens)

    partida = pd.to_datetime(viagens["Partida Prevista"], errors="coerce")
    chegada = pd.to_datetime(viagens["Chegada Prevista"], errors="coerce")

    abre = pd.Timestamp(inicio_janela)
    fecha = pd.Timestamp(fim_janela)

    # Uma viagem interessa se qualquer parte dela cai dentro da janela. Isso
    # inclui a que começou antes e ainda está rodando, que é justamente o motivo
    # de o arquivo pedir três dias para trás.
    cruza = (partida < fecha) & (chegada >= abre)
    sem_horario = partida.isna() | chegada.isna()

    na_janela = viagens[cruza & ~sem_horario]
    fora_da_janela = int((~cruza & ~sem_horario).sum())
    horario_ilegivel = int(sem_horario.sum())

    veiculo = _texto(na_janela["Veículo"]).str.upper()
    if "Frota" in na_janela.columns:
        frota = _texto(na_janela["Frota"]).str.upper()
    else:
        frota = pd.Series("", index=na_janela.index, dtype="object")

    marcador = (
        veiculo.isin(VEICULOS_MARCADORES)
        | veiculo.str.startswith(VEICULOS_PREFIXOS)
        | frota.isin(FROTAS_MARCADORAS)
    )
    real = ~marcador
    rotulos = [
        _rotulo_marcador(v, f)
        for v, f in zip(veiculo[marcador], frota[marcador])
    ]
    marcadores = pd.Series(rotulos, dtype="object").value_counts().to_dict()

    pronto = na_janela[real].rename(columns=RENOMEAR)

    corte = {
        "linhas_no_arquivo": total,
        "linhas_de_motorista": linhas_de_motorista,
        "viagens": len(viagens),
        "fora_da_janela": fora_da_janela,
        "horario_ilegivel": horario_ilegivel,
        "veiculo_marcador": marcadores,
        "viagens_na_janela": len(pronto),
        "janela_inicio": abre.to_pydatetime(),
        "janela_fim": fecha.to_pydatetime(),
    }
    return pronto.reset_index(drop=True), corte


def resumir_corte(corte: dict) -> list[str]:
    """Linhas de texto para o main.py mostrar o que entrou e o que ficou de fora."""
    linhas = [
        f"{corte['linhas_no_arquivo']} linhas no arquivo, "
        f"{corte['viagens']} viagens depois de juntar as escalas de motorista "
        f"({corte['linhas_de_motorista']} linhas eram do mesmo carro na mesma viagem)",
        f"Janela {corte['janela_inicio']:%d/%m %H:%M} a "
        f"{corte['janela_fim']:%d/%m %H:%M}: "
        f"{corte['viagens_na_janela']} viagens cruzam",
        f"Fora da janela: {corte['fora_da_janela']} viagem(ns)",
    ]
    if corte["horario_ilegivel"]:
        linhas.append(
            f"Sem horário legível: {corte['horario_ilegivel']} viagem(ns)"
        )
    if corte["veiculo_marcador"]:
        detalhe = ", ".join(
            f"{k} {v}" for k, v in corte["veiculo_marcador"].items()
        )
        linhas.append(
            "Descartadas por não ter veículo real: "
            f"{sum(corte['veiculo_marcador'].values())} ({detalhe})"
        )
    return linhas
