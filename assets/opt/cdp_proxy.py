import asyncio
import logging
from aiohttp import web, ClientSession, WSMsgType

# 設定
LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 9222
TARGET_HOST = 'localhost'
TARGET_PORT = 9223
TARGET_BASE_URL = f'http://{TARGET_HOST}:{TARGET_PORT}'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def proxy_http(request):
    """通常のHTTPリクエストをプロキシする"""
    target_url = f"{TARGET_BASE_URL}{request.path_qs}"
    headers = dict(request.headers)
    headers['Host'] = f'{TARGET_HOST}:{LISTEN_PORT}'

    async with ClientSession() as session:
        try:
            async with session.request(
                request.method,
                target_url,
                headers=headers,
                data=await request.read()
            ) as resp:
                content = await resp.read()
                response = web.Response(
                    body=content,
                    status=resp.status,
                    headers=resp.headers
                )
                # Content-Encodingヘッダを削除してaiohttpに再圧縮させない
                if 'Content-Encoding' in response.headers:
                    del response.headers['Content-Encoding']
                return response
        except Exception as e:
            logging.error(f"Error proxying HTTP request: {e}")
            return web.Response(status=502, text="Bad Gateway")


async def proxy_websocket(request):
    """WebSocket接続をプロキシする"""
    # クライアントからのWebSocket接続を準備
    ws_server = web.WebSocketResponse()
    await ws_server.prepare(request)

    # ターゲットへのWebSocket接続を準備
    target_url = f"ws://{TARGET_HOST}:{TARGET_PORT}{request.path_qs}"
    headers = dict(request.headers)
    headers['Host'] = f'{TARGET_HOST}:{TARGET_PORT}'

    async with ClientSession() as session:
        try:
            async with session.ws_connect(target_url, headers=headers) as ws_client:
                logging.info("WebSocket connection established.")

                async def forward_to_client():
                    """ターゲット -> プロキシ -> クライアント"""
                    async for msg in ws_client:
                        if msg.type == WSMsgType.TEXT:
                            await ws_server.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await ws_server.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSED:
                            await ws_server.close()
                        elif msg.type == WSMsgType.ERROR:
                            await ws_server.close()
                    logging.info("Forward to client finished.")


                async def forward_to_target():
                    """クライアント -> プロキシ -> ターゲット"""
                    async for msg in ws_server:
                        if msg.type == WSMsgType.TEXT:
                            await ws_client.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await ws_client.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSED:
                            await ws_client.close()
                        elif msg.type == WSMsgType.ERROR:
                            await ws_client.close()
                    logging.info("Forward to target finished.")

                # 双方向のメッセージ転送を並行して実行
                await asyncio.gather(forward_to_client(), forward_to_target())

        except Exception as e:
            logging.error(f"Error proxying WebSocket: {e}")
        finally:
            if not ws_server.closed:
                await ws_server.close()
            logging.info("WebSocket connection closed.")

    return ws_server


async def handle_request(request):
    """HTTPとWebSocketのリクエストを振り分ける"""
    # WebSocketへのアップグレードリクエストか判定
    if 'Upgrade' in request.headers and request.headers.get('Upgrade', '').lower() == 'websocket':
        return await proxy_websocket(request)
    else:
        return await proxy_http(request)

async def main():
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', handle_request)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, LISTEN_HOST, LISTEN_PORT)
    await site.start()
    logging.info(f"CDP reverse proxy started on http://{LISTEN_HOST}:{LISTEN_PORT}")
    # サーバーを永続的に実行
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Proxy server shutting down.")
