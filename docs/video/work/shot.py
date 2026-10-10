import asyncio, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width':1920,'height':1080})
        await pg.goto('http://127.0.0.1:8080/'); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='home.png')
        await pg.goto('http://127.0.0.1:8080/scoreboard'); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='score.png', full_page=True)
        await pg.goto('http://127.0.0.1:8080/replay/kubedeployer-pydantic-v2?speed=8'); 
        for i,t in enumerate([8000,12000,12000,12000]):
            await pg.wait_for_timeout(t); await pg.screenshot(path=f'rep{i}.png')
        print(await pg.evaluate("document.body.scrollHeight"))
        await b.close()
asyncio.run(main())
