# Aswan Projects launcher.
#
# Two modes from the same code:
# - On an instructor's laptop (a "projects" folder sits next to this one) it can
#   start and stop every project and open its docs.
# - On Streamlit Cloud (no "projects" folder) it only shows the info and the docs.

import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import streamlit as st

LAUNCHER_DIR = Path(__file__).resolve().parent
ROOT = LAUNCHER_DIR.parent
PROJECTS_DIR = ROOT / "projects"
LOGS_DIR = ROOT / "logs"
LOCAL = PROJECTS_DIR.is_dir()
ON_WINDOWS = os.name == "nt"

# A first start on Windows can be slow (the antivirus checks every file), so wait up to this long.
START_TIMEOUT_SECONDS = 90

DOC_KINDS = ["documentation", "poster", "presentation"]
DOC_LABELS = {"documentation": "Documentation", "poster": "Poster", "presentation": "Presentation"}
DOC_ICONS = {"documentation": ":material/description:", "poster": ":material/image:", "presentation": ":material/slideshow:"}

# Windows: run each project with its own hidden console, so closing the launcher window doesn't stop it.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


def load_manifest():
    return json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))


def find_docs_dir():
    # In the repo the docs sit next to the launcher; on a laptop they sit on the Desktop folder, one level up.
    if (ROOT / "Docs").is_dir():
        return ROOT / "Docs"
    return ROOT.parent / "Docs"


def doc_path(project, kind):
    return find_docs_dir() / project["name"] / (kind.capitalize() + ".pdf")


# ---------- running programs ----------

def python_exe():
    bundled = ROOT / "python" / "python.exe"
    if ON_WINDOWS and bundled.exists():
        return str(bundled)
    return sys.executable


def node_exe():
    bundled = ROOT / "node" / "node.exe"
    if ON_WINDOWS and bundled.exists():
        return str(bundled)
    return "node"


def python_env(app):
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    # The packages in libs/ are Windows builds; on another system (testing) use the current Python's own.
    if app.get("env") and ON_WINDOWS:
        env["PYTHONPATH"] = str(ROOT / "libs" / app["env"])
    return env


def app_ports(app):
    ports = []
    if app.get("port"):
        ports.append(app["port"])
    if app.get("backend_port"):
        ports.append(app["backend_port"])
    return ports


def app_url(app):
    if app.get("port"):
        return "http://localhost:" + str(app["port"])
    return ""


def app_commands(project, app):
    # Each command is (program and arguments, folder to run it in, environment).
    project_dir = PROJECTS_DIR / project["id"]
    folder = project_dir / app.get("dir", ".")
    kind = app["kind"]
    if kind == "streamlit":
        command = [
            python_exe(), "-m", "streamlit", "run", app["entry"],
            "--server.port", str(app["port"]),
            "--server.address", "localhost",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ]
        return [(command, folder, python_env(app))]
    if kind == "static":
        command = [python_exe(), "-m", "http.server", str(app["port"]), "--bind", "127.0.0.1"]
        return [(command, folder, python_env({}))]
    if kind == "node":
        backend = project_dir / app["backend_dir"]
        site = [python_exe(), "-m", "http.server", str(app["port"]), "--bind", "127.0.0.1"]
        return [
            ([node_exe(), app["backend_entry"]], backend, dict(os.environ)),
            (site, folder, python_env({})),
        ]
    if kind == "game":
        return [([python_exe(), app["entry"]], folder, python_env(app))]
    return []


def record_file(project, index):
    return LOGS_DIR / (project["id"] + "-" + str(index) + ".json")


def log_file(project, index):
    return LOGS_DIR / (project["id"] + "-" + str(index) + ".log")


def read_record(project, index):
    path = record_file(project, index)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def pid_alive(pid):
    if ON_WINDOWS:
        result = subprocess.run(
            ["tasklist", "/FI", "PID eq " + str(pid), "/NH"],
            capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def kill_tree(pid):
    if ON_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, creationflags=CREATE_NO_WINDOW,
        )
        return
    try:
        os.killpg(pid, 15)
    except OSError:
        pass


def pids_listening_on(port):
    # Finds a program left over from an earlier session that still holds the port.
    if not ON_WINDOWS:
        return []
    result = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    pids = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(":" + str(port)):
            pids.append(int(parts[4]))
    return pids


def start_app(project, index, app):
    LOGS_DIR.mkdir(exist_ok=True)
    log = open(log_file(project, index), "w", encoding="utf-8", errors="replace")
    pids = []
    for command, folder, env in app_commands(project, app):
        options = {"cwd": str(folder), "env": env, "stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
        if ON_WINDOWS:
            options["creationflags"] = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True
        process = subprocess.Popen(command, **options)
        pids.append(process.pid)
    log.close()
    record = {"pids": pids, "started": time.time()}
    record_file(project, index).write_text(json.dumps(record), encoding="utf-8")


def stop_app(project, index, app):
    record = read_record(project, index)
    if record:
        for pid in record["pids"]:
            kill_tree(pid)
        record_file(project, index).unlink()
    for port in app_ports(app):
        for pid in pids_listening_on(port):
            kill_tree(pid)
    # Wait a moment for the ports to close, so the card shows Stopped straight away.
    for attempt in range(20):
        still_open = False
        for port in app_ports(app):
            if port_open(port):
                still_open = True
        if not still_open:
            return
        time.sleep(0.25)


def app_status(project, index, app):
    # Gives back "running", "starting", "stopped" or "failed".
    record = read_record(project, index)
    ports = app_ports(app)
    if ports:
        all_open = True
        for port in ports:
            if not port_open(port):
                all_open = False
        if all_open:
            return "running"
    alive = False
    if record:
        for pid in record["pids"]:
            if pid_alive(pid):
                alive = True
    if app["kind"] == "game":
        if alive:
            return "running"
        if record and "Traceback" in read_log(project, index):
            return "failed"
        return "stopped"
    if alive:
        return "starting"
    if record:
        return "failed"
    return "stopped"


def read_log(project, index):
    path = log_file(project, index)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def plain_problem(log_text):
    text = log_text.lower()
    if "already in use" in text or "eaddrinuse" in text or "10048" in text:
        return "Another program is using this project's port. Click Stop all, then Try again."
    if "modulenotfounderror" in text or "cannot find module" in text:
        return "A part of this project is missing. Run Install again from the USB."
    if "api key" in text or "api_key" in text:
        return "The AI key is missing or not working. Call the lead instructor."
    return "This project could not start. Click Try again; if it fails again, call the lead instructor."


def wait_until_ready(project, index, app):
    deadline = time.time() + START_TIMEOUT_SECONDS
    while time.time() < deadline:
        status = app_status(project, index, app)
        if status != "starting":
            return status
        time.sleep(1)
    return app_status(project, index, app)


def run_app(project, index, app):
    if app_status(project, index, app) == "running":
        if app_url(app):
            webbrowser.open(app_url(app))
        return
    stop_app(project, index, app)
    start_app(project, index, app)
    if app["kind"] == "game":
        time.sleep(2)
        return
    with st.spinner("Starting " + app["label"] + "... the first time can take a minute."):
        status = wait_until_ready(project, index, app)
    if status == "running":
        webbrowser.open(app_url(app))


def open_file(path):
    if ON_WINDOWS:
        os.startfile(str(path))
    else:
        webbrowser.open(path.as_uri())


# ---------- the page ----------

# How each status looks: (text, Material icon, badge colour).
STATUS_BADGES = {
    "running": ("Running", ":material/check_circle:", "green"),
    "starting": ("Starting", ":material/progress_activity:", "orange"),
    "stopped": ("Stopped", ":material/pause_circle:", "gray"),
    "failed": ("Problem", ":material/error:", "red"),
}


def show_app_row(project, index, app):
    key = project["id"] + "-" + str(index)
    status = app_status(project, index, app)
    text, icon, color = STATUS_BADGES[status]
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("**" + app["label"] + "**", width="content")
        st.badge(text, icon=icon, color=color)

    with st.container(horizontal=True):
        if status == "running" or status == "starting":
            if app_url(app):
                st.link_button("Open", app_url(app), icon=":material/open_in_new:", type="primary")
            if st.button("Stop", key=key + "-stop", icon=":material/stop_circle:"):
                stop_app(project, index, app)
                st.rerun()
        elif status == "failed":
            if st.button("Try again", key=key + "-retry", icon=":material/refresh:", type="primary"):
                run_app(project, index, app)
                st.rerun()
        else:
            if st.button("Run", key=key + "-run", icon=":material/play_arrow:", type="primary"):
                run_app(project, index, app)
                st.rerun()

    if status == "failed":
        st.error(plain_problem(read_log(project, index)), icon=":material/error:")
        with st.expander("Show details", icon=":material/terminal:"):
            st.code(read_log(project, index)[-3000:] or "(no output)")


def file_reader(path):
    def read():
        return path.read_bytes()
    return read


def show_docs(project):
    with st.container(horizontal=True):
        for kind in DOC_KINDS:
            path = doc_path(project, kind)
            key = project["id"] + "-" + kind
            if not path.exists():
                st.button(DOC_LABELS[kind], key=key, icon=DOC_ICONS[kind], disabled=True, help="Not ready yet")
            elif LOCAL:
                if st.button(DOC_LABELS[kind], key=key, icon=DOC_ICONS[kind]):
                    open_file(path)
            else:
                # Read the PDF only when the button is clicked; sending all 26 on every page load would be slow.
                st.download_button(
                    DOC_LABELS[kind], file_reader(path), file_name=project["name"] + " - " + path.name,
                    mime="application/pdf", key=key, icon=DOC_ICONS[kind],
                )


def download_url(project):
    # GitHub makes a zip of the project's main branch at this address.
    return project["github"] + "/archive/HEAD.zip"


def show_links(project):
    with st.container(horizontal=True):
        if project.get("github"):
            st.link_button("Download project", download_url(project), icon=":material/download:")
            st.link_button("GitHub", project["github"], icon=":material/code:")
        if project.get("live"):
            st.link_button("Live website", project["live"], icon=":material/language:")


def show_card(project):
    with st.container(border=True):
        st.subheader(project["name"] + " — " + ", ".join(project["team"]))
        st.badge(project["category"], icon=":material/category:", color="blue")
        st.write(project["description"])
        if LOCAL:
            for index, app in enumerate(project["apps"]):
                show_app_row(project, index, app)
        st.caption("Docs")
        show_docs(project)
        st.caption("Code")
        show_links(project)


def stop_everything(manifest):
    for project in manifest["projects"]:
        for index, app in enumerate(project["apps"]):
            stop_app(project, index, app)


def matches(project, search):
    if search == "":
        return True
    text = (project["name"] + " " + " ".join(project["team"]) + " " + project["category"]).lower()
    return search.lower() in text


def show_page(manifest, search):
    projects = manifest["projects"]
    shown = []
    for project in projects:
        if matches(project, search):
            shown.append(project)
    if not shown:
        st.caption("No project matches that search.")
    for start in range(0, len(shown), 3):
        columns = st.columns(3)
        for offset in range(3):
            if start + offset < len(shown):
                with columns[offset]:
                    show_card(shown[start + offset])


st.set_page_config(page_title="Aswan Projects", page_icon=":material/travel_explore:", layout="wide")
manifest = load_manifest()
login = manifest["login"]

with st.container(horizontal=True, vertical_alignment="center"):
    st.title("Aswan Projects", icon=":material/travel_explore:", width="stretch")
    if LOCAL:
        if st.button("Stop all", icon=":material/stop_circle:"):
            stop_everything(manifest)
            st.rerun()

if LOCAL:
    st.caption("Press **Run** on a project, then **Open**. Keep the black window open while you work.")
else:
    st.caption("The student projects going to the Aswan competition, with their docs and code.")
st.info("Every project uses the same login: **" + login["email"] + "** / **" + login["password"] + "**", icon=":material/key:")

search = st.text_input("Search", placeholder="Search by project or student name", label_visibility="collapsed",
                       icon=":material/search:")

if LOCAL:
    # Refresh every few seconds so a project that finished starting shows as running.
    st.fragment(show_page, run_every=5)(manifest, search)
else:
    show_page(manifest, search)
