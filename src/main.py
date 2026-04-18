# --- Устаревший/некорректный вариант ---
# import uvicorn
# import asyncio
#
#
# async def main() -> None:
#     # uvicorn.run — синхронная функция, она сама создаёт event loop.
#     # Оборачивать её в async def и вызывать через asyncio.run бессмысленно
#     # (и даже вредно: вложенные event loop'ы приводят к RuntimeError).
#     uvicorn.run('application:get_app', host='localhost', port=8000, reload=True, factory=True)
#
# if __name__ == '__main__':
#     asyncio.run(main())
# -----------------------------------------

# Актуальный подход:
# - uvicorn.run вызывается напрямую, без asyncio-обёртки.
# - Путь к фабрике указан от корня пакета (`src.application:get_app`),
#   чтобы reload и импорт работали независимо от текущего каталога.
# - Для прод-запуска обычно используют отдельную команду
#   `uvicorn src.application:get_app --factory` без reload.
import uvicorn


def main() -> None:
    uvicorn.run(
        'src.application:get_app',
        host='127.0.0.1',
        port=8000,
        reload=True,
        factory=True,
    )


if __name__ == '__main__':
    main()
