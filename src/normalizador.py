"""
Converte a extração bruta em um formato único, independente de como as colunas
foram nomeadas no arquivo de origem.

Saída: lista de dicionários com as chaves
    trilho, prefixo, servico, tipo, origem, destino, inicio, fim, duracao_min
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

APELIDOS_COLUNA = {
    # trilho_nome vem primeiro: é a posição na malha, que é o que agrupa o
    # trilho. veiculo fica no fim, como último recurso, porque agrupar por
    # carro não é a mesma coisa que agrupar por posição.
    "trilho": ["trilho_nome", "trilho", "posicao", "posição", "grade",
               "linha_trilho", "carro", "veiculo", "veículo"],
    "prefixo": ["prefixo", "veiculo", "veículo", "numero_carro", "frota",
                "veiculo_prefixo"],
    "servico": ["servico", "serviço", "numero", "número", "codigo", "código",
                "id_servico", "numero_servico", "atividade"],
    "tipo": ["tipo", "tipo_atividade", "classificacao", "classificação", "natureza"],
    "origem": ["origem", "local_origem", "partida", "ponto_origem", "de", "sai_de"],
    "destino": ["destino", "local_destino", "chegada", "ponto_destino", "para", "vai_para"],
    "data": ["data", "data_operacao", "data_operação", "dtoper", "dia"],
    "inicio": ["inicio", "início", "hora", "hora_inicio", "hora_início",
               "horario_inicio", "horário_início", "partida_hora", "hora_partida"],
    "fim": ["fim", "hora_fim", "termino", "término", "horario_fim", "horário_fim",
            "chegada_hora", "hora_chegada"],
    "duracao": ["duracao", "duração", "duracao_min", "tempo", "tempo_min"],
}

OBRIGATORIAS = ["trilho", "origem", "destino", "inicio"]


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _chave(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _sem_acento(str(texto)).lower()).strip("_")


def carregar_bruto(caminho: Path) -> pd.DataFrame:
    sufixo = caminho.suffix.lower()
    if sufixo in (".xlsx", ".xlsm"):
        return pd.read_excel(caminho, dtype=str)
    if sufixo == ".xls":
        return _ler_xls(caminho)
    if sufixo == ".csv":
        for sep in (",", ";", "\t"):
            df = pd.read_csv(caminho, dtype=str, sep=sep, encoding="utf-8-sig")
            if df.shape[1] > 1:
                return df
        return pd.read_csv(caminho, dtype=str, encoding="utf-8-sig")
    if sufixo == ".json":
        with open(caminho, encoding="utf-8") as arquivo:
            return pd.DataFrame(json.load(arquivo))
    raise ValueError(f"Formato não suportado: {sufixo}")


def _ler_xls(caminho: Path) -> pd.DataFrame:
    """Lê o BIFF antigo que o SIGLA exporta.

    Vai direto no xlrd em vez de passar pelo pandas por um motivo só: o arquivo
    do SIGLA tem inconsistência de OLE2, inofensiva, e o xlrd anuncia isso
    escrevendo no logfile que ele fixa como sys.stdout no momento do import.
    Redirecionar a saída depois não adianta. Passando o logfile na mão o aviso
    morre de forma previsível.
    """
    import io

    import xlrd

    livro = xlrd.open_workbook(str(caminho), logfile=io.StringIO())
    try:
        aba = livro.sheet_by_index(0)
        linhas = [
            [_celula_xls(aba.cell(i, j), livro.datemode) for j in range(aba.ncols)]
            for i in range(aba.nrows)
        ]
    finally:
        livro.release_resources()

    if not linhas:
        return pd.DataFrame()
    cabecalho = [str(c).strip() for c in linhas[0]]
    return pd.DataFrame(linhas[1:], columns=cabecalho, dtype=object).astype(object)


def _celula_xls(celula, datemode) -> str:
    """Devolve texto, convertendo data serial do Excel e tirando o .0 dos inteiros."""
    import xlrd

    if celula.ctype == xlrd.XL_CELL_DATE:
        return str(xlrd.xldate.xldate_as_datetime(celula.value, datemode))
    if celula.ctype == xlrd.XL_CELL_NUMBER:
        valor = celula.value
        return str(int(valor)) if float(valor).is_integer() else str(valor)
    if celula.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return ""
    return str(celula.value)


def mapear_colunas(df: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    """Cada coluna do arquivo serve a um campo só.

    trilho e prefixo compartilham o apelido 'veiculo'. Sem exclusividade, um
    arquivo que só traga 'veiculo' faria os dois apontarem para a mesma coluna
    e o relatório repetiria o prefixo no lugar do trilho.
    """
    disponiveis = {_chave(c): c for c in df.columns}
    mapa: dict[str, str] = {}
    usadas: set[str] = set()
    for campo, apelidos in APELIDOS_COLUNA.items():
        for apelido in apelidos:
            chave = _chave(apelido)
            if chave in disponiveis and disponiveis[chave] not in usadas:
                mapa[campo] = disponiveis[chave]
                usadas.add(disponiveis[chave])
                break
    faltando = [c for c in OBRIGATORIAS if c not in mapa]
    return mapa, faltando


def _texto(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() in ("nan", "none", "nat") else texto


def _local(valor) -> str:
    return _sem_acento(_texto(valor)).upper()


def _para_minutos(valor) -> float | None:
    """Aceita '02:30', '2:30:00', '150', '150 min'."""
    texto = _texto(valor)
    if not texto:
        return None
    if ":" in texto:
        partes = [p for p in texto.split(":") if p.strip() != ""]
        try:
            numeros = [int(float(p)) for p in partes]
        except ValueError:
            return None
        if len(numeros) >= 3:
            return numeros[0] * 60 + numeros[1] + numeros[2] / 60
        if len(numeros) == 2:
            return numeros[0] * 60 + numeros[1]
        return float(numeros[0])
    achado = re.search(r"-?\d+(?:[.,]\d+)?", texto)
    return float(achado.group(0).replace(",", ".")) if achado else None


def _para_datahora(data_base: datetime | None, valor) -> datetime | None:
    texto = _texto(valor)
    if not texto:
        return None

    # Já vem com data completa
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            pass

    # Só hora, combina com a data base
    achado = re.match(r"^\s*(\d{1,2})[:h](\d{2})(?::(\d{2}))?", texto)
    if achado and data_base:
        hora, minuto = int(achado.group(1)), int(achado.group(2))
        segundo = int(achado.group(3) or 0)
        dias_extras, hora = divmod(hora, 24)  # aceita 25:30 como dia seguinte
        return data_base.replace(hour=hora, minute=minuto, second=segundo,
                                 microsecond=0) + timedelta(days=dias_extras)
    return None


def _data_base(mapa: dict[str, str], linha, padrao: datetime | None) -> datetime | None:
    if "data" in mapa:
        bruto = _texto(linha[mapa["data"]])
        for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(bruto[:10], formato)
            except ValueError:
                continue
    return padrao


def normalizar(df: pd.DataFrame, mapa: dict[str, str],
               data_padrao: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """Devolve (registros válidos, registros descartados com o motivo)."""
    validos: list[dict] = []
    descartados: list[dict] = []

    for indice, linha in df.iterrows():
        base = _data_base(mapa, linha, data_padrao)
        inicio = _para_datahora(base, linha[mapa["inicio"]]) if "inicio" in mapa else None
        fim = _para_datahora(base, linha[mapa["fim"]]) if "fim" in mapa else None
        duracao = _para_minutos(linha[mapa["duracao"]]) if "duracao" in mapa else None

        if inicio and not fim and duracao:
            fim = inicio + timedelta(minutes=duracao)
        if inicio and fim and fim < inicio:
            # Serviço que vira o dia. Empurra até ficar coerente.
            tentativas = 0
            while fim < inicio and tentativas < 3:
                fim += timedelta(days=1)
                tentativas += 1
        if inicio and fim and duracao is None:
            duracao = (fim - inicio).total_seconds() / 60

        registro = {
            "linha_origem": int(indice) + 2,
            "trilho": _texto(linha[mapa["trilho"]]) if "trilho" in mapa else "",
            "prefixo": _texto(linha[mapa["prefixo"]]) if "prefixo" in mapa else "",
            "servico": _texto(linha[mapa["servico"]]) if "servico" in mapa else "",
            "tipo": _local(linha[mapa["tipo"]]) if "tipo" in mapa else "",
            "origem": _local(linha[mapa["origem"]]) if "origem" in mapa else "",
            "destino": _local(linha[mapa["destino"]]) if "destino" in mapa else "",
            "inicio": inicio,
            "fim": fim,
            "duracao_min": duracao,
        }

        faltas = [campo for campo in ("trilho", "origem", "destino") if not registro[campo]]
        if registro["inicio"] is None:
            faltas.append("inicio")
        if faltas:
            registro["motivo"] = "sem " + ", ".join(faltas)
            descartados.append(registro)
        else:
            validos.append(registro)

    validos.sort(key=lambda r: (r["trilho"], r["inicio"]))
    return validos, descartados
