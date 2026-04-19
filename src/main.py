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