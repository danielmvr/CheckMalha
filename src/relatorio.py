"""
Monta o relatório HTML. Arquivo único, sem CDN, abre offline com duplo clique.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import arquivos

MODELO = Path(__file__).with_name("modelo.html")
CONFIG = Path(__file__).resolve().parent.parent / "config"

# Recorte do desenho, em minutos. Uma virada de 20 minutos é invisível quando a
# barra do serviço ao lado pode esticar por dias, e o eixo compartilhado por
# todos os trilhos fica tão largo que a régua de horas embaixo vira um borrão.
# Então cada serviço é desenhado só na vizinhança da virada: a última hora de
# quem chega e a primeira hora de quem parte. O texto da ocorrência, a dica do
# mouse e o CSV continuam com o horário cheio e correto.
RECORTE_MIN = 60


def _mapa_empresas() -> dict:
    """Config das empresas, com queda para vazio se o arquivo não existir."""
    try:
        with open(CONFIG / "empresas.json", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, ValueError):
        return {}


def _empresa(nome_trilho: str, servicos: list[dict], mapa: dict) -> str:
    """Empresa do trilho. O trilho é o carro, e o carro pertence a uma empresa.

    O sufixo do veículo manda, porque é atributo do carro. O prefixo do número
    do serviço é reserva, para veículo sem sufixo conhecido; ele erra quando um
    carro roda serviço de outra empresa, o que existe mas é minoria.
    """
    sufixo = nome_trilho.rsplit(".", 1)[-1].strip().upper() if "." in nome_trilho else ""
    por_sufixo = mapa.get("por_sufixo_veiculo", {})
    if sufixo in por_sufixo:
        return por_sufixo[sufixo]

    por_prefixo = mapa.get("por_prefixo_servico", {})
    for servico in servicos:
        numero = str(servico.get("servico") or "").strip()
        if len(numero) >= 2 and numero[:2] in por_prefixo:
            return por_prefixo[numero[:2]]
    return mapa.get("desconhecida", "OUTRAS")


def _hhmm(minutos: float | None) -> str:
    if minutos is None:
        return "-"
    total = int(round(abs(minutos)))
    horas, resto = divmod(total, 60)
    sinal = "-" if minutos < 0 else ""
    return f"{sinal}{horas}h{resto:02d}" if horas else f"{sinal}{resto}min"


def _relogio(momento: datetime | None) -> str:
    return momento.strftime("%d/%m %H:%M") if momento else "-"


def _juntar(pedacos: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Funde trechos que se tocam, para serviço curto sair como uma peça só."""
    ordenados = sorted(pedacos)
    juntos = [list(ordenados[0])]
    for inicio, fim in ordenados[1:]:
        if inicio <= juntos[-1][1]:
            juntos[-1][1] = max(juntos[-1][1], fim)
        else:
            juntos.append([inicio, fim])
    return [(a, b) for a, b in juntos]


def _trecho_na_janela(inicio: datetime, fim: datetime,
                      janela: tuple[datetime, datetime] | None,
                      recorte: timedelta) -> tuple[datetime, datetime]:
    """Serviço sem virada de nenhum lado: mostra o que cai dentro da janela.

    É o caso do bloco de manutenção que dura duas semanas. Recortar pela janela
    mantém a barra informativa sem arrastar o eixo para fora do que está sendo
    analisado. Antes o recorte era pelo dia alvo, o que passou a puxar o eixo
    para 00:00 depois que a janela virou 24h contadas do corte.
    """
    if janela is None:
        return (inicio, min(fim, inicio + recorte))
    abre, fecha = janela
    corte_a, corte_b = max(inicio, abre), min(fim, fecha)
    if corte_b <= corte_a:
        return (inicio, min(fim, inicio + recorte))
    return (corte_a, corte_b)


def _pedacos_do_trilho(
    trilho: dict,
    janela: tuple[datetime, datetime] | None,
) -> list[list[tuple[datetime, datetime]]]:
    """Trechos de cada serviço que entram no desenho, na ordem dos serviços."""
    recorte = timedelta(minutes=RECORTE_MIN)
    indice = {id(s): i for i, s in enumerate(trilho["servicos"])}
    chega, parte = set(), set()
    for elo in trilho["elos"]:
        chega.add(indice[id(elo["anterior"])])
        parte.add(indice[id(elo["proximo"])])

    saida = []
    for i, servico in enumerate(trilho["servicos"]):
        inicio = servico["inicio"]
        fim = servico["fim"] or inicio
        if fim < inicio:
            fim = inicio
        pedacos = []
        if i in parte:
            pedacos.append((inicio, min(fim, inicio + recorte)))
        if i in chega:
            pedacos.append((max(inicio, fim - recorte), fim))
        if not pedacos:
            pedacos.append(_trecho_na_janela(inicio, fim, janela, recorte))
        saida.append(_juntar(pedacos))
    return saida


def _montar_eixo(pedacos: list[tuple[datetime, datetime]]) -> dict:
    momentos = [ponta for par in pedacos for ponta in par]
    if not momentos:
        agora = datetime.now()
        momentos = [agora, agora + timedelta(hours=1)]

    inicio = min(momentos).replace(minute=0, second=0, microsecond=0)
    fim = max(momentos)
    if fim <= inicio:
        fim = inicio + timedelta(hours=1)
    fim = (fim + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    total = (fim - inicio).total_seconds()
    horas = total / 3600
    passo = 1 if horas <= 14 else (2 if horas <= 28 else 4)

    marcas = []
    cursor = inicio
    while cursor <= fim:
        marcas.append({
            "rotulo": cursor.strftime("%Hh"),
            "dia": cursor.strftime("%d/%m"),
            "pos": (cursor - inicio).total_seconds() / total * 100,
        })
        cursor += timedelta(hours=passo)

    return {"inicio": inicio, "fim": fim, "total": total, "marcas": marcas}


def _posicao(momento: datetime, eixo: dict) -> float:
    return (momento - eixo["inicio"]).total_seconds() / eixo["total"] * 100


def montar_dados(resultado: dict, meta: dict, descartados: list[dict],
                 janela: tuple[datetime, datetime] | None = None) -> dict:
    trilhos = resultado["trilhos"]
    pedacos_por_trilho = [_pedacos_do_trilho(t, janela) for t in trilhos]
    eixo = _montar_eixo([p for trilho in pedacos_por_trilho
                         for servico in trilho for p in servico])

    contagem = {"CRITICA": 0, "ALTA": 0, "MEDIA": 0, "BAIXA": 0}
    por_tipo: dict[str, int] = {}
    mapa_empresas = _mapa_empresas()
    por_empresa: dict[str, int] = {}
    por_empresa_anomalia: dict[str, int] = {}
    por_empresa_ocorrencias: dict[str, int] = {}
    trilhos_saida = []

    for trilho, pedacos_do_trilho in zip(trilhos, pedacos_por_trilho):
        indice_servico = {id(s): i for i, s in enumerate(trilho["servicos"])}

        servicos = []
        for servico, pedacos in zip(trilho["servicos"], pedacos_do_trilho):
            fim = servico["fim"] or servico["inicio"]
            pecas = []
            for corte_a, corte_b in pedacos:
                borda = _posicao(corte_a, eixo)
                pecas.append({
                    "pos": round(borda, 4),
                    "larg": round(max(_posicao(corte_b, eixo) - borda, 0.35), 4),
                    "corta_inicio": corte_a > servico["inicio"],
                    "corta_fim": corte_b < fim,
                })
            esquerda = pecas[0]["pos"]
            largura = max(pecas[-1]["pos"] + pecas[-1]["larg"] - esquerda, 0.35)
            servicos.append({
                "pecas": pecas,
                "servico": servico["servico"] or "sem número",
                "tipo": servico["tipo"] or "-",
                "origem": servico["origem"],
                "destino": servico["destino"],
                "inicio": _relogio(servico["inicio"]),
                "fim": _relogio(servico["fim"]),
                "duracao": _hhmm(servico["duracao_min"]),
                "linha": servico["linha_origem"],
                "e_servico": bool(servico.get("e_servico", True)),
                "pos": round(esquerda, 4),
                "larg": round(largura, 4),
            })

        elos = []
        for numero, elo in enumerate(trilho["elos"]):
            for problema in elo["problemas"]:
                contagem[problema["severidade"]] += 1
                por_tipo[problema["tipo"]] = por_tipo.get(problema["tipo"], 0) + 1

            pior = min(
                (p["severidade"] for p in elo["problemas"]),
                key=lambda s: ["CRITICA", "ALTA", "MEDIA", "BAIXA"].index(s),
                default="OK",
            ) if elo["problemas"] else "OK"

            fim_anterior = elo["anterior"]["fim"] or elo["anterior"]["inicio"]
            elos.append({
                "id": numero,
                "severidade": pior,
                "pos": round(_posicao(fim_anterior, eixo), 4),
                "de": elo["anterior"]["destino"],
                "para": elo["proximo"]["origem"],
                "servico_de": elo["anterior"]["servico"] or "sem número",
                "servico_para": elo["proximo"]["servico"] or "sem número",
                "chega": _relogio(fim_anterior),
                "parte": _relogio(elo["proximo"]["inicio"]),
                "intervalo": _hhmm(elo["intervalo_min"]),
                "intervalo_min": round(elo["intervalo_min"], 1),
                "minimo": _hhmm(elo["minimo_min"]),
                "minimo_min": round(elo["minimo_min"], 1),
                "regra": elo["regra_descricao"] or "",
                "regra_id": elo["regra_id"] or "",
                "cobra_virada": bool(elo.get("cobra_virada", True)),
                "idx_anterior": indice_servico[id(elo["anterior"])],
                "idx_proximo": indice_servico[id(elo["proximo"])],
                "problemas": elo["problemas"],
            })

        empresa = _empresa(trilho["nome"], trilho["servicos"], mapa_empresas)
        por_empresa[empresa] = por_empresa.get(empresa, 0) + 1
        if trilho["total_anomalias"]:
            por_empresa_anomalia[empresa] = por_empresa_anomalia.get(empresa, 0) + 1
            # Contagem em ocorrências, para o botão falar a mesma língua do
            # contador que fica ao lado dele na barra. Em trilhos os números não
            # somavam o total e a barra ficava contraditória.
            por_empresa_ocorrencias[empresa] = (
                por_empresa_ocorrencias.get(empresa, 0) + trilho["total_anomalias"])

        # Pior virada do trilho: o menor intervalo entre os elos que geraram
        # anomalia. Sobreposição é intervalo negativo, então ela cai na frente
        # sozinha, sem precisar de regra à parte.
        apertados = [e["intervalo_min"] for e in elos if e["problemas"]]
        pior_virada = min(apertados) if apertados else None

        trilhos_saida.append({
            "nome": trilho["nome"],
            "pior_virada": pior_virada,
            "prefixo": trilho["prefixo"],
            "empresa": empresa,
            "severidade": trilho["severidade_max"],
            "total": trilho["total_anomalias"],
            "servicos": servicos,
            "elos": elos,
        })

    # Ordem de exibição pedida pelo Daniel em 03/09/2026: da menor virada para a
    # maior, para o coordenador atacar o pior primeiro. A severidade caiu para
    # critério de desempate, porque o tempo de virada é a medida direta do
    # aperto, e a severidade é derivada dele.
    trilhos_saida.sort(key=lambda t: (
        t["pior_virada"] if t["pior_virada"] is not None else float("inf"),
        ["CRITICA", "ALTA", "MEDIA", "BAIXA", "OK"].index(t["severidade"]),
        -t["total"],
        t["nome"],
    ))

    return {
        "meta": meta,
        "eixo": {
            "inicio": eixo["inicio"].strftime("%d/%m/%Y %H:%M"),
            "fim": eixo["fim"].strftime("%d/%m/%Y %H:%M"),
            "marcas": eixo["marcas"],
        },
        "resumo": {
            "trilhos": len(trilhos_saida),
            "trilhos_com_anomalia": sum(1 for t in trilhos_saida if t["total"]),
            "servicos": sum(len(t["servicos"]) for t in trilhos_saida),
            "elos": sum(len(t["elos"]) for t in trilhos_saida),
            "severidade": contagem,
            "tipo": por_tipo,
            "empresas": por_empresa,
            "empresas_com_anomalia": por_empresa_anomalia,
            "empresas_ocorrencias": por_empresa_ocorrencias,
            "empresas_ordem": mapa_empresas.get("ordem", []),
            "empresas_rotulos": mapa_empresas.get("rotulos", {}),
            "dispensadas": resultado.get("dispensadas") or {},
            "descartados": len(descartados),
            "classificacao": resultado.get("classificacao", {}),
        },
        # Só trilho com anomalia vai para o payload. Trilho limpo não tem o que
        # revisar, e mandar todos multiplicava o tamanho do HTML por vinte: no
        # dia 03/09 eram 334 trilhos para 15 com anomalia. Os totais da malha
        # continuam certos porque o resumo é contado antes deste corte.
        "locais_fora_do_mapa": resultado["locais_fora_do_mapa"],
        "descartados": [
            {
                "linha": d["linha_origem"],
                "trilho": d["trilho"] or "-",
                "servico": d["servico"] or "-",
                "motivo": d["motivo"],
            }
            for d in descartados[:200]
        ],
        "trilhos": [t for t in trilhos_saida if t["total"]],
    }


def gerar(dados: dict, destino: Path) -> Path:
    modelo = MODELO.read_text(encoding="utf-8")
    payload = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    return arquivos.escrever_texto(destino, modelo.replace("/*__DADOS__*/", payload))
