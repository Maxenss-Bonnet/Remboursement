import os
import glob
import urllib.request
import urllib.error


KROKI_ENDPOINT = "https://kroki.io/plantuml/svg"


def render_puml_to_svg(src_path: str, out_path: str) -> None:
    with open(src_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(KROKI_ENDPOINT, data=data, headers={"Content-Type": "text/plain"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        svg = resp.read()
    with open(out_path, "wb") as f:
        f.write(svg)


def main() -> None:
    os.makedirs("diagrams-out", exist_ok=True)
    puml_files = sorted(glob.glob(os.path.join("diagrams", "*.puml")))
    failed = []
    for puml in puml_files:
        base = os.path.basename(puml)
        name, _ = os.path.splitext(base)
        out_svg = os.path.join("diagrams-out", f"{name}.svg")
        try:
            render_puml_to_svg(puml, out_svg)
            print(f"OK {base} -> {out_svg}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception) as e:
            failed.append((puml, str(e)))
            print(f"FAIL {base}: {e}")

    if failed:
        print("\nSome diagrams failed to render:")
        for p, err in failed:
            print(f" - {p}: {err}")


if __name__ == "__main__":
    main()


