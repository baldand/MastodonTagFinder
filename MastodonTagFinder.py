"""
MastodonTagFinder.py

About
-----

This program connects to the public feed of specified Mastodon-like servers.

It also connects to specified Mastodon user accounts with at least read:follows + read:search rights.

Any posts with a tag followed by a user are added to the federated feed of that user's 
instance using the Mastodon search API call. This will cause those posts to appear 
in the user's home feed.

Tag follow list are periodically rechecked so that users can add and remove tags. 

Data usage warning
------------------

If you connect to a large number of high volume servers,
incoming bandwidth will be quite significant (100s of KB per second or more). This will work best when incoming data is not charged.

CPU usage should be relatively low (few percent on one core) and also memory usage.

Dependencies
-----
Python 3.8
aiohttp

Usage
-----
Two files must be supplied at startup:

- List of servers, one name per line

- List of users, "server,access_token" per line

Note that access tokens must include read:follows + read:search rights

License
-------
Copyright 2022 Andrew Baldwin 
(Fediverse: @baldand@mstdn.thndl.com)

Redistribution and use in source and binary forms, with or without modification, 
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, 
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, 
this list of conditions and the following disclaimer in the documentation 
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors 
may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, 
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, 
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

import argparse
import asyncio
import datetime
import sys
import traceback

try:
    import aiohttp
except:
    print("This script depends on aiohttp.\nPlease add that to your python installation,\nfor example by using: 'pip install aiohttp'")
    sys.exit(-1)

DUPLICATE_HISTORY_LENGTH = 1000
TIME_BETWEEN_STATS = 5*60
TIME_BETWEEN_TAG_REFRESH = 5*60
TIME_BETWEEN_RECONNECT = 30

post_count = 0
servers = {}
total = 0
posts = {}
posts_order = [] 
users = []
streams = []

def getlist(data:bytes, field:bytes):
    field_start = data.find(field)
    if field_start == -1: return []
    empty = data.find(b"[]", field_start+len(field), field_start+len(field)+3)
    if empty != -1: return [] # Empty list
    # Otherwise assume content in list
    list_start = data.find(b"[", field_start+len(field))
    list_end = data.find(b"]", list_start+1)
    ptr = list_start+1
    items = []
    while True:
        entry_start = data.find(b"{", ptr, list_end)
        if entry_start == -1: break
        ptr = entry_start + 1
        entry_end = data.find(b"}", ptr, list_end)
        ptr = entry_end + 1
        tagname,_ = getfield(data[entry_start:entry_end],b"\"name\":")
        items += [tagname]
    return items

def getfield(data:bytes, field:bytes, offset=0):
    field_start = data.find(field, offset)
    if field_start == -1: return None, None
    if data.find(b"null", field_start+len(field), field_start+len(field)+4) != -1:
        return None, None
    value_start = data.find(b"\"", field_start+len(field))
    if value_start == -1: return None, None
    value_end = data.find(b"\"", value_start+1)
    if value_end == -1: return None, None
    return data[value_start+1:value_end], value_end + 1

class UserConnection:
    def __init__(self, server:str, user_token:str):
        self.server = server.strip()
        self.user_token = user_token.strip()
        self.sender = None
        self.follower = None
        self.tags = set()
        self.posts = asyncio.Queue()

    async def update(self):
        self.tags = await self.followed_tags()
        print(f"{datetime.datetime.now()}: Tags followed: {self.tags}")
        self.follower = asyncio.create_task(self.update_tags())
        self.sender = asyncio.create_task(self.send_posts())

    async def update_tags(self):
        while True:
            await asyncio.sleep(TIME_BETWEEN_TAG_REFRESH)
            self.tags = await self.followed_tags()

    async def queue_post(self, tags, url:str):
        intersection = self.tags.intersection(tags)
        if len(intersection)>0:
            print(f"{datetime.datetime.now()}: Sending {url.decode()} with tags {intersection} to {self.server}")
            await self.posts.put(url)

    async def send_posts(self):
        while True:
            post_url = await self.posts.get()
            await self.search(post_url.decode())

    async def search(self, url:str):
        timeout = aiohttp.ClientTimeout()
        auth = {"Authorization":f"Bearer {self.user_token}"}
        async with aiohttp.ClientSession(timeout=timeout, headers=auth) as session:
            request = f'https://{self.server}/api/v2/search?q={url}&resolve=True'
            async with session.get(request) as response:
                while True:
                    chunk = await response.content.readline()
                    if len(chunk)==0: break
            
    async def followed_tags(self):
        timeout = aiohttp.ClientTimeout()
        auth = {"Authorization":f"Bearer {self.user_token}"}
        async with aiohttp.ClientSession(timeout=timeout, headers=auth) as session:
            async with session.get(f'https://{self.server}/api/v1/followed_tags') as response:
                chunk = await response.content.readline()
                if len(chunk)==0: return None
                tags = set()
                offset = 0
                while True:
                    next_tag, offset = getfield(chunk, b"\"name\":", offset)
                    if next_tag is not None: 
                        tags.add(next_tag.decode().lower())
                    else: break
                return tags
        return None

async def process_update(data):
    global total, posts_order, post_count
    try:
        url,_ = getfield(data, b"\"uri\":")
        if url is not None:
            # Is this new or a duplicate?
            if url in posts:
                return
            else:
                posts[url] = [url,[]]
                posts_order += [url]
                while len(posts_order)>DUPLICATE_HISTORY_LENGTH:
                    del posts[posts_order.pop(0)]
            server = url[8:].split(b"/")[0]
            total += 1
            if server in servers:
                servers[server]+=1
            else:
                servers[server]=1
            post_count += 1
            tags = set([t.decode().lower() for t in getlist(data, b"\"tags\":")])
            if len(tags)>0:
                for user in users:
                    await user.queue_post(tags, url)
    except:
        print("Exception:")
        traceback.print_exc()

async def server_stream(server):
    while True:
        try:
            print(f"{datetime.datetime.now()}: Connecting to {server}")
            timeout = aiohttp.ClientTimeout(connect=10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f'https://{server}/api/v1/streaming/public') as response:
                    print(f"{datetime.datetime.now()}: Connected to {server}")
                    get_next = False
                    while True:
                        chunk = await response.content.readline()
                        if len(chunk)==0: break
                        if chunk==b'event: update\n':
                            get_next = True
                        if chunk[:5]==b'data:' and get_next:
                            await process_update(chunk[5:])
                            get_next = False
        except:
            print("Exception:")
            traceback.print_exc()

        await asyncio.sleep(TIME_BETWEEN_RECONNECT)


def top_servers():
    global post_count
    server_list = [(count, server) for server,count in servers.items()]
    server_list.sort()
    server_list.reverse()
    print(f"{datetime.datetime.now()}: Posts:{post_count}\nTop 10 posting servers:")
    for count, server in server_list[:10]:
        print(f"  {server.decode()} : {count}")
    servers.clear()
    post_count = 0

def command_line():
    parser = argparse.ArgumentParser(
                        prog = 'MastodonTagFinder',
                        description = 'Find tagged posts user follow, and bring those to their instances',
                        epilog = 'By Andrew Baldwin (baldand@mstdn.thndl.com)')
    parser.add_argument('server_list_file', help="List of servers to connect to, one per line")
    parser.add_argument('user_list_file', help="List of users in format \"serveraddress,access token\"") 
    args = parser.parse_args()
    return args

async def main(loop):
    args = command_line()

    for user_info in open(args.user_list_file):
        user_info_clean = user_info.strip()
        if len(user_info_clean)==0: continue
        user = UserConnection(*user_info_clean.split(","))
        await user.update()
        users.append(user)

    for server_address in open(args.server_list_file):
        server_address_clean = server_address.strip()
        if len(server_address_clean)==0: continue
        stream = asyncio.create_task(server_stream(server_address_clean))
        streams.append(stream)

    while True:
        await asyncio.sleep(TIME_BETWEEN_STATS)
        top_servers()

loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))
