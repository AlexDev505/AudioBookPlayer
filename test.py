import re
import time

import requests

H = {
    "origin": "https://akniga.org",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}
url = "https://akniga.org/domagoj-kurmaic-aka-nobody103-mat-uchenya"
TOKEN_URL = "https://akniga.org/ajax/player/token"
BOOK_URL = "https://akniga.org/ajax/b/{bid}"

s = requests.Session()

resp = s.get(url)
PHPSID = re.search(r"PHPSESSID=(.+?);", resp.headers["Set-Cookie"]).group(1)
SK = re.search(r"LIVESTREET_SECURITY_KEY = '(.+?)'", resp.text).group(1)
BID = re.search(r'data-bid="(.+?)"', resp.text).group(1)

resp = s.post(
    TOKEN_URL,
    data={
        "security_ls_key": SK,
        "bid": BID,
        "ts": int(time.time() * 1000),
    },
    headers=H,
)

token = resp.json()["token"]
print(token)

resp = s.post(
    BOOK_URL.format(bid=BID),
    data={"token": token, "security_ls_key": SK, "bid": BID, "hls": False},
    headers=H,
)

import json

data = resp.json()
data["items"] = json.loads(data["items"])
print(json.dumps(data, indent=4, ensure_ascii=False))

msg = "ymXEKzvUkuo5G03.1C159BD535E9793"
import base64
import hashlib

from Crypto.Cipher import AES
