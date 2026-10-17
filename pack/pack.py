"""Build the Aswan Projects USB folder (run on this Linux machine, with internet).

    python3 pack/pack.py docs    copy each project's 3 PDFs into Docs/ (commit them for the hosted site)
    python3 pack/pack.py build   build dist/ASWAN-KIT, the folder to copy onto each USB
    python3 pack/pack.py zip     zip dist/ASWAN-KIT into dist/ASWAN-KIT.zip (the Drive backup)
    python3 pack/pack.py keys    rewrite only dist/ASWAN-KIT/Install.bat (after changing a key)

The projects are copied from the folders next to this repo, as they are right now.
The API keys are read from those folders too and written only into dist/.../Install.bat.
Needs `uv` (to download the Windows Python packages).
"""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

KIT_REPO = Path(__file__).resolve().parent.parent
WORKSPACE = KIT_REPO.parent
PACK_DIR = KIT_REPO / "pack"
CACHE = KIT_REPO / "cache"
DIST = KIT_REPO / "dist"
USB = DIST / "ASWAN-KIT"
PAYLOAD = USB / "payload"
KIT = PAYLOAD / "kit"

# Windows builds to put on the USB. Pinned so every USB gets the same thing.
PYTHON_VERSION = "3.12"
PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20261013/"
              "cpython-3.12.15%2B20261013-x86_64-pc-windows-msvc-install_only.tar.gz")
NODE_VERSION = "v22.23.3"
NODE_URL = "https://nodejs.org/dist/" + NODE_VERSION + "/node-" + NODE_VERSION + "-win-x64.zip"

# Left out of every project copy: history, local environments, caches and agent folders.
SKIP_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__", ".claude", ".agents", ".vscode", ".idea", "logs"}

DOC_KINDS = ["documentation", "poster", "presentation"]


def load_manifest():
    return json.loads((KIT_REPO / "projects.json").read_text(encoding="utf-8"))


def say(text):
    print(text, flush=True)


# ---------- docs ----------

def collect_docs():
    manifest = load_manifest()
    docs_root = KIT_REPO / "Docs"
    if docs_root.exists():
        shutil.rmtree(docs_root)
    missing = []
    for project in manifest["projects"]:
        target = docs_root / project["name"]
        target.mkdir(parents=True)
        for kind in DOC_KINDS:
            relative = project["docs"].get(kind)
            source = WORKSPACE / project["folder"] / relative if relative else None
            if source and source.exists():
                shutil.copy2(source, target / (kind.capitalize() + ".pdf"))
            else:
                missing.append(project["name"] + ": " + kind)
    say("Docs copied into " + str(docs_root))
    for line in missing:
        say("  missing  " + line)


# ---------- downloads ----------

def download(url, name):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists():
        say("Downloading " + name + " ...")
        urllib.request.urlretrieve(url, path)
    return path


def add_python():
    archive = download(PYTHON_URL, "python-windows.tar.gz")
    with tarfile.open(archive) as tar:
        tar.extractall(KIT, filter="data")
    if not (KIT / "python" / "python.exe").exists():
        sys.exit("Python archive did not contain python/python.exe")


def add_node():
    archive = download(NODE_URL, "node-windows.zip")
    with zipfile.ZipFile(archive) as zip_file:
        zip_file.extractall(KIT)
    (KIT / ("node-" + NODE_VERSION + "-win-x64")).rename(KIT / "node")


# ---------- python packages ----------

def requirement_lines(text):
    lines = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if line:
            lines.append(line)
    return sorted(lines)


def make_env(requirements, built):
    # Projects with the same requirements share one folder of packages.
    key = "\n".join(requirements)
    name = "env-" + hashlib.sha1(key.encode()).hexdigest()[:8]
    if name in built:
        return name
    target = KIT / "libs" / name
    requirements_file = CACHE / (name + ".txt")
    requirements_file.write_text(key + "\n", encoding="utf-8")
    say("Downloading Windows packages for: " + ", ".join(requirements))
    subprocess.run(
        ["uv", "pip", "install", "--quiet", "--target", str(target),
         "--python-platform", "x86_64-pc-windows-msvc", "--python-version", PYTHON_VERSION,
         "--only-binary", ":all:", "-r", str(requirements_file)],
        check=True,
        # Some packages (pyarrow) are big; a slow connection needs more than uv's 30 second default.
        env=dict(os.environ, UV_HTTP_TIMEOUT="600", UV_HTTP_RETRIES="10"),
    )
    built.add(name)
    return name


def app_requirements(project, app):
    if app.get("requirements"):
        return sorted(app["requirements"])
    path = WORKSPACE / project["folder"] / app.get("dir", ".") / "requirements.txt"
    if not path.exists():
        sys.exit(project["name"] + " / " + app["label"] + ": no requirements.txt and no requirements in projects.json")
    return requirement_lines(path.read_text(encoding="utf-8"))


# ---------- projects ----------

def skip_files(folder, names):
    skipped = []
    for name in names:
        if name in SKIP_NAMES or name.endswith(".pyc"):
            skipped.append(name)
    return skipped


def copy_project(project):
    source = WORKSPACE / project["folder"]
    target = KIT / "projects" / project["id"]
    say("Copying " + project["folder"] + " ...")
    shutil.copytree(source, target, ignore=skip_files)
    # The keys are written by Install.bat instead, so they never sit in a plain copy.
    for relative in project.get("secrets", {}):
        secret = target / relative
        if secret.exists():
            secret.unlink()
    # Other files to leave out, e.g. an example file that holds a real key.
    for relative in project.get("strip", []):
        extra = target / relative
        if extra.exists():
            extra.unlink()
    return target


def add_admin(project, target):
    admin = project.get("admin")
    if not admin:
        return
    db_path = target / admin["db"]
    if not db_path.exists():
        sys.exit(project["name"] + ": database not found at " + admin["db"])
    connection = sqlite3.connect(db_path)
    # executescript runs several statements, for projects that need more than one row.
    connection.executescript(admin["sql"])
    connection.commit()
    connection.close()


def check_admin(project, target, login):
    admin = project.get("admin")
    if not admin:
        return "no login needed (any text works)"
    connection = sqlite3.connect(target / admin["db"])
    table_info = connection.execute("PRAGMA table_info(users)").fetchall()
    columns = {}
    for row in table_info:
        columns[row[1].lower()] = row[1]
    query = ("SELECT COUNT(*) FROM users WHERE " + columns["email"] + " = ? AND " + columns["password"] + " = ?")
    count = connection.execute(query, (login["email"], login["password"])).fetchone()[0]
    connection.close()
    if count == 1:
        return "admin login OK"
    sys.exit(project["name"] + ": admin login check failed")


def install_node_modules(project, target):
    for app in project["apps"]:
        if app["kind"] == "node":
            backend = target / app["backend_dir"]
            say("npm install for " + project["name"] + " ...")
            subprocess.run(["npm", "ci", "--omit=dev", "--no-audit", "--no-fund"], cwd=backend, check=True)


# ---------- the two .bat files ----------

def batch_escape(text):
    text = text.replace("^", "^^").replace("%", "%%")
    for char in "&<>|":
        text = text.replace(char, "^" + char)
    return text


def read_key(text, name):
    # Finds NAME = "value" (secrets.toml) or NAME=value (.env).
    for line in text.splitlines():
        if "=" in line and line.split("=", 1)[0].strip() == name:
            return line.split("=", 1)[1].strip().strip('"')
    return None


def secret_file_lines(secret):
    # A secret is either a key file to copy as it is, or one key taken from another file
    # and written in a new form ({"source", "read", "write"}).
    if isinstance(secret, str):
        source = WORKSPACE / secret
    else:
        source = WORKSPACE / secret["source"]
    if not source.exists():
        sys.exit("Key file missing on this machine: " + str(source))
    text = source.read_text(encoding="utf-8")
    if isinstance(secret, str):
        return text.splitlines()
    value = read_key(text, secret["read"])
    if not value:
        sys.exit(secret["read"] + " not found in " + str(source))
    return [secret["write"].replace("{value}", value)]


def secret_lines(manifest):
    lines = []
    for project in manifest["projects"]:
        for relative, secret in project.get("secrets", {}).items():
            destination = '"%TARGET%\\kit\\projects\\' + project["id"] + "\\" + relative.replace("/", "\\") + '"'
            first = True
            for line in secret_file_lines(secret):
                if line.strip() == "" or line.strip().startswith("#"):
                    continue
                arrow = ">" if first else ">>"
                lines.append(arrow + destination + " echo " + batch_escape(line))
                first = False
            # Tell the instructor straight away if a key file could not be written.
            lines.append("if exist " + destination + " (echo  AI key for " + project["name"] + ": OK) else (echo  WARNING: the AI key for "
                         + project["name"] + " was not written. Call the lead instructor.)")
    return lines


def write_installer(manifest):
    install_text = (PACK_DIR / "Install.bat").read_text(encoding="utf-8")
    write_batch(USB / "Install.bat", install_text.replace("@@SECRETS@@", "\n".join(secret_lines(manifest))))


def write_batch(path, text):
    # cmd.exe wants Windows line endings.
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def build():
    manifest = load_manifest()
    if USB.exists():
        shutil.rmtree(USB)
    KIT.mkdir(parents=True)

    add_python()
    add_node()

    built = set()
    kit_manifest = json.loads(json.dumps(manifest))
    report = []
    for project in kit_manifest["projects"]:
        target = copy_project(project)
        add_admin(project, target)
        report.append(project["name"] + ": " + check_admin(project, target, manifest["login"]))
        install_node_modules(project, target)
        for app in project["apps"]:
            if app["kind"] in ("streamlit", "game"):
                app["env"] = make_env(app_requirements(project, app), built)

    launcher_env = make_env(requirement_lines((KIT_REPO / "requirements.txt").read_text(encoding="utf-8")), built)
    (KIT / "projects.json").write_text(json.dumps(kit_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copytree(KIT_REPO / "launcher", KIT / "launcher", ignore=skip_files)
    shutil.copytree(KIT_REPO / ".streamlit", KIT / ".streamlit")
    shutil.copytree(KIT_REPO / "Docs", PAYLOAD / "Docs")

    start_text = (PACK_DIR / "Open Project Manager.bat").read_text(encoding="utf-8")
    write_batch(PAYLOAD / "Open Project Manager.bat", start_text.replace("@@LAUNCHER_ENV@@", launcher_env))
    write_installer(manifest)

    say("")
    for line in report:
        say("  " + line)
    size = subprocess.run(["du", "-sh", str(USB)], capture_output=True, text=True).stdout.split()[0]
    say("Built " + str(USB) + " (" + size + "). Copy everything inside it onto each USB.")


def make_zip():
    if not USB.exists():
        sys.exit("Run `pack.py build` first.")
    say("Zipping ...")
    shutil.make_archive(str(DIST / "ASWAN-KIT"), "zip", DIST, "ASWAN-KIT")
    say("Built " + str(DIST / "ASWAN-KIT.zip"))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "docs":
        collect_docs()
    elif command == "build":
        build()
    elif command == "zip":
        make_zip()
    elif command == "keys":
        # Only rewrite Install.bat, e.g. after changing a key; much faster than a full build.
        if not USB.exists():
            sys.exit("Run `pack.py build` first.")
        write_installer(load_manifest())
        say("Rewrote " + str(USB / "Install.bat"))
    else:
        sys.exit(__doc__)
