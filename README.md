# Glow Hockey Online — versão pronta para deploy

Versão unificada: um único servidor Python (`server.py`) serve tanto a
página do jogo (`index.html`) quanto a conexão WebSocket, na mesma porta.
Isso torna o teste local mais simples e o deploy possível em um único
serviço de hospedagem.

## Testar localmente

```bash
pip install -r requirements.txt
python server.py
```

Abra `http://localhost:8765` em duas abas do navegador (uma para cada
jogador) — não precisa mais rodar `python -m http.server` separado. O
campo de endereço do servidor já vem preenchido automaticamente.

## Jogar com um amigo na mesma rede Wi-Fi

Descubra o IP local do computador que roda o servidor (`ipconfig` no
Windows, procurando a seção do adaptador Wi-Fi) e no celular acesse:

```
http://SEU_IP:8765
```

O campo de conexão já vem preenchido certo automaticamente.

## Deploy para jogar pela internet (sem depender do seu PC ligado)

A opção mais simples e com plano gratuito é o **Render**:

1. Crie uma conta em https://render.com (dá para logar com GitHub).
2. Suba esta pasta (`server.py`, `index.html`, `requirements.txt`,
   `render.yaml`) para um repositório no GitHub.
3. No painel do Render, clique em **New +** → **Web Service**, conecte
   o repositório do GitHub. O Render detecta o `render.yaml`
   automaticamente com as configurações certas (comando de build e de
   start). Se preferir configurar manualmente:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Environment:** Python 3
4. Depois do deploy, o Render te dá uma URL pública tipo
   `https://glow-hockey.onrender.com`. Compartilhe esse link com seu
   amigo — cada um abre a URL no navegador (PC ou celular) e clica em
   "Entrar na partida". O endereço do WebSocket é preenchido
   automaticamente como `wss://glow-hockey.onrender.com/ws`.

**Observação sobre o plano gratuito do Render:** o serviço "dorme" após
alguns minutos sem uso, e demora ~30-60s para acordar na próxima
conexão. Para jogos ocasionais isso não é problema; se quiser sempre
ativo, existem planos pagos ou alternativas como Railway ou Fly.io.

### Alternativas ao Render

- **Railway** (https://railway.app) — fluxo parecido (conecta o
  repositório do GitHub, detecta `requirements.txt` e roda
  `python server.py`).
- **Fly.io** — mais controle, exige `fly launch` via linha de comando,
  bom se quiser manter o servidor sempre ativo com custo baixo.
- **VPS próprio** (ex: um droplet da DigitalOcean, ou uma AWS
  EC2/Lightsail) — mais trabalho para configurar (abrir porta,
  processo em background com `systemd` ou `screen`), mas dá controle
  total e evita o "sleep" do plano gratuito.

## Fluxo de trabalho para ir melhorando aos poucos

1. Mantenha o projeto num repositório Git (GitHub, GitLab, etc.).
2. Faça as alterações e teste localmente com `python server.py` antes
   de subir.
3. Quando estiver satisfeito, dê `git push`. Se usar Render ou Railway
   conectado ao repositório, o deploy da nova versão acontece
   automaticamente a cada push.
4. Ideias de próximas melhorias:
   - Tela de "vitória" ao atingir um número de gols, com botão de
     revanche.
   - Efeitos sonoros ao bater no disco e ao marcar gol.
   - Sistema de salas com código, para várias partidas simultâneas no
     mesmo servidor (hoje só suporta uma partida de 2 jogadores por
     vez).
   - Reconexão automática se a internet cair no meio da partida.
   - Placar de vitórias entre os dois jogadores ao longo de várias
     partidas.

## Detalhes técnicos

- **server.py**: usa `aiohttp` para servir tanto a rota HTTP `/`
  (retorna `index.html`) quanto a rota WebSocket `/ws`. A física do
  disco roda em uma tarefa assíncrona (`game_loop`) a 60 atualizações
  por segundo, autoritativa (o servidor decide a posição real do disco
  e do placar — os clientes só mostram e enviam a posição do próprio
  rebatedor).
  Lê a porta da variável de ambiente `PORT` quando disponível (usada
  por serviços de hospedagem como Render/Railway), com fallback para
  8765 localmente.
- **index.html**: cliente único em HTML/CSS/JS, sem build. Detecta
  automaticamente se deve usar `ws://` (local) ou `wss://` (quando a
  própria página é servida via HTTPS, como em produção) e monta o
  endereço do WebSocket a partir do host atual — por isso não é
  necessário digitar o endereço manualmente na maioria dos casos; o
  campo continua editável para casos especiais (ex: apontar para outro
  servidor durante testes).