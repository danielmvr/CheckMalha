# Processo: Controle Remoto SIGLA

Este documento descreve a ordem e o papel de cada etapa desta automação dentro de um processo maior de gestão de manutenção e programação de viagens.

---

## Contexto no processo maior

Esta automação é uma **etapa de extração e classificação** — ela lê a programação do dia no sistema SIGLA (desktop) e transforma dados visuais em registros estruturados, que alimentam o controle de manutenção (`dadosManut.xlsx`) e outros sistemas downstream.

```
[SIGLA - sistema desktop]
        ↓
[1. Extração automática] ← esta automação
        ↓
[2. Análise / resumo estatístico]
        ↓
[3. Exportação para dadosManut]
        ↓
[sistema downstream / BI / gestão de frota]
```

---

## Etapas e ordem de execução

### Pré-requisito único (feito uma vez)

Antes de qualquer execução diária, é necessário calibrar as coordenadas de tela:

1. Abrir `EXECUTAR.bat` → **Opção 1** — instala dependências Python (`pyautogui`, `pillow`, `pytesseract`, `pandas`, `openpyxl`)
2. Copiar `config.example.json` → `config.json` e revisar credenciais e caminhos
3. Abrir `EXECUTAR.bat` → **Opção 2** (`sigla_calibrador.py`) — posicionar o mouse nos pontos pedidos e confirmar com ENTER; isso grava as coordenadas em `config.json`

---

### Execução diária

#### Etapa 1 — Extração (`sigla_automacao_v2.py`)

**Como disparar:** `EXECUTAR.bat` → Opção 3 (fluxo completo) ou Opção 4 (malha já aberta)

**O que faz:**
- Abre o SIGLA, faz login e navega até a tela de programação do dia informado
- Varre cada trilho/carro horizontalmente ao longo do eixo de horários
- A cada posição, clica e lê o painel-resumo via OCR (Tesseract)
- Classifica cada registro como `MANUT`, `SERV`, `REV`, `V.Vazia`, `VAZIO` ou `ERRO`
- Aplica skip-ahead: ao detectar o fim de um bloco, pula direto para o horário seguinte (evita cliques desnecessários)
- Salva os resultados em `saida/DD-MM-AAAA/vN/`:
  - `SIGLA_Relatorio_DD-MM-AAAA.xlsx` — registros válidos
  - `SIGLA_Relatorio_DD-MM-AAAA.csv` — mesma base em CSV
  - `SIGLA_Relatorio_DD-MM-AAAA.json` — mesma base em JSON
  - `SIGLA_Relatorio_DD-MM-AAAA_descartados.csv` — linhas rejeitadas

**Entrada:** `config.json`, tela do SIGLA aberta e visível  
**Saída:** arquivos em `saida/`  
**Pré-condição:** `config.json` existir (calibração feita)

---

#### Etapa 2 — Análise (`analisar_relatorio.py`)

**Como disparar:** `EXECUTAR.bat` → Opção 5, ou via Cowork ("analise o relatório do dia X")

**O que faz:**
- Lê o `.xlsx` gerado na Etapa 1
- Normaliza durações (`HH:MM` → minutos)
- Gera estatísticas agregadas por trilho e por tipo de serviço
- Produz um Excel resumido com abas: Visão Geral, Por Trilho, Por Tipo

**Entrada:** `saida/.../SIGLA_Relatorio_DD-MM-AAAA.xlsx`  
**Saída:** `SIGLA_Relatorio_DD-MM-AAAA_RESUMO.xlsx` (mesma pasta)  
**Observação:** roda também no sandbox do Cowork (sem precisar do Windows)

---

#### Etapa 3 — Exportação para manutenção (`exportar_manut.py`)

**Como disparar:** executar `python exportar_manut.py` diretamente

**O que faz:**
- Varre todos os relatórios em `saida/` ainda não presentes em `dadosManut.xlsx`
- Aplica regras de negócio:
  - `MANUT` cobrindo o dia inteiro → `VTR`
  - `MANUT` ≥ 8h → `Reten.`; < 8h → ignorado
  - `REV` com veículo ≥ 7 dígitos → `REV.DD`; < 7 → `REV.RSD`
  - Empresa derivada do sufixo do veículo: F=RAF, U=Util, R=REX, S=Samp
- Gera `manut_para_importar_DDMMYYYY-DDMMYYYY.xlsx` para **revisão antes de importar**
- Após conferência manual, os dados são inseridos em `dadosManut.xlsx`

**Entrada:** `saida/**/*.xlsx`, `dadosManut.xlsx`  
**Saída:** `manut_para_importar_*.xlsx` (arquivo de revisão)  
**Observação:** etapa intencionalmente manual — o arquivo de revisão existe para evitar importações erradas

---

## Arquivos de configuração e saída

| Arquivo | Papel |
|---|---|
| `config.json` | Credenciais, coordenadas calibradas, parâmetros de varredura |
| `config.example.json` | Template para novo setup |
| `saida/DD-MM-AAAA/vN/` | Relatórios brutos da extração (xlsx, csv, json, descartados) |
| `dadosManut.xlsx` | Base consolidada de manutenções (destino final desta perna) |
| `manut_para_importar_*.xlsx` | Arquivo de revisão gerado antes de inserir em dadosManut |

---

## Pontos de atenção operacional

- **Não mexer no mouse** durante a Etapa 1 — a automação usa coordenadas absolutas de tela
- **Failsafe:** mover o mouse para o canto superior esquerdo aborta a execução imediatamente
- A senha está em `config.json` em texto plano — não compartilhar o arquivo; em ambientes compartilhados, migrar para variável de ambiente
- Cada reexecução do dia cria uma subpasta `v2`, `v3`... preservando o histórico
- A Etapa 3 é deliberadamente manual: conferir `manut_para_importar_*.xlsx` antes de qualquer importação

---

## Como o Cowork se encaixa

O Cowork (Claude) pode orquestrar as Etapas 2 e 3 remotamente, sem acesso ao desktop Windows:

- **Etapa 1** sempre exige a máquina Windows com SIGLA aberto (disparar via `EXECUTAR.bat`)
- **Etapa 2** (`analisar_relatorio.py`) roda no sandbox do Cowork sobre o `.xlsx` da pasta selecionada
- **Etapa 3** (`exportar_manut.py`) também pode ser executada pelo Cowork, que gera o arquivo de revisão para aprovação manual
