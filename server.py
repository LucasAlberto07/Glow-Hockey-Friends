"""
Glow Hockey Online - SERVIDOR UNIFICADO (pronto para deploy)
--------------------------------------------------------------
Um único processo serve a página do jogo (index.html) e o WebSocket
da partida, na mesma porta. Isso simplifica tanto o teste local quanto
o deploy em serviços como Render, Railway ou Fly.io.

Requisitos:
    pip install -r requirements.txt

Uso local:
    python server.py
    (abre em http://localhost:8765)

Em produção, a maioria dos serviços de hospedagem define a porta através
da variável de ambiente PORT automaticamente — o código já respeita isso.
"""

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path

from aiohttp import web, WSMsgType

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / 'index.html'

WIDTH, HEIGHT = 800, 500
PADDLE_RADIUS = 25
PUCK_RADIUS = 15
GOAL_HALF = 80
FRICTION = 0.997
MAX_SPEED = 20
TICK_RATE = 60


class GameState:
    def __init__(self):
        self.paddles = {1: [100.0, HEIGHT / 2], 2: [WIDTH - 100.0, HEIGHT / 2]}
        self.prev_paddles = {1: [100.0, HEIGHT / 2], 2: [WIDTH - 100.0, HEIGHT / 2]}
        self.puck = [WIDTH / 2, HEIGHT / 2]
        self.puck_vel = [0.0, 0.0]
        self.score = {1: 0, 2: 0}
        self.reset_timer = 0.0
        self.reset_puck(direction=1)

    def reset_puck(self, direction=1):
        self.puck = [WIDTH / 2, HEIGHT / 2]
        speed = 5.0
        angle = math.radians(25)
        sign_y = 1 if int(time.time() * 1000) % 2 == 0 else -1
        self.puck_vel = [speed * math.cos(angle) * direction,
                          speed * math.sin(angle) * sign_y]

    def update_paddle(self, player, x, y):
        r = PADDLE_RADIUS
        y = max(r, min(HEIGHT - r, y))
        if player == 1:
            x = max(r, min(WIDTH / 2 - r, x))
        else:
            x = max(WIDTH / 2 + r, min(WIDTH - r, x))
        self.prev_paddles[player] = self.paddles[player][:]
        self.paddles[player] = [x, y]

    def step(self, dt):
        if self.reset_timer > 0:
            self.reset_timer -= dt
            return

        self.puck[0] += self.puck_vel[0]
        self.puck[1] += self.puck_vel[1]
        self.puck_vel[0] *= FRICTION
        self.puck_vel[1] *= FRICTION

        if self.puck[1] - PUCK_RADIUS < 0:
            self.puck[1] = PUCK_RADIUS
            self.puck_vel[1] *= -1
        elif self.puck[1] + PUCK_RADIUS > HEIGHT:
            self.puck[1] = HEIGHT - PUCK_RADIUS
            self.puck_vel[1] *= -1

        scored = None
        if self.puck[0] - PUCK_RADIUS < 0:
            if abs(self.puck[1] - HEIGHT / 2) < GOAL_HALF:
                scored = 2
            else:
                self.puck[0] = PUCK_RADIUS
                self.puck_vel[0] *= -1
        elif self.puck[0] + PUCK_RADIUS > WIDTH:
            if abs(self.puck[1] - HEIGHT / 2) < GOAL_HALF:
                scored = 1
            else:
                self.puck[0] = WIDTH - PUCK_RADIUS
                self.puck_vel[0] *= -1

        if scored:
            self.score[scored] += 1
            direction = 1 if scored == 1 else -1
            self.reset_puck(direction)
            self.reset_timer = 1.0

        for pid, ppos in self.paddles.items():
            dx = self.puck[0] - ppos[0]
            dy = self.puck[1] - ppos[1]
            dist = math.hypot(dx, dy)
            min_dist = PUCK_RADIUS + PADDLE_RADIUS
            if 0 < dist < min_dist:
                nx, ny = dx / dist, dy / dist
                overlap = min_dist - dist
                self.puck[0] += nx * overlap
                self.puck[1] += ny * overlap

                pvx = ppos[0] - self.prev_paddles[pid][0]
                pvy = ppos[1] - self.prev_paddles[pid][1]
                speed_in = abs(self.puck_vel[0] * nx + self.puck_vel[1] * ny)

                self.puck_vel[0] += nx * speed_in * 1.4 + pvx * 1.3
                self.puck_vel[1] += ny * speed_in * 1.4 + pvy * 1.3

                speed = math.hypot(*self.puck_vel)
                if speed > MAX_SPEED:
                    scale = MAX_SPEED / speed
                    self.puck_vel[0] *= scale
                    self.puck_vel[1] *= scale
                elif speed < 2 and self.reset_timer <= 0:
                    self.puck_vel[0] += nx * 2
                    self.puck_vel[1] += ny * 2

    def get_state(self):
        return {
            'paddles': self.paddles,
            'puck': self.puck,
            'score': self.score,
        }


state = GameState()
player_slots = {1: None, 2: None}


async def safe_send(ws, payload):
    try:
        await ws.send_str(payload)
    except Exception:
        pass


async def index_handler(request):
    return web.FileResponse(INDEX_PATH)


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)

    player_id = None
    for pid in (1, 2):
        if player_slots[pid] is None:
            player_id = pid
            break

    if player_id is None:
        await ws.send_json({'type': 'full'})
        await ws.close()
        return ws

    player_slots[player_id] = ws
    await ws.send_json({'type': 'welcome', 'player': player_id, 'width': WIDTH, 'height': HEIGHT})
    print(f'[Servidor] Jogador {player_id} conectou.')

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                if data.get('type') == 'move':
                    state.update_paddle(player_id, float(data['x']), float(data['y']))
            elif msg.type == WSMsgType.ERROR:
                break
    finally:
        if player_slots.get(player_id) is ws:
            player_slots[player_id] = None
        print(f'[Servidor] Jogador {player_id} desconectou.')

    return ws


async def game_loop(app):
    dt = 1.0 / TICK_RATE
    try:
        while True:
            start = time.time()
            state.step(dt)
            conns = [ws for ws in player_slots.values() if ws is not None]
            if conns:
                payload = json.dumps({'type': 'state', **state.get_state()})
                await asyncio.gather(*[safe_send(ws, payload) for ws in conns])
            elapsed = time.time() - start
            await asyncio.sleep(max(0.0, dt - elapsed))
    except asyncio.CancelledError:
        pass


async def start_background_tasks(app):
    app['game_loop_task'] = asyncio.create_task(game_loop(app))


async def cleanup_background_tasks(app):
    app['game_loop_task'].cancel()
    await app['game_loop_task']


def main():
    app = web.Application()
    app.router.add_get('/', index_handler)
    app.router.add_get('/ws', ws_handler)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    port = int(os.environ.get('PORT', sys.argv[1] if len(sys.argv) > 1 else 8765))
    print(f'[Servidor] Glow Hockey rodando em http://0.0.0.0:{port}')
    web.run_app(app, host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()