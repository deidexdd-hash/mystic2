"""
Веб-сервер для поддержки Render health checks
Не влияет на функциональность бота, только предоставляет HTTP endpoint
"""
import os
import logging
from aiohttp import web
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
log = logging.getLogger(__name__)


async def health_check(request):
    """Health check endpoint для Render"""
    return web.json_response({
        'status': 'ok',
        'service': 'mystic-bot',
        'message': 'Bot is running'
    })


async def root_handler(request):
    """Корневой endpoint"""
    return web.Response(text="Mystic Numerology Bot is running! 🔮")


def create_app():
    """Создание aiohttp приложения"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', root_handler)
    return app


async def start_web_server(port: int = 8080):
    """Запуск веб-сервера"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"🌐 Веб-сервер запущен на порту {port}")
    log.info(f"✅ Health check доступен на http://0.0.0.0:{port}/health")
    return runner


async def run_forever():
    """Держит сервер запущенным"""
    port = int(os.environ.get("PORT", 8080))
    runner = await start_web_server(port)
    
    try:
        # Держим сервер активным
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        log.info("Остановка веб-сервера...")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(run_forever())
