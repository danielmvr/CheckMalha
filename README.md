# Validação da malha

Segundo braço do projeto SIGLA. Lê a extração bruta que o extrator já gera, encadeia
os serviços de cada trilho e aponta duas coisas:

1. **Trilho quebrado.** O serviço termina em um lugar e o seguinte parte de outro,
   fora da mesma zona metropolitana. QNT e RIO contam como o mesmo lugar, então essa
   troca não é apontada.
2. **Virada curta.** O intervalo entre o fim de um serviço e o início do próximo está
   abaixo do mínimo de 4 horas, descontadas as exceções configuradas.

Também aponta serviços sobrepostos, que é o caso em que o próximo começa antes do
anterior terminar, e locais que ainda não estão no mapa de zonas.

Nem todo local pertence a uma zona, e isso é esperado. O mapa de zonas cobre só as
regiões metropolitanas onde faz sentido trocar de ponto dentro da mesma virada. Um
local fora do mapa não é erro de cadastro, é um lugar onde a continuidade não pode ser
conferida por zona.

O resultado sai em um HTML único, que abre com duplo clique, sem internet.

---

## Rodar

```
cd ProjetoIndisponiveis
python main.py
```

O script procura sozinho a extração mais recente em `ControleRemoto SIGLA/saida`, que é
onde o extrator grava, em `DD-MM-AAAA/vN/`. A escolha segue esta ordem:

1. maior data de operação no nome do arquivo
2. maior versão, lida do sufixo `_v2` no nome ou da pasta `vN`
3. formato mais confiável entre os da mesma execução: `xlsx`, `xlsm`, `csv`, `json`
4. maior data de modificação

O `SIGLA_Relatorio_DD-MM-AAAA_descartados.csv` é ignorado. Ele casa com o mesmo prefixo
e é gravado depois dos outros, então sem essa exclusão ele ganharia o desempate por data
de modificação e o validador leria o arquivo errado.

Copia o arquivo escolhido para `dados_trabalho/` e trabalha só na cópia. A extração
original nunca é tocada.

Opções:

```
python main.py --pasta "C:\Users\daniel.reis\Desktop"   procurar em outra pasta
python main.py --arquivo "C:\...\SIGLA_Relatorio_21-05-2026.xlsx"   usar um arquivo específico
python main.py --sem-abrir                              não abrir o navegador no fim
```

Formatos aceitos na entrada: `.xlsx`, `.xlsm`, `.csv`, `.json`.

---

## O que conta como servico

Servico e o que traz numero de linha. Os prefixos sao as empresas: **15 UTIL, 20 REX,
25 RAF, 35 Samp**. `VZ`, viagem vazia, tambem conta.

Manutencao (`MNT`), revisao (`REV`), emergencia (`EMG`) e linha sem numero legivel sao
**bloco interno**. Eles continuam desenhados na linha do tempo, hachurados, porque
mostram onde o carro esteve, mas ficam fora do encadeamento e nao respondem por regra
nenhuma. Nenhuma anomalia cita bloco interno.

Consequencia importante: quando dois servicos estao separados por uma manutencao, a
virada passa a ser medida **entre os dois servicos**, atravessando o bloco. Antes esse
intervalo nao era conferido por ninguem.

Configurado em `config/regras_virada.json`, bloco `classificacao_servico`, com dois
cenarios trocaveis pelo campo `cenario`:

| Cenario | Padrao | Servicos no dia 26/08 |
|---|---|---|
| `estrito` | numero limpo de 8 digitos, ou 8+8 separados por barra | 432 |
| `amplo` (em uso) | numero comecando com 15, 20, 25 ou 35, mais `VZ` | 456 |

Os quatro prefixos cobrem 100% dos numeros limpos, entao `amplo` e superconjunto de
`estrito`. A diferenca sao 24 linhas que o OCR truncou, como `252031` e
`20203175/204231`.

Para voltar ao comportamento antigo, cobrando virada de tudo, ponha `"ativa": false`.

---

## Excecoes de virada

O minimo padrao e 240 minutos. Cada excecao em `config/regras_virada.json` abaixa esse
minimo quando as condicoes batem. Se mais de uma se aplica, vale a de menor minimo, e o
relatorio mostra qual regra pegou.

Condicoes disponiveis dentro de `quando`:

| Condicao | O que compara |
|---|---|
| `zona_virada` | zona do local de chegada |
| `tipo_anterior` / `tipo_proximo` | tipo do servico que chega ou que parte |
| `trilho` | nome do trilho |
| `par_local` | par [destino_anterior, origem_proxima] |
| `par_servico` | par [numero_anterior, numero_proximo] |
| `mesmo_servico` | true quando o numero do servico e o mesmo dos dois lados |
| `local_encaixa` | true quando o destino que chega e igual a origem que parte |
| `duracao_anterior_max_min` | duracao do servico que chega, em minutos, exclusivo |
| `duracao_proxima_max_min` | duracao do servico que parte, em minutos, exclusivo |

Todas as condicoes de uma excecao precisam bater ao mesmo tempo. Duracao desconhecida
nunca satisfaz as condicoes de duracao, por seguranca.

### continuidade-servico

Ligada. A pedra as vezes e quebrada em secoes dentro da mesma viagem, por troca de
carro ou rendicao. As duas secoes carregam o mesmo numero de servico, entao o intervalo
entre elas nao e virada e o minimo cai para zero.

Ressalva: numero igual nem sempre e continuacao. No dia 26/08, 13 dos 33 pares com
numero igual sao a mesma linha diaria capturada em dois dias, com origem e destino
repetidos, por exemplo `SAO->IRE` seguido de `SAO->IRE`. Esses tem intervalo de 4h30 a
14h e passam no minimo padrao de qualquer jeito, entao hoje a regra nao muda nada neles.
Para restringir so a continuacao de verdade, acrescente `"local_encaixa": true` no
`quando` da excecao.

No dia 26/08 pegou 33 elos e derrubou a virada curta de 53 para 34.

### curta-distancia

Ligada. Linha curta nao precisa de virada cheia, o carro e virado na propria
rodoviaria, entao o minimo cai para 1 minuto.

Vale so quando os **dois** lados tem menos de 4 horas. A leitura de um lado so foi
descartada olhando o dado: pelo criterio "so o que chega", uma virada de 25 minutos
antes de uma viagem de 9h45, e de 1h40 antes de uma de 18h25, seriam aceitas.

No dia 26/08 a excecao pegou 40 elos e derrubou a virada curta de 88 para 53.

---

## Garagens

Código que começa com `G` vale como o local sem o `G`. `GBSB` é a garagem de `BSB`,
`GSSA` é a garagem de `SSA`. Para o encadeamento do trilho os dois são o mesmo lugar,
então chegar em `BSB` e sair de `GBSB` fecha o trilho.

A regra só se aplica quando o código sem o `G` existe no catálogo oficial de siglas,
em `ControleRemoto SIGLA/siglas.json`. É isso que separa garagem de localidade própria:
`GYN`, `GJF`, `GMA`, `GATS`, `GRAM`, `GCG`, `GRQ` e `GJS` ficam intactos porque `YN`,
`JF`, `MA`, `ATS`, `RAM`, `CG`, `RQ` e `JS` não existem no catálogo. Código já
cadastrado em `zonas` nunca é reescrito.

A exceção conhecida é o RIO, cuja garagem é `GCE` e não segue o padrão. Ela está em
`config/zonas.json`, no bloco `garagens.excecoes`.

Dois locais que resolvem para o mesmo código fecham o trilho mesmo quando estão fora do
mapa de zonas, porque são o mesmo lugar. Chegar em `SSA` e sair de `GSSA` fecha, ainda
que `SSA` não pertença a nenhuma zona.

Se o catálogo não puder ser lido, a regra desliga sozinha e o `main.py` avisa na etapa 4.

---

## Agrupamento do trilho

O trilho é a **posição da malha** (`trilho_nome`, no formato `Pos-NNN`), não o carro.
São coisas diferentes: na extração de 26/08/2026, 17 carros aparecem em duas posições
distintas. Agrupar por carro juntaria essas duas posições em um trilho só e inventaria
sobreposições que não existem, 78 contra as 51 reais.

O número do carro entra como `prefixo`, que é informativo e não agrupa nada.

---

## O que a extração precisa trazer

Estas colunas são obrigatórias:

| Coluna | Para quê |
|---|---|
| `trilho` | agrupar os serviços da mesma posição da malha |
| `origem` | ponto de partida do serviço |
| `destino` | ponto de chegada do serviço |
| `inicio` | hora de partida |

E estas melhoram o resultado:

| Coluna | Para quê |
|---|---|
| `fim` | fecha o cálculo da virada com precisão |
| `duracao` | usado para achar o `fim` quando ele não vem |
| `tipo` | libera as exceções de manutenção e reserva |
| `servico` | identifica a pedra no relatório |
| `data` | monta a data completa quando a hora vem sozinha |
| `prefixo` | mostra o número do carro no cabeçalho do trilho |

**Atenção.** O extrator atual captura duração, número e tipo, mas não captura origem
e destino. Sem esses dois campos não dá para conferir se o trilho fecha, e o script
para na etapa 3 avisando o que falta. Antes de usar este módulo, inclua origem e
destino na captura do popup de serviço.

Os nomes das colunas não precisam ser exatamente esses. O módulo reconhece variações
comuns (`veiculo`, `partida`, `chegada`, `hora_inicio`, `dtoper` e outras). Se a sua
extração usa um nome que não é reconhecido, acrescente esse nome em `APELIDOS_COLUNA`,
em `src/normalizador.py`.

Serviços que cruzam a meia-noite são tratados. Se o fim é menor que o início, o módulo
empurra para o dia seguinte.

---

## Configuração

### `config/zonas.json`

Define quais códigos de local contam como o mesmo lugar. O mapa foi montado a partir
do artefato **Zonas de Localidade**: 10 zonas e 32 códigos, com a contagem de usos
comerciais de cada código guardada em `_usos` para você enxergar o peso antes de mexer
no agrupamento.

Para incluir um local em uma zona, acrescente o código na lista `locais`. Todo código
que aparecer na extração e não estiver nesse arquivo entra na seção "Locais fora do
mapa" do relatório, com a contagem de quantas vezes apareceu. Use essa lista para
completar o mapa.

O bloco `apelidos` está vazio de propósito. Ele serve para o caso de a extração
escrever o local de outro jeito, como `NOVO RIO` no lugar de `RIO`. Preencha só com
equivalências confirmadas, porque um apelido errado esconde uma quebra de trilho real.

### `config/regras_virada.json`

`minimo_padrao_min` é o mínimo geral, hoje em 240 minutos. `tolerancia_min` evita
apontar diferenças de poucos minutos.

As exceções abaixam esse mínimo quando as condições batem. Cada uma tem um campo
`ativa`, que liga e desliga a regra sem apagá-la. Quando mais de uma exceção se aplica,
vale a de menor mínimo, e o relatório mostra qual regra pegou.

Condições disponíveis dentro de `quando`:

| Condição | O que compara |
|---|---|
| `zona_virada` | a zona onde o carro faz a virada |
| `tipo_anterior` | o tipo do serviço que termina |
| `tipo_proximo` | o tipo do serviço que começa |
| `trilho` | o nome do trilho |
| `par_local` | um par destino/origem específico |
| `par_servico` | um par de números de serviço específico |

Duas exceções já vêm ligadas: entrar em manutenção, reserva, transferência ou
abastecimento, e sair delas, não exige virada cheia. As demais vêm desligadas para
você preencher com as viradas que a coordenação realmente autoriza.

### `config/caminhos.json`

`pasta_extracoes` é onde procurar os arquivos brutos, `prefixo_arquivo` filtra por
início do nome e `abrir_ao_terminar` abre o HTML no navegador.

---

## O relatório

Cada trilho aparece como uma faixa horizontal no eixo do dia, com uma barra por
serviço. As barras listradas são atividades internas. Entre duas barras há uma marca
vertical, que é a virada: cinza quando está tudo certo, colorida na severidade do
problema quando não está.

Clicar na marca leva até a ocorrência correspondente e acende os dois serviços
envolvidos. Clicar na ocorrência faz o mesmo caminho de volta. Passar o mouse sobre
uma barra mostra serviço, tipo, trecho, horários e a linha de origem na planilha.

No topo, os quatro cartões de severidade filtram a lista. As fichas filtram por tipo
de ocorrência. A busca aceita nome de trilho, número de serviço e código de local, e
alcança também os trilhos sem anomalia. "Baixar CSV" exporta exatamente o que está
visível na tela, para repassar à equipe.

Severidades:

| Severidade | Quando |
|---|---|
| Crítica | serviços sobrepostos |
| Alta | trilho quebrado, ou virada abaixo da metade do mínimo |
| Média | virada abaixo do mínimo |
| Baixa | local sem zona cadastrada, continuidade não conferida |

---

## Pastas

```
sigla_malha_validador/
├── config/            zonas, regras de virada, caminhos
├── src/               localizador, normalizador, validador, relatório, modelo HTML
├── dados_trabalho/    cópias das extrações, uma subpasta por dia
├── saida/             relatórios gerados, um por execução
├── exemplo/           extração de teste com anomalias conhecidas
└── main.py
```

Para conferir que está tudo funcionando sem depender de uma extração real:

```
python main.py --pasta exemplo --sem-abrir
```

O exemplo tem 19 linhas e deve produzir 5 anomalias em 4 de 8 trilhos, com XPT
listado como local fora do mapa e uma linha descartada por falta de destino.

---

## Dependências

```
pip install pandas openpyxl
```
