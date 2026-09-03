"""
Aplica as duas regras da malha sobre os serviços já normalizados:

  1. Continuidade do trilho. O local onde um serviço termina e o local onde o
     próximo começa precisam estar na mesma zona metropolitana.
  2. Tempo de virada. O intervalo entre o fim de um serviço e o início do
     próximo precisa ser maior ou igual ao mínimo aplicável.

Antes de comparar, cada local passa pelo resolvedor: apelido explícito,
exceção de garagem, e a regra geral de garagem (código iniciado em G cujo
resto existe no catálogo oficial de siglas vale como o resto). Dois locais
que resolvem para o mesmo código fecham o trilho mesmo estando fora do mapa
de zonas, porque são o mesmo lugar.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

SEVERIDADES = ["CRITICA", "ALTA", "MEDIA", "BAIXA"]
PESO_SEVERIDADE = {nome: indice for indice, nome in enumerate(SEVERIDADES)}


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).upper()


class MapaZonas:
    def __init__(self, config: dict, pasta_config: Path | None = None):
        self.zonas = config.get("zonas", {})
        self.apelidos = {
            _sem_acento(k): _sem_acento(v)
            for k, v in config.get("apelidos", {}).items()
            if not k.startswith("_")
        }
        self.local_para_zona: dict[str, str] = {}
        self.nome_zona: dict[str, str] = {}
        for codigo, dados in self.zonas.items():
            self.nome_zona[codigo] = dados.get("nome", codigo)
            for local in dados.get("locais", []):
                self.local_para_zona[_sem_acento(local)] = codigo
        self.desconhecidos: dict[str, int] = {}

        self._configurar_garagens(config.get("garagens", {}), pasta_config)

    def _configurar_garagens(self, config: dict, pasta_config: Path | None) -> None:
        self.garagem_prefixo = _sem_acento(config.get("prefixo", "G"))
        self.garagem_excecoes = {
            _sem_acento(k): _sem_acento(v)
            for k, v in config.get("excecoes", {}).items()
            if not k.startswith("_")
        }
        self.catalogo: set[str] = set()
        self.catalogo_origem: str | None = None
        self.catalogo_erro: str | None = None
        self.garagens_ativas = bool(config.get("ativa", False))

        # Aceita um caminho ou uma lista de candidatos, na ordem. A lista existe
        # para o deploy: no PC o catálogo vive na pasta do extrator, e num
        # repositório que leva só este projeto ele vem da cópia em config/.
        caminho = config.get("catalogo_siglas")
        if not (self.garagens_ativas and caminho):
            return
        candidatos = [caminho] if isinstance(caminho, str) else list(caminho)
        erros = []
        for candidato in candidatos:
            alvo = Path(candidato)
            if not alvo.is_absolute() and pasta_config is not None:
                alvo = pasta_config / alvo
            try:
                with open(alvo, encoding="utf-8") as arquivo:
                    self.catalogo = {_sem_acento(c) for c in json.load(arquivo)}
                self.catalogo_origem = str(alvo)
                return
            except (OSError, ValueError) as erro:
                erros.append(f"{alvo}: {erro}")
        self.garagens_ativas = False
        self.catalogo_erro = " | ".join(erros)

    @classmethod
    def de_arquivo(cls, caminho: Path) -> "MapaZonas":
        caminho = Path(caminho)
        with open(caminho, encoding="utf-8") as arquivo:
            return cls(json.load(arquivo), pasta_config=caminho.parent)

    def resolver(self, local: str) -> str:
        """Código canônico do local, depois de apelido e regra de garagem."""
        chave = _sem_acento(local)
        if not chave:
            return chave
        if chave in self.apelidos:
            return self.apelidos[chave]
        if chave in self.garagem_excecoes:
            return self.garagem_excecoes[chave]
        # Cadastrado como localidade própria, não se mexe.
        if chave in self.local_para_zona:
            return chave
        if self.garagens_ativas and chave.startswith(self.garagem_prefixo):
            base = chave[len(self.garagem_prefixo):]
            if base in self.catalogo:
                return base
        return chave

    def zona(self, local: str) -> str | None:
        return self.local_para_zona.get(self.resolver(local))

    def contar_desconhecidos(self, registros: list[dict]) -> None:
        """Conta uma vez por ocorrência real na extração, não por consulta."""
        self.desconhecidos = {}
        for registro in registros:
            if not registro.get("e_servico", True):
                continue
            for local in (registro["origem"], registro["destino"]):
                chave = self.resolver(local)
                if chave and self.zona(chave) is None:
                    self.desconhecidos[chave] = self.desconhecidos.get(chave, 0) + 1

    def mesma_zona(self, a: str, b: str) -> bool | None:
        """True, False, ou None quando algum dos locais está fora do mapa.

        Locais que resolvem para o mesmo código são o mesmo lugar e fecham o
        trilho mesmo sem zona cadastrada. É o caso de chegar em SSA e sair de
        GSSA, ou de chegar e sair do mesmo ponto.
        """
        ra, rb = self.resolver(a), self.resolver(b)
        if ra and ra == rb:
            return True
        za, zb = self.zona(a), self.zona(b)
        if za is None or zb is None:
            return None
        return za == zb

    def rotulo(self, local: str) -> str:
        zona = self.zona(local)
        return self.nome_zona.get(zona, "fora do mapa") if zona else "fora do mapa"

    def rotulo_local(self, local: str) -> str:
        """Mostra a garagem junto do local resolvido, quando são diferentes."""
        bruto = _sem_acento(local)
        resolvido = self.resolver(local)
        return bruto if bruto == resolvido else f"{bruto} (={resolvido})"


class ClassificadorServico:
    """Separa serviço comercial de bloco interno da malha.

    Serviço é o que traz número de linha. Manutenção, revisão, emergência e
    linha sem número legível são blocos internos: continuam no trilho, mas não
    respondem pela regra de virada, porque virada é o intervalo entre duas
    viagens comerciais.
    """

    def __init__(self, config: dict):
        self.ativa = bool(config.get("ativa", False))
        self.cenario = str(config.get("cenario", ""))
        escolhido = config.get("cenarios", {}).get(self.cenario, {})
        self.descricao = escolhido.get("descricao", "")
        self.padroes = [re.compile(p, re.IGNORECASE)
                        for p in escolhido.get("padroes", [])]

        # Fonte que traz o tipo estruturado, como o relatório execucao, decide
        # por ele. O padrão do número fica de reserva para a extração por OCR,
        # onde o tipo não é confiável.
        por_tipo = config.get("por_tipo", {})
        self.tipos_servico = {_sem_acento(t) for t in por_tipo.get("servicos", [])}
        self.tipos_internos = {_sem_acento(t) for t in por_tipo.get("internos", [])}

        # Nome do serviço que sai do encadeamento antes de qualquer outro teste.
        # É o caso do transporte de funcionário, que vem como Viagem Vazia e
        # portanto passaria pelo por_tipo como serviço comercial.
        self.prefixos_internos = tuple(
            _sem_acento(p) for p in config.get("prefixos_internos", [])
            if str(p).strip()
        )

        if not self.padroes and not (self.tipos_servico or self.tipos_internos
                                     or self.prefixos_internos):
            self.ativa = False

    @classmethod
    def de_arquivo(cls, caminho: Path) -> "ClassificadorServico":
        with open(caminho, encoding="utf-8") as arquivo:
            config = json.load(arquivo)
        return cls(config.get("classificacao_servico", {}))

    def e_servico(self, registro: dict) -> bool:
        if not self.ativa:
            return True
        nome = _sem_acento(str(registro.get("servico", "")).strip())
        if self.prefixos_internos and nome.startswith(self.prefixos_internos):
            return False
        tipo = _sem_acento(registro.get("tipo", ""))
        if tipo and tipo in self.tipos_servico:
            return True
        if tipo and tipo in self.tipos_internos:
            return False
        numero = str(registro.get("servico", "")).strip()
        if not numero:
            return False
        return any(padrao.match(numero) for padrao in self.padroes)


class RegrasVirada:
    def __init__(self, config: dict):
        self.minimo_padrao = float(config.get("minimo_padrao_min", 240))
        self.tolerancia = float(config.get("tolerancia_min", 0))
        self.excecoes = [e for e in config.get("excecoes", []) if e.get("ativa")]

    @classmethod
    def de_arquivo(cls, caminho: Path) -> "RegrasVirada":
        with open(caminho, encoding="utf-8") as arquivo:
            return cls(json.load(arquivo))

    def _condicao_bate(self, quando: dict, contexto: dict) -> bool:
        for chave, esperado in quando.items():
            if chave == "par_servico":
                par = (contexto["servico_anterior"], contexto["servico_proximo"])
                if not any(tuple(p) == par for p in esperado):
                    return False
            elif chave == "rota_algum_lado":
                rotas = {
                    (_sem_acento(contexto.get("origem_anterior", "")) + ">" +
                     _sem_acento(contexto.get("destino_anterior", ""))),
                    (_sem_acento(contexto.get("origem_proxima", "")) + ">" +
                     _sem_acento(contexto.get("destino_proxima", ""))),
                }
                alvo = {_sem_acento(r).replace(" ", "") for r in esperado}
                if not (rotas & alvo):
                    return False
            elif chave == "par_rota":
                rota_a = (_sem_acento(contexto.get("origem_anterior", "")) + ">" +
                          _sem_acento(contexto.get("destino_anterior", "")))
                rota_b = (_sem_acento(contexto.get("origem_proxima", "")) + ">" +
                          _sem_acento(contexto.get("destino_proximo", "")))
                alvo = {(_sem_acento(p[0]).replace(" ", ""),
                         _sem_acento(p[1]).replace(" ", ""))
                        for p in esperado if len(p) == 2}
                if (rota_a, rota_b) not in alvo:
                    return False
            elif chave == "par_local":
                par = (contexto["destino_anterior"], contexto["origem_proxima"])
                if not any(tuple(p) == par for p in esperado):
                    return False
            elif chave == "zona_virada":
                if contexto["zona_virada"] not in esperado:
                    return False
            elif chave == "tipo_anterior":
                if contexto["tipo_anterior"] not in [_sem_acento(v) for v in esperado]:
                    return False
            elif chave == "tipo_proximo":
                if contexto["tipo_proximo"] not in [_sem_acento(v) for v in esperado]:
                    return False
            elif chave == "trilho":
                if contexto["trilho"] not in esperado:
                    return False
            elif chave == "mesmo_servico":
                anterior = str(contexto.get("servico_anterior", "")).strip()
                proximo = str(contexto.get("servico_proximo", "")).strip()
                igual = bool(anterior) and anterior == proximo
                if bool(esperado) != igual:
                    return False
            elif chave == "local_encaixa":
                chegada = str(contexto.get("destino_anterior", "")).strip()
                partida = str(contexto.get("origem_proxima", "")).strip()
                encaixa = bool(chegada) and chegada == partida
                if bool(esperado) != encaixa:
                    return False
            elif chave == "duracao_anterior_max_min":
                duracao = contexto.get("duracao_anterior")
                if duracao is None or duracao >= float(esperado):
                    return False
            elif chave == "duracao_proxima_max_min":
                duracao = contexto.get("duracao_proxima")
                if duracao is None or duracao >= float(esperado):
                    return False
            else:
                return False
        return True

    def avaliar(self, contexto: dict) -> tuple[float, str | None, str | None, bool]:
        """Devolve (mínimo em minutos, id da exceção, descrição, dispensado).

        `dispensado` vem de uma exceção com `"ignorar": true` e significa que o
        elo **não gera anomalia nenhuma**, nem virada curta nem sobreposição.
        Abaixar o mínimo não resolvia esse caso: a sobreposição é testada por
        `intervalo < 0`, antes e independente do mínimo, então virada de -5 min
        numa ponta de transbordo saía como CRITICA por mais baixo que fosse o
        mínimo.
        """
        minimo, regra_id, descricao = self.minimo_padrao, None, None
        dispensado = False
        for excecao in self.excecoes:
            if not self._condicao_bate(excecao.get("quando", {}), contexto):
                continue
            if excecao.get("ignorar"):
                # Dispensa vale por si, sem competir por menor mínimo.
                dispensado = True
                regra_id = excecao.get("id")
                descricao = excecao.get("descricao")
                continue
            candidato = float(excecao.get("minimo_min", self.minimo_padrao))
            if candidato < minimo:
                minimo = candidato
                if not dispensado:
                    regra_id = excecao.get("id")
                    descricao = excecao.get("descricao")
        return minimo, regra_id, descricao, dispensado


class LinhasCurtas:
    """Linhas cuja viagem inteira é curta, que toleram virada mais apertada.

    A ponta é comparada pela zona quando o local tem zona cadastrada, então JDF
    cobre GJF e JFA. O par não tem direção: BSB x GYN vale nos dois sentidos.
    """

    def __init__(self, config: dict, mapa: MapaZonas):
        self.ativa = bool(config.get("ativa", False))
        self.duracao_maxima = float(config.get("duracao_maxima_min", 300))
        self.mapa = mapa
        self.pares: set[frozenset] = set()
        for par in config.get("pares", []):
            if len(par) == 2:
                self.pares.add(frozenset(self._ponta(p) for p in par))
        if not self.pares:
            self.ativa = False

    @classmethod
    def de_arquivo(cls, caminho: Path, mapa: MapaZonas) -> "LinhasCurtas":
        with open(caminho, encoding="utf-8") as arquivo:
            config = json.load(arquivo)
        return cls(config.get("linhas_curtas", {}), mapa)

    def _ponta(self, local: str) -> str:
        zona = self.mapa.zona(local)
        return zona if zona else _sem_acento(self.mapa.resolver(local))

    def e_curta(self, origem: str, destino: str) -> bool:
        if not self.ativa:
            return False
        return frozenset((self._ponta(origem), self._ponta(destino))) in self.pares


def _abaixar_severidade(severidade: str) -> str:
    indice = PESO_SEVERIDADE.get(severidade, len(SEVERIDADES) - 1)
    return SEVERIDADES[min(indice + 1, len(SEVERIDADES) - 1)]


def _severidade_virada(intervalo: float, minimo: float) -> str:
    if minimo <= 0:
        return "BAIXA"
    proporcao = intervalo / minimo
    if proporcao < 0.5:
        return "ALTA"
    return "MEDIA"


def validar(registros: list[dict], mapa: MapaZonas, regras: RegrasVirada,
            classificador: "ClassificadorServico | None" = None,
            linhas_curtas: "LinhasCurtas | None" = None) -> dict:
    """Agrupa por trilho, encadeia os serviços e devolve trilhos com seus elos."""
    if classificador is None:
        classificador = ClassificadorServico({})
    for registro in registros:
        registro["e_servico"] = classificador.e_servico(registro)

    mapa.contar_desconhecidos(registros)
    fora_do_encadeamento = 0
    dispensadas: dict[str, int] = {}

    por_trilho: dict[str, list[dict]] = {}
    for registro in registros:
        por_trilho.setdefault(registro["trilho"], []).append(registro)

    trilhos = []
    for nome, servicos in sorted(por_trilho.items()):
        servicos = sorted(servicos, key=lambda r: r["inicio"])

        # Bloco interno continua na lista de serviços, porque a barra dele aparece
        # na linha do tempo, mas sai do encadeamento e não responde por regra nenhuma.
        if classificador.ativa:
            encadeados = [s for s in servicos if s["e_servico"]]
            fora_do_encadeamento += len(servicos) - len(encadeados)
        else:
            encadeados = servicos

        elos = []

        for anterior, proximo in zip(encadeados, encadeados[1:]):
            fim_anterior = anterior["fim"] or anterior["inicio"]
            intervalo = (proximo["inicio"] - fim_anterior).total_seconds() / 60

            zona_destino = mapa.zona(anterior["destino"])
            zona_origem = mapa.zona(proximo["origem"])
            continuidade = mapa.mesma_zona(anterior["destino"], proximo["origem"])

            contexto = {
                "trilho": nome,
                "servico_anterior": anterior["servico"],
                "servico_proximo": proximo["servico"],
                "origem_anterior": anterior["origem"],
                "destino_anterior": anterior["destino"],
                "origem_proxima": proximo["origem"],
                "destino_proximo": proximo["destino"],
                "destino_proxima": proximo["destino"],
                "tipo_anterior": anterior["tipo"],
                "tipo_proximo": proximo["tipo"],
                "duracao_anterior": anterior.get("duracao_min"),
                "duracao_proxima": proximo.get("duracao_min"),
                "zona_virada": zona_destino,
            }
            minimo, regra_id, regra_desc, dispensado = regras.avaliar(contexto)

            problemas = []

            if dispensado:
                dispensadas[regra_id or "sem id"] = (
                    dispensadas.get(regra_id or "sem id", 0) + 1)
            elif continuidade is False:
                problemas.append({
                    "tipo": "SEQUENCIA",
                    "severidade": "ALTA",
                    "titulo": "Trilho quebrado",
                    "detalhe": (
                        f"Chega em {mapa.rotulo_local(anterior['destino'])} "
                        f"({mapa.rotulo(anterior['destino'])}) e o próximo serviço "
                        f"parte de {mapa.rotulo_local(proximo['origem'])} "
                        f"({mapa.rotulo(proximo['origem'])})."
                    ),
                })
            elif continuidade is None and not dispensado:
                fora = [mapa.resolver(l)
                        for l in (anterior["destino"], proximo["origem"])
                        if mapa.zona(l) is None]
                problemas.append({
                    "tipo": "LOCAL_FORA_DO_MAPA",
                    "severidade": "BAIXA",
                    "titulo": "Local sem zona cadastrada",
                    "detalhe": (
                        f"Não dá para validar a continuidade porque {', '.join(fora)} "
                        f"não está em config/zonas.json."
                    ),
                })

            if dispensado:
                pass
            elif intervalo < 0:
                problemas.append({
                    "tipo": "SOBREPOSICAO",
                    "severidade": "CRITICA",
                    "titulo": "Serviços sobrepostos",
                    "detalhe": (
                        f"O próximo serviço começa {abs(intervalo):.0f} min antes "
                        f"do anterior terminar."
                    ),
                })
            elif intervalo + regras.tolerancia < minimo:
                falta = minimo - intervalo
                severidade = _severidade_virada(intervalo, minimo)
                # Linha de viagem curta tolera virada mais apertada. Não é
                # perdão: sai com tipo próprio, para revisar em separado, e uma
                # severidade abaixo. Vale só quando os DOIS lados são dela.
                linha_curta = bool(
                    linhas_curtas
                    and linhas_curtas.e_curta(anterior["origem"], anterior["destino"])
                    and linhas_curtas.e_curta(proximo["origem"], proximo["destino"])
                )
                if linha_curta:
                    problemas.append({
                        "tipo": "VIRADA_LINHA_CURTA",
                        "severidade": _abaixar_severidade(severidade),
                        "titulo": "Virada curta em linha curta",
                        "detalhe": (
                            f"Virada de {_hhmm(intervalo)} contra o mínimo de "
                            f"{_hhmm(minimo)}, faltam {_hhmm(falta)}. Os dois lados são "
                            f"linhas de viagem até "
                            f"{_hhmm(linhas_curtas.duracao_maxima)}, que toleram virada "
                            f"mais apertada."
                        ),
                    })
                else:
                    problemas.append({
                        "tipo": "VIRADA_CURTA",
                        "severidade": severidade,
                        "titulo": "Virada abaixo do mínimo",
                        "detalhe": (
                            f"Virada de {_hhmm(intervalo)} contra o mínimo de "
                            f"{_hhmm(minimo)}. Faltam {_hhmm(falta)}."
                        ),
                    })

            elos.append({
                "anterior": anterior,
                "proximo": proximo,
                "intervalo_min": intervalo,
                "minimo_min": minimo,
                "regra_id": regra_id,
                "regra_descricao": regra_desc,
                "zona_destino": zona_destino,
                "zona_origem": zona_origem,
                "cobra_virada": True,
                "dispensado": dispensado,
                "problemas": problemas,
            })

        anomalias = [p for elo in elos for p in elo["problemas"]]
        severidade_max = min(
            (PESO_SEVERIDADE[a["severidade"]] for a in anomalias), default=len(SEVERIDADES)
        )
        trilhos.append({
            "nome": nome,
            "prefixo": next((s["prefixo"] for s in servicos if s["prefixo"]), ""),
            "servicos": servicos,
            "elos": elos,
            "total_anomalias": len(anomalias),
            "severidade_max": SEVERIDADES[severidade_max] if anomalias else "OK",
        })

    return {
        "trilhos": trilhos,
        "locais_fora_do_mapa": dict(
            sorted(mapa.desconhecidos.items(), key=lambda kv: -kv[1])
        ),
        "classificacao": {
            "ativa": classificador.ativa,
            "cenario": classificador.cenario,
            "descricao": classificador.descricao,
            "servicos": sum(1 for r in registros if r["e_servico"]),
            "blocos_internos": sum(1 for r in registros if not r["e_servico"]),
            "fora_do_encadeamento": fora_do_encadeamento,
        },
        "dispensadas": dispensadas,
        "linhas_curtas": {
            "ativa": bool(linhas_curtas and linhas_curtas.ativa),
            "pares": len(linhas_curtas.pares) if linhas_curtas else 0,
            "duracao_maxima_min": (linhas_curtas.duracao_maxima
                                   if linhas_curtas else None),
        },
    }


def _hhmm(minutos: float) -> str:
    minutos = int(round(abs(minutos)))
    horas, resto = divmod(minutos, 60)
    return f"{horas}h{resto:02d}" if horas else f"{resto}min"
