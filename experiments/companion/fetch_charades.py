"""Fetch a few named public research clips with HTTP ranges, never the 16 GB archive."""

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://ai2-public-datasets.s3-us-west-2.amazonaws.com/charades/Charades_v1_480.zip"


class RemoteZip(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        with urlopen(Request(url, method="HEAD"), timeout=30) as response:
            self.size = int(response.headers["content-length"])
        self.position = 0
        self.downloaded = 0

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        self.position = (
            offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        )
        return self.position

    def tell(self):
        return self.position

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if size == 0:
            return b""
        if size > 8 * 1024**2 or self.downloaded + size > 32 * 1024**2:
            raise ValueError("Range download budget exceeded; refusing the full archive")
        start = self.position
        request = Request(self.url, headers={"Range": f"bytes={start}-{start + size - 1}"})
        with urlopen(request, timeout=45) as response:
            if response.status != 206 or not response.headers.get("Content-Range", "").startswith(
                f"bytes {start}-"
            ):
                raise ValueError("Server did not honor byte range; download refused")
            data = response.read(size + 1)
        if len(data) != size:
            raise ValueError("Incomplete or oversized range response")
        self.position += len(data)
        self.downloaded += len(data)
        return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ids", nargs="+", default=["VXJS4", "BM3UJ", "I7AS7", "MZ3X9", "VFAE3", "FPJ9D"]
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    remote = RemoteZip(URL)
    records = []
    with zipfile.ZipFile(remote) as archive:
        for identifier in args.ids:
            matches = [
                row for row in archive.infolist() if Path(row.filename).name == f"{identifier}.mp4"
            ]
            if len(matches) != 1:
                raise ValueError(f"Expected one archive member for {identifier}")
            info = matches[0]
            if info.file_size > 8 * 1024**2:
                raise ValueError("Selected clip exceeds 8 MiB limit")
            data = archive.read(info)
            (args.output / f"{identifier}.mp4").write_bytes(data)
            records.append(
                {
                    "id": identifier,
                    "member": info.filename,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
            print(f"Downloaded {identifier}: {len(data)} bytes", flush=True)
    (args.output / "sources.json").write_text(
        json.dumps(
            {
                "url": URL,
                "source": "Charades / Hollywood in Homes, Sigurdsson et al. 2016",
                "archive_bytes": remote.size,
                "downloaded_bytes": remote.downloaded,
                "clips": records,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
