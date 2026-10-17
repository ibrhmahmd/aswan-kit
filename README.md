# Aswan Kit

Puts the 13 competition projects on the instructors' Windows laptops with one double-click, without internet.

## For instructors

1. Plug in the USB and double-click **Install**. Wait until the window says *Done*.
2. From then on, double-click **Open Project Manager** on the Desktop.
3. On a project, press **Run**, then **Open**. Every project uses the login **admin@admin.com / admin**.
4. Keep the black window open while you work. You can minimize it. Press **Stop all** when you are done.

The docs (documentation, poster, presentation) are in `Desktop\Aswan Projects\Docs`, and also on each project card.

## For the lead instructor (building the USB)

Run these on the Linux machine that has the projects next to this repo. It needs internet and `uv`.

```bash
python3 pack/pack.py docs    # copy each project's 3 PDFs into Docs/ (commit them for the hosted site)
python3 pack/pack.py build   # build dist/ASWAN-KIT
python3 pack/pack.py zip     # make dist/ASWAN-KIT.zip, the Drive backup
```

Copy **everything inside** `dist/ASWAN-KIT` (the `Install.bat` file and the `payload` folder) onto each USB.

- The projects are copied from this machine **as they are when you run `build`**, with their databases. Run `build` again after any change.
- The build adds `admin@admin.com / admin` to each project's database in the copy only. The students' folders are not changed.
- The Gemini keys are read from `egy_law/.streamlit/secrets.toml` and `MedMind/backend/.env` and written **only** into the built `Install.bat`. `dist/` is git-ignored. Never commit it, and don't share the zip publicly.

## Hosted info site

Deploy `launcher/app.py` from this repo on Streamlit Cloud. With no `projects` folder next to it, it only shows the info and lets people download the PDFs.

## Ports

Launcher 8500 · Byte Me 8501 · Ma'at 8502 · EmlakHub 8503 · Many Houses 8504 · NEO Challenge 8505 · MedMind 8506 (+ API 3000) · Legion 8507 · Vivestand 8508 · Pixel Verse website 8509 · foodZILLA 8510 · Kido Care 8511 · MedSync 8512. The three games (Crab Quest, Space X, Turbo) open their own window.

## Limits

- **Windows 64-bit only.** The bundled Python, Node and packages are Windows builds.
- **The keys are inside `Install.bat` on every USB and in the zip.** A lost USB leaks them. Revoke the keys after the trip.
- **Re-installing replaces the projects' data** with the USB version.
- If something else on the laptop already uses one of the ports, that project can't start.
