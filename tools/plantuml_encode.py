import sys
import zlib
import os


def encode6bit(b: int) -> str:
    if b < 10:
        return chr(48 + b)
    b -= 10
    if b < 26:
        return chr(65 + b)
    b -= 26
    if b < 26:
        return chr(97 + b)
    b -= 26
    if b == 0:
        return '-'
    if b == 1:
        return '_'
    return '?'


def append3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return ''.join([
        encode6bit(c1 & 0x3F),
        encode6bit(c2 & 0x3F),
        encode6bit(c3 & 0x3F),
        encode6bit(c4 & 0x3F)
    ])


def plantuml_encode(data: bytes) -> str:
    # Raw deflate (-15) without zlib header as required by PlantUML
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(data) + compressor.flush()
    res = []
    # Pad compressed data to multiple of 3 bytes for encoding
    i = 0
    while i < len(compressed):
        b1 = compressed[i]
        b2 = compressed[i + 1] if i + 1 < len(compressed) else 0
        b3 = compressed[i + 2] if i + 2 < len(compressed) else 0
        res.append(append3bytes(b1, b2, b3))
        i += 3
    return ''.join(res)


def main(paths: list[str]) -> None:
    if not paths:
        print("Usage: python tools/plantuml_encode.py <file1.puml> <file2.puml> ...", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        with open(path, 'rb') as f:
            content = f.read()
        encoded = plantuml_encode(content)
        print(f"{os.path.basename(path)}={encoded}")


if __name__ == "__main__":
    main(sys.argv[1:])


