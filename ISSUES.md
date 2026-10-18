# Issues

## #1 Kit repo + project list — feature
`projects.json` describes all 9 projects: team, description, links, how each app runs (kind, port), the admin login SQL, the key files and the 3 docs.

## #2 Pack script — feature
`pack/pack.py build` makes `dist/ASWAN-KIT`: Windows Python + Node, Windows packages per requirements set, the projects copied from this machine (with their DBs and the admin@admin.com / admin login), Docs, and the two .bat files with the keys written into Install.bat.

## #3 One-click install — feature
`Install.bat` copies the payload to `Desktop\Aswan Projects`, writes the keys, adds the "Open Project Manager" Desktop icon and opens the launcher. No admin rights, no internet.

## #4 Launcher website — feature
`launcher/app.py`: local mode runs/stops projects (several at once, Stop all, plain error + Try again + Show details) and opens the PDFs; hosted mode shows info and downloads the PDFs.

## #5 Excel sheet — docs
Update `../Aswan_Projects_Teams.xlsx` in place: team & description, links, docs available.

## #6 Missing docs — docs
Legion has no documentation/poster/presentation; Many Houses has no documentation PDF. Waiting on the user (projects are being updated).

## #7 Hosted site — feature
Push to `ibrhmahmd/aswan-kit` and deploy `launcher/app.py` on Streamlit Cloud.

## #8 Windows test run — bug hunt (user)
Full install + run of every project on a real Windows laptop before the trip.

## #9 Add Eyad Store — feature
Add Eyad Store (static shop in `store eyad aswan/STORE`, home page `html.htm`, port 8513): manifest entry, a `page` field so Open lands on the shop, Font Awesome bundled into the copy for offline icons, its 3 docs, and an Excel row.
