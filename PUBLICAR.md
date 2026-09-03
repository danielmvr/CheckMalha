# Publicar a validação da malha como página online

A página é o `streamlit_app.py`. Ela não reimplementa nada: a cada 10 minutos
baixa o `execucao.XLS` do link compartilhado, chama o mesmo `main.py` do menu, e
embute o relatório HTML que ele gera. O texto do console fica no expansor
"Como este número foi apurado", que é a trilha de auditoria.

---

## 1. Rodar na máquina, para conferir antes de subir

```
pip install -r requirements.txt
set SIGLA_EXECUCAO_URL=https://... (o link compartilhado)
streamlit run streamlit_app.py
```

**É `streamlit run`, não `python`.** Chamado com `python streamlit_app.py` não
sobe servidor nenhum: o Streamlit roda em "bare mode" e cada chamada de `st.*`
imprime um aviso de ScriptRunContext, dando uma parede de warnings e página
nenhuma no fim. O app agora detecta isso, para na primeira linha e mostra o
comando certo. Para validar sem página, use `python main.py --remoto --sem-abrir`.

Servindo a rede interna, como o dash do BIFrotaManut:

```
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Sem a variável de ambiente, a chave "Baixar do link compartilhado" na barra
lateral já vem desligada e a página usa o `execucao.XLS` da pasta.

---

## 2. Repositório no GitHub

O Streamlit Cloud publica a partir de um repositório. Vai só o que a página
precisa. O `.gitignore` já exclui o resto.

```
main.py
streamlit_app.py
requirements.txt
src/            fonte_execucao.py fonte_remota.py localizador.py
                normalizador.py relatorio.py validador.py modelo.html
config/         caminhos.json regras_virada.json zonas.json siglas.json
exemplo/        para o autoteste
PUBLICAR.md     README.md
```

`config/siglas.json` é a cópia do catálogo de 295 siglas que vive na pasta do
extrator. O `zonas.json` tenta primeiro o original e cai nessa cópia, então a
regra de garagem continua ligada no deploy. **Se o catálogo mudar, copie de
novo**, senão a página fica com a versão velha:

```
copy "ControleRemoto SIGLA\siglas.json" "config\siglas.json"
```

Ficam de fora, e é de propósito:

- `execucao.XLS`, que vem do link em tempo de execução
- `dados_trabalho/` e `saida/`, refeitos a cada rodada. Desde 03/09/2026 os dois
  usam **nome fixo**: uma cópia de trabalho e um HTML por dia de operação,
  sobrescritos a cada execução. Era com carimbo de hora, e a 10 minutos por
  rodada isso acumulava 144 arquivos por dia; a limpeza liberou 252 MB
- `ControleRemoto SIGLA/` e `BIFrotaManut - 2/`, que são outros projetos
- os `.bak`

---

## 3. A URL não entra no repositório

O link carrega o token de compartilhamento: **quem tem o link tem o arquivo**.
Num repositório público isso vaza a malha. Então a URL vive fora do código.

No Streamlit Cloud, em Settings → Secrets:

```
SIGLA_EXECUCAO_URL = "https://bcoguan02-my.sharepoint.com/:x:/g/personal/..."
```

Local, para teste, dá para usar `.streamlit/secrets.toml` com a mesma linha. Esse
arquivo já está no `.gitignore`. O campo `execucao_url` do `config/caminhos.json`
existe só para uso local e deve ficar vazio no repositório.

---

## 4. Publicar

1. share.streamlit.io → New app
2. aponte para o repositório, branch e `streamlit_app.py`
3. Advanced settings → Secrets → cole a linha do `SIGLA_EXECUCAO_URL`
4. Deploy

---

## 5. O link já foi testado, e funciona

Confirmado em 03/09/2026, na máquina do Daniel: **o link entrega a planilha sem
login**, pela estratégia `download=1`. Não é preciso Microsoft Graph nem registro
de aplicativo no Entra ID.

O `fonte_remota.py` tenta, nesta ordem:

| Estratégia | O que faz |
|---|---|
| `download=1` | acrescenta o parâmetro na URL de compartilhamento |
| `download.aspx` | `/personal/<conta>/_layouts/15/download.aspx?share=<ID>` |
| `url crua` | para o caso de o link já apontar para o arquivo |

Ele só grava o arquivo se os primeiros bytes forem de planilha de verdade,
`D0 CF 11 E0` para o XLS antigo ou `PK` para xlsx. Se vier HTML, a mensagem é
**"não veio planilha, e sim text/html"**, e isso significa uma coisa só: o link
passou a pedir login. Nesse caso, no OneDrive, mudar o acesso do arquivo para
**"Qualquer pessoa com o link"**.

A gravação é atômica: o corpo desce para um `.part` na mesma pasta do destino e
é publicado com `os.replace`, que insiste seis vezes com espera crescente. Isso
existe porque no Windows o OneDrive e o antivírus seguram handle no arquivo por
frações de segundo, e aí a troca falha com `WinError 32`. Se as seis tentativas
falharem, o arquivo íntegro fica no `.part` e a mensagem diz por que não deu para
publicar, em vez de perder o download.

Para testar a URL isolada, sem rodar a página inteira:

```
python src/fonte_remota.py "https://..."
```

---

## 6. Dois avisos sobre expor a página

- **App público mostra a malha para quem tiver o endereço.** O Streamlit Cloud
  permite restringir por lista de e-mails, em Settings → Sharing. Vale usar.
- A URL do link fica no servidor, dentro dos Secrets, e nunca é enviada ao
  navegador de quem abre a página. Isso está correto por construção, mas só
  enquanto a URL não for escrita no código.

---

## 7. Como a atualização de 10 minutos funciona

- `streamlit_autorefresh` recarrega a página a cada 600 s.
- O `@st.cache_data` é chaveado pelo bloco de 10 minutos
  (`int(time.time() // 600)`), então o pipeline roda **uma vez por bloco**, e não
  a cada clique de filtro da barra lateral.
- "Atualizar agora" limpa o cache e força uma rodada fora do relógio.
- Se o pacote `streamlit-autorefresh` faltar, a página avisa na barra lateral que
  a atualização automática está desligada e continua funcionando no botão.

O download tem rede de segurança: se o link falhar e existir a cópia anterior no
cache, o `main.py` segue com ela e avisa na tela que pode estar velha.
