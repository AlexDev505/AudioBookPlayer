"""

Uploads update to SourceForge.

"""

import argparse
import os
import sys

from paramiko import SSHClient
from scp import SCPClient
from version import Version

parser = argparse.ArgumentParser()
parser.add_argument("version", type=str)
args = parser.parse_args()

__version__ = Version.from_str(args.version)

if not os.environ.get("SOURCEFORGE_PASS"):
    print("SOURCEFORGE_PASS not set")
    exit()


def progress(filename, size, sent):
    sys.stdout.write(
        "%s progress: %.2f%%   \r"
        % (filename.decode(), float(sent) / float(size) * 100)
    )


print("Uploading update")
ssh = SSHClient()
ssh.load_system_host_keys()
ssh.connect(
    "frs.sourceforge.net",
    username="alexdev-py",
    password=os.environ["SOURCEFORGE_PASS"],
)
scp = SCPClient(ssh.get_transport(), progress=progress)
scp.put(
    f"updates/{__version__}",
    recursive=True,
    remote_path="/home/frs/project/audiobookplayer/",
)
scp.put(
    f"updates/updates.json",
    remote_path="/home/frs/project/audiobookplayer/",
)
scp.close()
