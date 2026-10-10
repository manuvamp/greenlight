import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width':1920,'height':1080})
        await pg.goto('http://127.0.0.1:8080/replay/kubedeployer-pydantic-v2?speed=instant'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='full.png', full_page=True)
        # element boxes
        info = await pg.evaluate("""()=>[...document.querySelectorAll('section,.panel,.card,[class*=panel]')].slice(0,60).map(e=>[e.tagName,e.className.toString().slice(0,60),Math.round(e.getBoundingClientRect().x),Math.round(e.getBoundingClientRect().y+scrollY),Math.round(e.getBoundingClientRect().width),Math.round(e.getBoundingClientRect().height)])""")
        for i in info: print(i)
        await b.close()
asyncio.run(main())
