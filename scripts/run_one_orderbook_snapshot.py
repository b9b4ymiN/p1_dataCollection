import asyncio
import yaml
from datetime import datetime
from data_collector.optimized_collector import OptimizedDataCollector

async def main():
    cfg = yaml.safe_load(open('/app/config.yaml'))
    collector = OptimizedDataCollector(cfg)
    await collector.initialize()
    now = datetime.utcnow()
    symbol = cfg['collection']['symbols'][0]
    total = await collector.collect_order_book_optimized(symbol, now, now)
    print('INSERTED_ROWS:', total)

if __name__ == '__main__':
    asyncio.run(main())
