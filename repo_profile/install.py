"""Install only owned skill assets; preserve repository policy and settings."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config

SOURCE = Path(__file__).resolve().parent.parent
NAME = 'osengineer-repo-profile'
SKILL_REL = f'.claude/skills/{NAME}'
LINK_REL = f'.agents/skills/{NAME}'
PROFILE_REL = config.PROFILE_REL
MANIFEST_REL = '.osengineer/repo-profile-install.json'
DEFAULT_POLICY = config.DEFAULTS['policy']
DEFAULT_PLAN_DIR = config.DEFAULTS['planDirectory']
REGISTRY_REL = config.DEFAULTS['skillRegistry']
ROW = {'name': NAME, 'canonical': SKILL_REL, 'projections': {'codex': LINK_REL}}


def profile_config(policy=DEFAULT_POLICY, plan_dir=DEFAULT_PLAN_DIR):
    checked = config.validate({'policy': policy, 'planDirectory': plan_dir})
    return {'schemaVersion': 1, 'profile': 'repo', 'policy': checked['policy'],
            'skillRegistry': REGISTRY_REL, 'planDirectory': checked['planDirectory']}


def release_version(source):
    # The profile ships with osEngineer, so it carries the release version.
    path = Path(source) / 'VERSION'
    return path.read_text().strip() if path.is_file() else '0.0.0-dev'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(repo, relative):
    path = repo / relative
    # Reject redirected parents or assets, including policy-file symlinks.
    if not path.resolve().is_relative_to(repo):
        raise ValueError(f'Installation path escapes repository: {relative}')
    return path


def read_manifest(repo):
    path = safe_path(repo, MANIFEST_REL)
    return json.loads(path.read_text()) if path.exists() else None


def verify_owned(repo, manifest):
    for relative, expected in manifest.get('files', {}).items():
        path = safe_path(repo, relative)
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'Owned asset changed; preserve and resolve manually: {relative}')
    skill = safe_path(repo, SKILL_REL)
    actual = {str(p.relative_to(repo)) for p in skill.rglob('*')
              if p.is_file() and '__pycache__' not in p.relative_to(skill).parts
              and p.suffix != '.pyc'}
    expected = {p for p in manifest['files'] if p.startswith(SKILL_REL + '/')}
    if actual != expected:
        raise ValueError('Installed skill contains additional or missing files; refusing replacement')
    link = repo / LINK_REL
    if not link.is_symlink() or os.readlink(link) != manifest['linkTarget']:
        raise ValueError('Skill projection changed; refusing replacement')


def registry_payload(repo, remove=False, policy=DEFAULT_POLICY):
    path = safe_path(repo, REGISTRY_REL)
    original = path.read_bytes() if path.exists() else None
    payload = json.loads(original) if original is not None else {'policy': policy, 'skills': []}
    if not isinstance(payload, dict) or not isinstance(payload.get('skills'), list):
        raise ValueError('Invalid skill registry')
    rows = payload['skills']
    hits = [r for r in rows if isinstance(r, dict) and r.get('name') == NAME]
    if hits and hits != [ROW]:
        raise ValueError('Existing Repo profile skill registry entry differs; refusing overwrite')
    payload['skills'] = [r for r in rows if r != ROW] if remove else rows if hits else rows + [ROW]
    return path, original, (json.dumps(payload, indent=2) + '\n').encode()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.repo-profile-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def install(repo, source=SOURCE, policy=DEFAULT_POLICY, plan_dir=DEFAULT_PLAN_DIR):
    config = profile_config(policy, plan_dir)
    repo, source = Path(repo).resolve(), Path(source).resolve()
    if not (repo / '.git').exists() or not (repo / policy).is_file():
        raise ValueError('Repo profile installation requires a Git checkout and its policy file')
    skill, link, profile, manifest_path = [safe_path(repo, p) for p in
                                         (SKILL_REL, LINK_REL, PROFILE_REL, MANIFEST_REL)]
    previous = read_manifest(repo)
    if previous:
        verify_owned(repo, previous)
    elif any(p.exists() or p.is_symlink() for p in (skill, link, profile)):
        raise ValueError('Existing unowned Repo profile assets; refusing overwrite')
    reg_path, reg_original, reg_new = registry_payload(repo, policy=policy)
    saved_profile = profile.read_bytes() if profile.exists() else None
    saved_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    skill.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.repo-profile-stage-', dir=skill.parent))
    backup = None
    try:
        shutil.copytree(source / 'profiles/repo', stage, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for package in ('repo_runtime', 'repo_integrations', 'repo_profile'):
            if not (source / package).is_dir():
                raise ValueError(f'Missing implementation package: {package}')
            shutil.copytree(source / package, stage / 'scripts' / package,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        files = {f'{SKILL_REL}/{p.relative_to(stage)}': digest(p)
                 for p in stage.rglob('*') if p.is_file()}
        profile_bytes = (json.dumps(config, indent=2) + '\n').encode()
        files[PROFILE_REL] = hashlib.sha256(profile_bytes).hexdigest()
        try:
            revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                               text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            revision = 'unknown'
        target = os.path.relpath(skill, link.parent)
        manifest = {'schemaVersion': 1, 'profileVersion': release_version(source), 'sourceRevision': revision,
                    'files': files, 'linkTarget': target, 'registryCreated':
                    previous.get('registryCreated', False) if previous else reg_original is None}
        if skill.exists():
            backup = skill.with_name('.repo-profile-backup-' + stage.name)
            os.replace(skill, backup)
        os.replace(stage, skill)
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target, target_is_directory=True)
        atomic_write(profile, profile_bytes)
        atomic_write(reg_path, reg_new)
        atomic_write(manifest_path, (json.dumps(manifest, indent=2) + '\n').encode())
        if backup:
            shutil.rmtree(backup)
        return {'status': 'installed', 'skill': str(skill), 'profile': 'repo',
                'hooks': 'not-installed', 'sourceRevision': revision}
    except Exception:
        # Restore every previously published asset on a failed installation.
        if backup and backup.exists():
            if skill.exists():
                shutil.rmtree(skill)
            os.replace(backup, skill)
        elif not previous and skill.exists():
            shutil.rmtree(skill)
        if previous:
            if saved_profile is not None:
                atomic_write(profile, saved_profile)
            if saved_manifest is not None:
                atomic_write(manifest_path, saved_manifest)
            if link.is_symlink():
                link.unlink()
            link.symlink_to(previous["linkTarget"], target_is_directory=True)
        if not previous:
            if link.is_symlink():
                link.unlink()
            for p in (profile, manifest_path):
                if p.exists():
                    p.unlink()
        if reg_original is not None:
            atomic_write(reg_path, reg_original)
        elif reg_path.exists():
            reg_path.unlink()
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def uninstall(repo):
    repo = Path(repo).resolve()
    manifest = read_manifest(repo)
    if not manifest:
        return {'status': 'not-installed'}
    verify_owned(repo, manifest)
    try:
        policy = json.loads((repo / PROFILE_REL).read_text()).get('policy', DEFAULT_POLICY)
    except (OSError, ValueError):
        policy = DEFAULT_POLICY
    reg_path, _, reg_new = registry_payload(repo, remove=True, policy=policy)
    payload = json.loads(reg_new)
    if manifest.get('registryCreated') and payload == {'policy': policy, 'skills': []}:
        reg_path.unlink()
    else:
        atomic_write(reg_path, reg_new)
    (repo / LINK_REL).unlink()
    shutil.rmtree(repo / SKILL_REL)
    (repo / PROFILE_REL).unlink()
    (repo / MANIFEST_REL).unlink()
    return {'status': 'uninstalled', 'preserved': 'policy, foreign settings, agents, state and learning'}
