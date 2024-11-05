import os


if __name__ == "__main__":
    import uvicorn

    SERVER_HOST = os.getenv("SERVER_HOST")
    SERVER_PORT = os.getenv("SERVER_PORT")
    uvicorn.run(
        "app.api.main:app",
        host=SERVER_HOST,
        port=int(SERVER_PORT),
        reload=True,
    )
