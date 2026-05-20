"""arXiv paper download and extraction utilities."""

import re
import ssl
import tarfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm


def _create_session() -> requests.Session:
    """Create a requests session with SSL workarounds for servers that drop TLS connections early."""
    session = requests.Session()
    try:
        from urllib3.util.ssl_ import create_urllib3_context

        ctx = create_urllib3_context()
        if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
            ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF

        class _TLSAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs["ssl_context"] = ctx
                return super().init_poolmanager(*args, **kwargs)

        session.mount("https://", _TLSAdapter())
    except Exception:
        pass
    return session


def get_arxiv_metadata(arxiv_id: str) -> dict | None:
    """
    Get paper metadata from arXiv API.

    Args:
        arxiv_id: arXiv paper ID (e.g., 2307.16789 or 2307.16789v2)

    Returns:
        Dictionary with 'arxiv_id', 'published', and 'category' keys, or None if failed.
    """
    # Strip version for API query (API returns latest version info)
    base_id = re.sub(r"v\d+$", "", arxiv_id)
    MY_API_URL = f"http://export.arxiv.org/api/query?id_list={base_id}"

    try:
        session = _create_session()
        response = session.get(MY_API_URL, timeout=10)
        response.raise_for_status()

        # Parse XML response
        root = ElementTree.fromstring(response.content)

        # Define namespace
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        # Find the entry
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None

        # Get published date
        published_elem = entry.find("atom:published", ns)
        if published_elem is None or published_elem.text is None:
            return None

        # Parse date: 2025-11-05T12:34:56Z -> "5 Nov 2025"
        pub_date = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
        formatted_date = pub_date.strftime("%-d %b %Y")

        # Get primary category
        category_elem = entry.find("arxiv:primary_category", ns)
        category = category_elem.get("term") if category_elem is not None else None

        return {
            "arxiv_id": arxiv_id,
            "published": formatted_date,
            "category": category,
        }

    except Exception:
        return None


def parse_arxiv_input(input_str: str) -> str | None:
    """
    Parse arXiv input and return the arXiv ID.

    Supports:
        - 2307.16789 or 2307.16789v2 (plain ID)
        - https://arxiv.org/abs/2307.16789
        - https://arxiv.org/pdf/2307.16789
        - https://arxiv.org/src/2307.16789
        - https://arxiv.org/html/2307.16789
        - arxiv.org/xxx/2307.16789

    Returns None if input is not an arXiv reference.
    """
    input_str = input_str.strip()

    # Pattern for arXiv ID: YYMM.NNNNN or YYMM.NNNNNvN
    arxiv_id_pattern = r"(\d{4}\.\d{4,5}(?:v\d+)?)"

    # Check if it's a URL
    if "arxiv.org" in input_str.lower():
        # Extract ID from URL path
        match = re.search(arxiv_id_pattern, input_str)
        if match:
            return match.group(1)
        return None

    # Check if it's a plain arXiv ID
    if re.match(r"^" + arxiv_id_pattern + r"$", input_str):
        return input_str

    return None


def download_arxiv_source(arxiv_id: str, output_dir: Path) -> Path:
    """
    Download arXiv source files and return the path to the archive.

    Args:
        arxiv_id: arXiv paper ID (e.g., 2307.16789 or 2307.16789v2)
        output_dir: Directory to save the archive (default: tex/)

    Returns:
        Path to the downloaded .tar.gz file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Construct download URL
    src_url = f"https://arxiv.org/src/{arxiv_id}"

    print(f"Downloading arXiv source: {arxiv_id}")
    print(f"  URL: {src_url}")

    try:
        session = _create_session()
        # First, make a HEAD request to get the actual filename (with version)
        head_response = session.head(src_url, timeout=30, allow_redirects=True)
        head_response.raise_for_status()

        # Extract actual filename from content-disposition header
        # Format: attachment; filename="arXiv-2307.16789v2.tar.gz"
        content_disp = head_response.headers.get("content-disposition", "")
        actual_filename = None
        if "filename=" in content_disp:
            match = re.search(r'filename="?([^";\s]+)"?', content_disp)
            if match:
                actual_filename = match.group(1)

        # Use actual filename if available, otherwise construct from ID
        if actual_filename:
            archive_name = actual_filename
            # Extract actual version from filename for display
            version_match = re.search(r"v(\d+)", actual_filename)
            if version_match and "v" not in arxiv_id:
                print(f"  Latest version: v{version_match.group(1)}")
        else:
            archive_name = f"arXiv-{arxiv_id}.tar.gz"

        archive_path = output_dir / archive_name

        # Skip if already downloaded
        if archive_path.exists():
            print(f"Already downloaded: {archive_path}")
            return archive_path

        # Download with streaming to handle large files
        response = session.get(src_url, stream=True, timeout=60)
        response.raise_for_status()

        # Get file size for progress bar
        total_size = int(response.headers.get("content-length", 0))

        # Write to file with progress
        with open(archive_path, "wb") as f:
            if total_size > 0:
                with tqdm(
                    total=total_size, unit="B", unit_scale=True, desc="Downloading"
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"  Saved to: {archive_path}")
        return archive_path

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise FileNotFoundError(f"arXiv paper not found: {arxiv_id}")
        raise RuntimeError(f"Failed to download arXiv source: {e}")
    except Exception as e:
        # Clean up partial download
        if "archive_path" in locals() and archive_path.exists():
            archive_path.unlink()
        raise RuntimeError(f"Download failed: {e}")


def extract_archive(archive_path: Path) -> Path:
    """Extract tar.gz archive and return the extracted directory."""
    extract_dir = archive_path.parent

    # Determine the folder name (remove .tar.gz or .tgz)
    name = archive_path.name
    if name.endswith(".tar.gz"):
        folder_name = name[:-7]
    elif name.endswith(".tgz"):
        folder_name = name[:-4]
    else:
        folder_name = name

    target_dir = extract_dir / folder_name

    # Extract if not already extracted
    if not target_dir.exists():
        print(f"Extracting {archive_path.name}...")
        with tarfile.open(archive_path, "r:gz") as tar:
            # Check if archive has a top-level directory
            members = tar.getnames()
            has_top_dir = (
                all(
                    m.startswith(members[0].split("/")[0] + "/")
                    or m == members[0].split("/")[0]
                    for m in members
                )
                if members
                else False
            )

            if has_top_dir:
                # Extract directly, top-level dir exists
                tar.extractall(path=extract_dir)
            else:
                # Create target dir and extract into it
                target_dir.mkdir(parents=True, exist_ok=True)
                tar.extractall(path=target_dir)
        print(f"Extracted to: {target_dir}")
    else:
        print(f"Already extracted: {target_dir}")

    return target_dir
