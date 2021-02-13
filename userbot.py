import json
import os
from json.decoder import JSONDecodeError

from aiohttp import web
from aiohttp.http_websocket import WSMsgType
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import GetGroupCallRequest
from telethon.tl.functions.phone import JoinGroupCallRequest
from telethon.tl.types import DataJSON

load_dotenv()

client = TelegramClient(
    'session', os.environ['API_ID'], os.environ['API_HASH'],
)
client.start()


async def get_entity(chat):
    try:
        return await client.get_input_entity(chat['id'])
    except ValueError:
        if 'username' in chat:
            return await client.get_entity(chat['username'])
        raise


async def join_call(data):
    chat = await get_entity(data['chat'])
    full_chat = await client(GetFullChannelRequest(chat))
    call = await client(GetGroupCallRequest(full_chat.full_chat.call))

    result = await client(
        JoinGroupCallRequest(
            call=call.call,
            muted=False,
            params=DataJSON(
                data=json.dumps({
                    'ufrag': data['ufrag'],
                    'pwd': data['pwd'],
                    'fingerprints': [{
                        'hash': data['hash'],
                        'setup': data['setup'],
                        'fingerprint': data['fingerprint'],
                    }],
                    'ssrc': data['source'],
                }),
            ),
        ),
    )

    transport = json.loads(result.updates[0].call.params.data)['transport']

    return {
        '_': 'get_join',
        'data': {
            'chat_id': data['chat']['id'],
            'transport': {
                'ufrag': transport['ufrag'],
                'pwd': transport['pwd'],
                'fingerprints': transport['fingerprints'],
                'candidates': transport['candidates'],
            },
        },
    }


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except JSONDecodeError:
                await ws.close()
                break

            response = None
            if data['_'] == 'join':
                response = await join_call(data['data'])

            if response is not None:
                await ws.send_json(response)

    return ws


def main():
    app = web.Application()
    app.router.add_route('GET', '/', websocket_handler)
    web.run_app(app, port=1390)


if __name__ == '__main__':
    main()
