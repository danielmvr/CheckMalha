# Histórico de versões

Formato MAIOR.MENOR.CORRECAO, explicado em `src/versao.py`. A versão aparece no
canto superior esquerdo do relatório e da página.

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
