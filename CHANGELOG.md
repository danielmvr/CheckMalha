# Histórico de versões

Formato MAIOR.MENOR.CORRECAO, explicado em `src/versao.py`. A versão aparece no
canto superior esquerdo do relatório e da página.

## 1.5.0, 03/09/2026

### Exceção vira-em-man

Quarta da família "linha que vira nela mesma", mesmo desenho das de QMI e QJO:
`par_local: [["MAN","MAN"]]` mais `rota_algum_lado: ["SSA>MAN","MAN>SSA"]`, com
`ignorar: true`.

Medido no arquivo de 03/09: MAN é tocado por duas rotas só, `SSA>MAN` e
`MAN>SSA`. A única virada em MAN da janela é `SSA>MAN` para `MAN>SSA`, com
**-20 min**, que saía como SOBREPOSICAO CRITICA. O `ignorar` é indispensável
aqui, porque sobreposição é testada antes e independente do mínimo.

MAN não tem zona cadastrada e resolve para si mesmo. Não confundir com GMA.

## 1.4.0, 03/09/2026

### Contador de ocorrências na barra de empresa

Bloco destacado, fundo cheio na cor da tinta, no começo da barra de filtro de
empresa, com a barra centralizada. Conta **ocorrências**, não trilhos, e conta o
mesmo que os cartões desenham: problema por problema depois do `casoVisivel`.

- Reage a todos os filtros juntos, empresa, tipo, severidade e busca.
- Sem filtro mostra só o número. Com filtro mostra "N de M" e fica azul, senão o
  número sozinho não diz de quanto é.
- Verde quando o dia não tem anomalia nenhuma.
- O contador fica sempre, mesmo quando o dia tem uma empresa só e as fichas de
  empresa não aparecem.

### Botões de empresa passaram a contar ocorrências

Efeito colateral que o contador expôs: os botões mostravam **trilhos** e somavam
31 ao lado de um contador que dizia 34 ocorrências. Duas unidades diferentes
lado a lado na mesma barra.

Agora os botões contam ocorrências e **somam exatamente o total**, o que torna a
barra autoverificável: clicar em `RAF 12` faz o contador dizer "12 ocorrências de
34". A contagem em trilhos foi para o `title`: "12 ocorrência(s) em 10
trilho(s), de 61 na malha". Campo novo no resumo: `empresas_ocorrencias`.

## 1.3.0, 03/09/2026

### Ordem de exibição pela virada mais apertada

Pedido do Daniel: o coordenador precisa resolver os piores primeiro. A lista de
trilhos e as ocorrências dentro de cada cartão passaram a sair **da menor virada
para a maior**. Sobreposição é intervalo negativo, então cai na frente sozinha,
sem precisar de regra à parte.

A severidade virou critério de desempate, porque o tempo de virada é a medida
direta do aperto e a severidade é derivada dele. Cada trilho carrega
`pior_virada`, o menor intervalo entre seus elos com anomalia.

### Duas exceções novas de linha que vira nela mesma

| exceção | virada em | pernas | o que saía |
|---|---|---|---|
| `vira-em-qmi` | QMI | `QVR>QMI`, `QMI>QVR` | 8 VIRADA_CURTA de 10 min |
| `vira-em-qjo` | QJO | `RIO>QJO`, `QJO>RIO` | 7 VIRADA_CURTA de 105 a 150 min |

Ambas com `ignorar: true`, valendo para virada curta e sobreposição.

**As duas condições são obrigatórias juntas:** `par_local` amarra a virada no
local certo e `rota_algum_lado` amarra a perna da linha. Só o `par_local`
liberaria qualquer virada naquele local; só a rota liberaria a virada daquela
linha em outro lugar. Em QMI isso importa: das 12 viradas medidas no arquivo, as
4 que não vêm de uma perna do QVR têm intervalo folgado e seguem sendo
conferidas.

Conferido dia a dia de 31/08 a 08/09: zero anomalias remanescentes em viradas de
QMI, QJO ou DIV.

**A linha de base mudou:** menos 2 anomalias por dia de operação, além das 2 da
1.2.0.

## 1.2.0, 03/09/2026

### Exceção pode dispensar o elo por completo

`ignorar: true` numa exceção faz o elo **não gerar anomalia nenhuma**, nem virada
curta, nem sobreposição, nem local fora do mapa. Antes só existia abaixar o
mínimo, e isso não bastava: a sobreposição é testada por `intervalo < 0`, antes e
independente do mínimo, então virada de -5 min saía como CRITICA por mais baixo
que o mínimo fosse.

- `RegrasVirada.minimo_para` virou `RegrasVirada.avaliar`, devolvendo também
  `dispensado`.
- Condição nova `rota_algum_lado`: lista de rotas `ORIGEM>DESTINO`, basta **um**
  dos dois lados casar. As condições dentro de `quando` são combinadas em E, e
  esta é a forma de expressar "qualquer um dos lados".
- Os elos dispensados são **contados e mostrados**, no console e no cabeçalho do
  relatório, campo "Dispensadas por exceção". Regra silenciosa esconde erro.

### transbordo-bsb-div corrigida

A primeira versão usava `par_rota` com o par DIV para BSB puro, e não pegava o
caso real: a virada acontece em **BSB**, entre a perna do DIV e a do GYN. Medido
no arquivo de 03/09, o padrão se repetia todo dia:

| encadeamento | virada | saía como |
|---|---|---|
| `GYN>BSB` para `BSB>DIV` | 5 a 25 min | VIRADA_CURTA |
| `DIV>BSB` para `BSB>GYN` | -5 min | SOBREPOSICAO |

Eram 2 anomalias por dia, 16 nos 9 dias do arquivo. Agora zero em todos os dias,
com 3 elos dispensados por dia.

**A linha de base mudou:** menos 2 anomalias por dia de operação.

## 1.1.0, 03/09/2026

### Janela de análise de 24 horas a partir do corte

Antes a análise ia do corte até 23:59 do dia alvo, então a janela encurtava
conforme o dia avançava e a análise da noite ficava sem material. Medido no
arquivo de 03/09:

| hora de corte | antes, até 23:59 | agora, 24h do corte |
|---|---|---|
| 06:00 | 18h, 619 serviços, 43 anomalias | 24h, 672 serviços, 45 anomalias |
| 12:00 | 12h, 457 serviços, 25 anomalias | 24h, 636 serviços, 42 anomalias |
| 18:00 | 6h, 350 serviços, 9 anomalias | 24h, 667 serviços, 36 anomalias |
| 23:00 | **1h, 240 serviços, 2 anomalias** | **24h, 711 serviços, 47 anomalias** |

- `fonte_execucao.preparar` passou a receber a janela pronta, `[inicio, fim)`,
  em vez do dia alvo.
- `main.py` resolve a hora de corte **antes** do recorte, porque é dela que a
  janela nasce, e ganhou `_janela()`. Tamanho em `JANELA_HORAS = 24`,
  sobreponível por `janela_horas` no `config/caminhos.json`.
- Sem corte (`--corte nao`), a janela volta a ser o dia alvo inteiro, que é o
  que faz sentido para revisar um dia que já passou.
- Aviso novo quando a janela passa da última partida do arquivo: o trecho final
  fica sem dado e o execucao precisa cobrir mais dias para frente.
- No cabeçalho do relatório, "Janela" agora é a janela da análise, e o intervalo
  do eixo virou "Desenho".

## 1.0.0, 03/09/2026

Primeira versão numerada. Estado do validador da malha SIGLA nesta data.

### Fontes
- `execucao.XLS` do SIGLA, com dedução da escala de motorista e recorte da
  janela pelo dia alvo.
- Raspagem por OCR da malha, mantida em paralelo.
- Consumo por **link compartilhado** do OneDrive, com três estratégias de
  download, checagem por assinatura de arquivo e queda para o cache anterior.

### Regras
- Virada mínima de 240 min, tolerância 5, com exceções em `regras_virada.json`:
  curta distância, continuidade de serviço, atividade interna e o transbordo
  BSB/DIV pela condição nova `par_rota`.
- Classificação de serviço em três níveis de precedência: `prefixos_internos`
  pelo nome (`FUNCIONARIO`), `por_tipo` pelo tipo estruturado, e o padrão do
  número como reserva.
- `VIRADA_LINHA_CURTA`, tipo próprio para as 11 linhas de viagem até 5h, com
  filtro dedicado e uma severidade abaixo.
- Descarte de veículo que não é veículo: `SIMULTANEO`, `TURISMO`, vazio,
  `CANCELAD.*` e `N ABRIR*`. Veículo de terceiro fica.
- 12 zonas e 40 códigos, com normalização de garagem pelo catálogo de 295
  siglas.
- **Hora de corte**, padrão a hora de geração: o que já terminou sai da análise.
  Ancorada no fuso da operação, não no relógio da máquina.

### Relatório
- Recorte de 1 hora em volta da virada no desenho, com o horário cheio no texto.
- Escala de cor de 5 degraus no tempo de virada, pela fração do mínimo que
  sobrou.
- Filtros por tipo de anomalia, por severidade, por **empresa** e busca livre.
- Exportação CSV do que está filtrado.

### Operação
- Nome fixo em `dados_trabalho` e `saida`, um por dia de operação.
- Escrita atômica em toda gravação, `src/arquivos.py`, para sobreviver ao
  OneDrive no Windows.
- Página online em Streamlit, atualização automática a cada 10 minutos,
  chamando o `main.py` por subprocesso.
