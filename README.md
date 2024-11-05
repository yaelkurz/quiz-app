# Quiz App

This live quiz application is designed to provide interactive quiz sessions where moderators can manage events and engage with participants in real-time through WebSocket connections. Built for scalability and statelessness, the backend architecture aims to support high concurrency and seamless session handling without relying on persistent states.

For more details, check out the [client repository](https://github.com/yaelkurz/quiz-app-clients)


## Setup

1. Create a virtual environment:
    ```sh
    python -m venv .venv
    ```

2. Activate the virtual environment:
    - On Windows:
        ```sh
        .venv\Scripts\activate
        ```
    - On macOS/Linux:
        ```sh
        source .venv/bin/activate
        ```

3. Install the dependencies:
    ```sh
    pip install -r requirements.txt
    ```
4. Create a `.env` file in the root directory of the project and add the following environment variables:
    ```sh
    DB_URL = <postgras url> # e.g. postgresql://user:password@localhost:5432/quiz
    WEBSOCKET_TIMEOUT = 360 # seconds
    HEARTBEAT_INTERVAL = 1 # seconds
    REDIS_HOST = <redis host url> # e.g. localhost
    REDIS_PORT = <redis port> # default port is 6379
    SERVER_HOST = <server host >
    SERVER_PORT = <server port>
    ```

### Setting up the database
To create the postgres database, run the following commands:
```ptython
from db import DbManager
db = DbManager()
db.create_tables()
```

### Running the server
To run the server, execute the following command:
```python
import uvicorn
import os

SERVER_HOST = os.getenv("SERVER_HOST")
SERVER_PORT = os.getenv("SERVER_PORT")

uvicorn.run(
    "app.api.main:app",
    host=SERVER_HOST,
    port=int(SERVER_PORT),
    reload=True,
)
```


