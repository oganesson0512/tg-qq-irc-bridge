import asyncio
import html
import re

import aiohttp
from aiohttp import ClientWebSocketResponse


def create_qq_bot(base_uri, group_id, blacklist=None, password=None, loop=None):
    if blacklist is None:
        blacklist = []
    if base_uri.endswith('/'):
        base_uri = base_uri.rstrip('/')

    if not loop:
        loop = asyncio.get_event_loop()

    receive_queue = asyncio.Queue()
    send_queue = asyncio.Queue()

    session = aiohttp.ClientSession()

    async def receive_msg(base_uri):
        async with session.ws_connect(base_uri + '/event/') as ws:  # type: ClientWebSocketResponse
            api_ws = await session.ws_connect(base_uri + '/api/')
            while True:
                message = await ws.receive_json()
                print('recv from qq:')
                print(message)
                if message['post_type'] == "message" and message['message_type'] == "group" \
                        and 'group_id' in message and message['group_id'] == group_id:
                    if message['user_id'] in blacklist:
                        continue
                    text_message = message['message']
                    text_message = re.sub(
                        r"\[CQ:face,id=\d+\]",
                        " ",
                        text_message
                    )
                    text_message = re.sub(
                        r"\[CQ:image,file=\w+\.gif,url=[^\]]+\]",
                        " ",
                        text_message
                    )
                    text_message = text_message.strip()
                    if text_message:
                        await receive_msg_content(text_message, message['user_id'], api_ws)

    async def receive_msg_content(text_messages, user_id, api_ws):
        for text_message in text_messages.splitlines():
            call = {
                "action": "get_group_member_info",
                "params": {
                    "group_id": group_id,
                    "user_id": user_id
                }
            }
            await api_ws.send_json(call)
            resp = await api_ws.receive_json()
            author = resp['data']['card']
            if not author:
                author = resp['data']['nickname']
            if author in ['qqcl','tgcl']:
                final_msg = ' {msg}'.format(author=author, msg=html.unescape(text_message))
            else:
                final_msg = '{author}: {msg}'.format(author=author, msg=html.unescape(text_message))
            await receive_queue.put(final_msg)

    async def send_msg(base_uri):
        async with session.ws_connect(base_uri + '/api/') as ws:  # type: ClientWebSocketResponse
            while True:
                raw_msg = await send_queue.get()
                data = {
                    "action": "send_group_msg",
                    "params": {
                        "group_id": group_id,
                        "message": raw_msg,
                        "auto_escape": "false"
                    }
                }
                await ws.send_json(data)
                resp = await ws.receive_json()
                print(resp)

    loop.create_task(receive_msg(base_uri))
    loop.create_task(send_msg(base_uri))

    return receive_queue, send_queue
