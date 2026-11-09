"""Check local Markdown links and figure paths in publishable repository files."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    failures = []
    checked = 0
    documents = sorted({ROOT / p for p in paths if p.endswith(".md")})
    for path in documents:
        # Ignore illustrative code, including the original proposed directory tree.
        text = re.sub(r"^```.*?^```[^\n]*", "", path.read_text(), flags=re.MULTILINE | re.DOTALL)
        for label, href in re.findall(r"!?\[([^\]]*)\]\(([^)]+)\)", text):
            href = href.strip().split(' "', 1)[0].strip("<>")
            link = urlsplit(href)
            if link.scheme or link.netloc:
                continue
            target = (path.parent / unquote(link.path)).resolve() if link.path else path
            checked += 1
            if not target.exists():
                failures.append(f"{path.relative_to(ROOT)}: missing {href} ({label})")
            elif link.fragment and target.suffix == ".md":
                headings = re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", target.read_text(), re.MULTILINE)
                anchors = set()
                occurrences = {}
                for heading in headings:
                    slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                    count = occurrences.get(slug, 0)
                    anchors.add(f"{slug}-{count}" if count else slug)
                    occurrences[slug] = count + 1
                if unquote(link.fragment) not in anchors:
                    failures.append(f"{path.relative_to(ROOT)}: missing anchor {href}")
    for failure in failures:
        print(failure)
    print(f"Checked {checked} local links/figures in {len(documents)} Markdown files.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
