from fastapi import APIRouter, WebSocket
from fastapi.responses import HTMLResponse

from app.value_trace import ValueQueue


class WebsocketsRouter:
    def __init__(self, q: ValueQueue):
        self.q = q

    def create(self):
        router = APIRouter(
            prefix="/ws",
            tags=["websockets"],
            dependencies=[]
        )

        @router.get("/")
        async def web():
            html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:9330/ws/");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
            """
            return HTMLResponse(html)

        @router.websocket("/")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            while True:
                # data = await websocket.receive_text()
                # await websocket.send_text(data)
                data = await self.q.get_data()
                await websocket.send_text(str(data))
                self.q.reset()

        return router
