import asyncio
from app.providers import fetch_warrant, fetch_stock_quote

async def main():
    code = "067185"
    try:
        name, stock, metrics = await fetch_warrant(code)
        print('warrant_name=', name)
        print('parsed stock.code=', stock.code)
        print('parsed stock.name=', stock.name)
        print('metrics.exercise_ratio=', metrics.exercise_ratio)
    except Exception as e:
        print('fetch_warrant error:', repr(e))
        return

    try:
        stock2, warning = fetch_stock_quote(stock)
        print('fetch_stock_quote returned:')
        print('  code=', stock2.code)
        print('  name=', stock2.name)
        print('  price=', stock2.price)
        print('  open=', stock2.open)
        print('  high=', stock2.high)
        print('  low=', stock2.low)
        print('  volume=', stock2.volume)
        print('  source=', stock2.source)
        print('  quoted_at=', stock2.quoted_at)
        print('  warning=', warning)
    except Exception as e:
        print('fetch_stock_quote error:', repr(e))

if __name__ == '__main__':
    asyncio.run(main())
