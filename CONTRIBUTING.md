# Contributing

Thank you for wanting to help. Fixes, new skills and better examples are all welcome. For a new skill or a big change,
please open an issue first so we can agree on the idea before you build it.

## What every skill does

Each skill makes one evidence graphic that carries its own sources. A new skill should keep these habits:

- **The source is on the graphic.** Every page and every export credits the data it uses. Where the user supplies
  the evidence, the graphic names its source, or says plainly that no source was given.
- **It says what it found, not more.** A gap is "no reports for 31 hours", not "switched off its transponder". Where a
  finding is an inference, the skill says so.
- **It never tracks or models a private person.** See "What these skills will not do" in the README.

## How a skill is laid out

```
skills/<name>/
  SKILL.md        instructions for the agent
  scripts/        one Python script that builds the page
  assets/         the HTML template it fills in
```

- **Name:** short and lowercase, like `track-map` or `network-graph`. The `name:` in `SKILL.md` must match the folder.
- **`SKILL.md`:** a `description` that says when to use the skill, then the sections most skills use, such as *Before
  you start*, *Run*, *How to report*, *Limits* and *Will not do*.
- **Script:** Python 3.9 or newer, standard library only, no API keys. It runs on its own, without an agent, so a
  skill folder can be copied by itself.
- **Output:** a single HTML file.

## Safety rules for code

- **Data in the page:** insert data into the template with a `page_json()` helper like the other scripts', never
  plain `json.dumps` (network-graph does the same escaping in its own `render()`), so text in someone's file cannot
  close the data block and run as code. In the page's JavaScript, put text on screen with `textContent`, not
  `innerHTML`.
- **Links:** allow only `http` and `https` links that come from data.
- **Outside libraries:** pin an exact version and add an `integrity` fingerprint (with `crossorigin="anonymous"`), as
  the existing templates do. If you bundle a library instead, include its licence and say where it came from.
- **Online services:** keep to each service's usage rules. Send an identifying User-Agent like the other scripts',
  cache results, keep request rates low, and add the service and its licence to the README's data table.

## Examples and tests

- **Example data:** must be invented, or real public data credited by name. Say which in the README. No real private
  individuals.
- **Tests:** go in `tests/` and must run offline with `python3 -m unittest discover -s tests`. They run automatically
  on every pull request, on Python 3.9 and 3.13.
- **Gallery:** add a screenshot to `docs/gallery/` and a short entry to the README in the same plain style.

## Pull requests

Keep each pull request to one change, say how you tested it, and include before/after screenshots for anything
visual. By contributing, you agree that your work is published under the repository's MIT licence.

Security problems: please report them privately instead (see [SECURITY.md](SECURITY.md)).
