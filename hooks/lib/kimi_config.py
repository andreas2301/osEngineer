"""Text-level surgery on Kimi's config.toml for osEngineer hook entries.

Kimi re-serializes config.toml itself, so entries are identified structurally
("osEngineer-" in the command), never by marker comments. TOML is read with
tomllib; new [[hooks]] blocks are hand-emitted and gated by a tomllib parse
before os.replace() swaps the file in.
"""
import os
import tomllib

MARKER = "osEngineer-"
EMIT_KEYS = ("event", "matcher", "command", "timeout")


def _escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _render(entry):
    lines = ["[[hooks]]"]
    for key in EMIT_KEYS:
        value = entry.get(key)
        if value is None:
            continue
        if key == "timeout":
            lines.append(f"{key} = {int(value)}")
        else:
            lines.append(f'{key} = "{_escape(str(value))}"')
    return "\n".join(lines) + "\n"


def _valid(block_text):
    try:
        tomllib.loads(block_text)
        return True
    except tomllib.TOMLDecodeError:
        return False


def _rewrite(config_path, entries):
    path = str(config_path)
    existed = os.path.exists(path)
    text = ""
    if existed:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        tomllib.loads(text)  # refuse to touch a malformed config

    lines = text.splitlines(keepends=True)
    kept = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "[[hooks]]":
            kept.append(lines[i])
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not lines[j].startswith("["):
            j += 1
        block_text = "".join(lines[i:j])
        command = ""
        if _valid(block_text):
            command = str(tomllib.loads(block_text)["hooks"][0].get("command", ""))
        if MARKER not in command:  # foreign or unparsable: leave it alone
            kept.append(block_text)
        i = j

    out = "".join(kept)
    for entry in entries or []:
        block_text = _render(entry)
        if _valid(block_text):
            if out and not out.endswith("\n"):
                out += "\n"
            out += block_text
    tomllib.loads(out)  # never leave a malformed config behind

    if existed:
        with open(path + ".ose-bak", "w", encoding="utf-8") as f:
            f.write(text)
    tmp = path + ".ose-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    os.replace(tmp, path)


def apply_hooks(config_path, entries):
    parent = os.path.dirname(str(config_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    _rewrite(config_path, entries)


def remove_hooks(config_path):
    if not os.path.exists(str(config_path)):
        return
    _rewrite(config_path, None)
