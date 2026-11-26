# Security

## Reporting a problem

If you find a security problem in osint-visuals, please report it privately: open the repository's **Security** tab
and choose **Report a vulnerability**. Only the maintainers can see the report. Please don't open a public issue for
it until a fix is out.

A useful report says which skill and script are affected, what input triggers the problem, and what happens. A small
example file is ideal. We'll reply, fix it, and credit you if you'd like.

## What counts

These tools read files from other people: position exports, spreadsheets, story scripts. Anything that lets such a
file run code or change a generated page, read or send out local files, or make a page load something it shouldn't
is in scope. So is a way around the fingerprint checks on the libraries the pages load.

Out of scope: problems in the third-party services the skills use (OpenFreeMap, Overpass, Nominatim, NASA GIBS,
unpkg, and GitHub, where locator-map downloads Natural Earth). Please report those to the services themselves.

## Supported versions

Only the latest version on the `main` branch gets fixes.
