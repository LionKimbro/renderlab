"""Renderlab CLI entrypoint."""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

import lionscliapp as app


VERSION = "0.1.0"
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"

CMD_INIT = "init"
CMD_RECIPE_NEW = "recipe:new"
CMD_RECIPE_LIST = "recipe:list"
CMD_RECIPE_SHOW = "recipe:show"
CMD_RECIPE_CLONE = "recipe:clone"
CMD_JOB_CREATE = "job:create"
CMD_JOB_RUN = "job:run"
CMD_RUN_LIST = "run:list"
CMD_RUN_SHOW = "run:show"


def main() -> None:
    declare_app()
    app.main()


def declare_app() -> None:
    """Declare the full CLI surface before dispatch."""
    app.declare_app("renderlab", VERSION)
    app.describe_app("Create, run, and inspect renderlab recipes, jobs, and runs.")
    app.declare_projectdir(".renderlab")

    app.declare_key("path.root", ".")
    app.declare_key("id", "")
    app.declare_key("model", DEFAULT_MODEL)
    app.declare_key("name", "")
    app.declare_key("job.count", "1")
    app.declare_key("run.parallelism", "6")

    app.describe_key("path.root", "Root directory for renderlab data.")
    app.describe_key("id", "Identifier used by show and execution commands.")
    app.describe_key("model", "Default model for new recipes.")
    app.describe_key("name", "Name for a new recipe.")
    app.describe_key("job.count", "Default batch count used by job:create.")
    app.describe_key("run.parallelism", "Maximum concurrent runs for job:run.")

    app.set_flag("search_upwards_for_project_dir", True)

    app.declare_cmd(CMD_INIT, cmd_init)
    app.declare_cmd(CMD_RECIPE_NEW, cmd_recipe_new)
    app.declare_cmd(CMD_RECIPE_LIST, cmd_recipe_list)
    app.declare_cmd(CMD_RECIPE_SHOW, cmd_recipe_show)
    app.declare_cmd(CMD_RECIPE_CLONE, cmd_recipe_clone)
    app.declare_cmd(CMD_JOB_CREATE, cmd_job_create)
    app.declare_cmd(CMD_JOB_RUN, cmd_job_run)
    app.declare_cmd(CMD_RUN_LIST, cmd_run_list)
    app.declare_cmd(CMD_RUN_SHOW, cmd_run_show)

    app.describe_cmd(CMD_INIT, "Initialize the renderlab directory tree under path.root.")
    app.describe_cmd(CMD_RECIPE_NEW, "Create a new recipe.")
    app.describe_cmd(CMD_RECIPE_LIST, "List recipes.")
    app.describe_cmd(CMD_RECIPE_SHOW, "Show a recipe identified by --id.")
    app.describe_cmd(CMD_RECIPE_CLONE, "Clone a recipe identified by --id.")
    app.describe_cmd(CMD_JOB_CREATE, "Create a job from a recipe identified by --id.")
    app.describe_cmd(CMD_JOB_RUN, "Execute a job identified by --id.")
    app.describe_cmd(CMD_RUN_LIST, "List runs.")
    app.describe_cmd(CMD_RUN_SHOW, "Show a run identified by --id.")


def cmd_init() -> None:
    """Bootstrap the renderlab filesystem structure."""
    root = get_root_path()

    directories = [
        root / "assets",
        root / "recipes",
        root / "jobs",
        root / "runs",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    ensure_json_file(root / "assets" / "assets.json", {})
    ensure_json_file(root / "recipes" / "recipes.json", {})
    ensure_json_file(root / "jobs" / "index_jobs.json", {})
    ensure_state_file()

    print(f"Initialized renderlab at {root}")


def cmd_recipe_new() -> None:
    ensure_root_layout()

    state = load_state()
    recipe_number = state["next_recipe_number"]
    recipe_id = format_identifier("recipe", recipe_number)
    recipe_name = app.ctx["name"] or recipe_id

    recipe = {
        "recipe_id": recipe_id,
        "name": recipe_name,
        "model": app.ctx["model"],
        "tags": [],
        "created_at": timestamp_to_iso8601(time.time()),
        "prompt": None,
        "attachments": [],
        "settings": {},
    }

    recipe_dir = get_root_path() / "recipes" / recipe_id
    recipe_dir.mkdir(parents=True, exist_ok=False)
    (recipe_dir / "attachments").mkdir()
    write_json_file(recipe_dir / "recipe.json", recipe)

    state["next_recipe_number"] = recipe_number + 1
    save_state(state)

    print(recipe_id)


def cmd_recipe_list() -> None:
    ensure_root_layout()
    recipes_dir = get_root_path() / "recipes"
    recipe_dirs = sorted(
        path
        for path in recipes_dir.iterdir()
        if path.is_dir() and path.name.startswith("recipe-")
    )

    for recipe_dir in recipe_dirs:
        recipe = read_recipe(recipe_dir.name)
        name = recipe.get("name") or ""
        model = recipe.get("model") or ""
        print(f"{recipe['recipe_id']}\t{name}\t{model}")


def cmd_recipe_show() -> None:
    ensure_root_layout()
    recipe_id = app.ctx["id"]
    if not recipe_id:
        raise ValueError("recipe:show requires --id")

    recipe = read_recipe(recipe_id)
    print(json.dumps(recipe, indent=2))


def cmd_recipe_clone() -> None:
    ensure_root_layout()
    source_recipe_id = app.ctx["id"]
    if not source_recipe_id:
        raise ValueError("recipe:clone requires --id")

    source_recipe = read_recipe(source_recipe_id)
    state = load_state()
    recipe_number = state["next_recipe_number"]
    recipe_id = format_identifier("recipe", recipe_number)
    recipe_name = app.ctx["name"] or recipe_id

    recipe = dict(source_recipe)
    recipe["recipe_id"] = recipe_id
    recipe["name"] = recipe_name
    recipe["created_at"] = timestamp_to_iso8601(time.time())

    source_dir = get_recipe_dir(source_recipe_id)
    recipe_dir = get_recipe_dir(recipe_id)
    attachments_src = source_dir / "attachments"
    attachments_dst = recipe_dir / "attachments"

    recipe_dir.mkdir(parents=True, exist_ok=False)
    if attachments_src.exists():
        shutil.copytree(attachments_src, attachments_dst)
    else:
        attachments_dst.mkdir()
    write_json_file(recipe_dir / "recipe.json", recipe)

    state["next_recipe_number"] = recipe_number + 1
    save_state(state)

    print(recipe_id)


def cmd_job_create() -> None:
    ensure_root_layout()
    recipe_id = app.ctx["id"]
    if not recipe_id:
        raise ValueError("job:create requires --id")

    recipe = read_recipe(recipe_id)
    batch_count = parse_positive_int(app.ctx["job.count"], "job.count")

    state = load_state()
    job_number = state["next_job_number"]
    job_id = format_identifier("job", job_number)

    job = {
        "job_id": job_id,
        "created_at": timestamp_to_iso8601(time.time()),
        "recipe_id": recipe["recipe_id"],
        "batch": {
            "count": batch_count,
        },
    }

    job_dir = get_job_dir(job_id)
    snapshot_dir = job_dir / "snapshot"
    snapshot_attachments_dir = snapshot_dir / "attachments"
    recipe_dir = get_recipe_dir(recipe_id)
    recipe_attachments_dir = recipe_dir / "attachments"

    job_dir.mkdir(parents=True, exist_ok=False)
    snapshot_dir.mkdir()
    if recipe_attachments_dir.exists():
        shutil.copytree(recipe_attachments_dir, snapshot_attachments_dir)
    else:
        snapshot_attachments_dir.mkdir()

    write_json_file(job_dir / "job.json", job)
    write_json_file(snapshot_dir / "recipe.json", recipe)

    state["next_job_number"] = job_number + 1
    save_state(state)

    print(job_id)


def cmd_job_run() -> None:
    ensure_root_layout()
    job_id = app.ctx["id"]
    if not job_id:
        raise ValueError("job:run requires --id")

    job = read_job(job_id)
    parse_positive_int(app.ctx["run.parallelism"], "run.parallelism")
    batch_count = parse_positive_int(job["batch"]["count"], "job.batch.count")

    state = load_state()
    next_run_number = state["next_run_number"]
    created_run_ids = []

    for offset in range(batch_count):
        run_number = next_run_number + offset
        run_id = format_identifier("run", run_number)
        run = {
            "run_id": run_id,
            "job_id": job_id,
            "created_at": timestamp_to_iso8601(time.time()),
            "status": "pending",
            "outputs": [],
        }

        run_dir = get_run_dir(run_id)
        (run_dir / "outputs").mkdir(parents=True, exist_ok=False)
        write_json_file(run_dir / "run.json", run)
        created_run_ids.append(run_id)

    state["next_run_number"] = next_run_number + batch_count
    save_state(state)
    append_job_runs(job_id, created_run_ids)

    for run_id in created_run_ids:
        print(run_id)


def cmd_run_list() -> None:
    ensure_root_layout()
    runs_dir = get_root_path() / "runs"
    run_dirs = sorted(
        path
        for path in runs_dir.iterdir()
        if path.is_dir() and path.name.startswith("run-")
    )

    for run_dir in run_dirs:
        run = read_run(run_dir.name)
        status = run.get("status") or ""
        job_id = run.get("job_id") or ""
        print(f"{run['run_id']}\t{job_id}\t{status}")


def cmd_run_show() -> None:
    ensure_root_layout()
    run_id = app.ctx["id"]
    if not run_id:
        raise ValueError("run:show requires --id")

    run = read_run(run_id)
    print(json.dumps(run, indent=2))


def get_root_path() -> Path:
    """Return the configured renderlab root path."""
    return Path(app.ctx["path.root"])


def ensure_root_layout() -> None:
    """Ensure the renderlab root directories and seed files exist."""
    root = get_root_path()
    directories = [
        root / "assets",
        root / "recipes",
        root / "jobs",
        root / "runs",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    ensure_json_file(root / "assets" / "assets.json", {})
    ensure_json_file(root / "recipes" / "recipes.json", {})
    ensure_json_file(root / "jobs" / "index_jobs.json", {})
    ensure_state_file()


def ensure_json_file(path: Path, data: object) -> None:
    """Create a JSON file only when it does not already exist."""
    if path.exists():
        return

    write_json_file(path, data)


def write_json_file(path: Path, data: object) -> None:
    """Write JSON with stable formatting and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def read_json_file(path: Path) -> object:
    """Read JSON from a filesystem path."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_state_file() -> None:
    """Create the project-local state file when missing."""
    state_path = app.get_path("state.json", "p")
    if state_path.exists():
        return

    app.write_json("state.json", default_state(), "p2")


def load_state() -> dict:
    """Load allocation counters from the project-local state file."""
    ensure_state_file()
    state = app.read_json("state.json", "p")
    for key, value in default_state().items():
        state.setdefault(key, value)
    return state


def save_state(state: dict) -> None:
    """Persist allocation counters to the project-local state file."""
    app.write_json("state.json", state, "p2")


def default_state() -> dict:
    """Return the initial identifier allocation counters."""
    return {
        "next_recipe_number": 1,
        "next_job_number": 1,
        "next_run_number": 1,
    }


def format_identifier(prefix: str, number: int) -> str:
    """Format an integer identifier using four decimal digits."""
    return f"{prefix}-{number:04d}"


def parse_positive_int(value: object, field_name: str) -> int:
    """Parse a strictly positive integer value from CLI context."""
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return number


def timestamp_to_iso8601(value: float) -> str:
    """Convert a Unix timestamp to a local ISO 8601 string."""
    return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def get_recipe_path(recipe_id: str) -> Path:
    """Return the path to a recipe.json file for a recipe id."""
    return get_recipe_dir(recipe_id) / "recipe.json"


def get_recipe_dir(recipe_id: str) -> Path:
    """Return the path to a recipe directory."""
    return get_root_path() / "recipes" / recipe_id


def get_job_dir(job_id: str) -> Path:
    """Return the path to a job directory."""
    return get_root_path() / "jobs" / job_id


def get_run_dir(run_id: str) -> Path:
    """Return the path to a run directory."""
    return get_root_path() / "runs" / run_id


def read_recipe(recipe_id: str) -> dict:
    """Load a recipe by id from the filesystem."""
    recipe_path = get_recipe_path(recipe_id)
    if not recipe_path.exists():
        raise FileNotFoundError(f"Recipe not found: {recipe_id}")

    return read_json_file(recipe_path)


def read_job(job_id: str) -> dict:
    """Load a job by id from the filesystem."""
    job_path = get_job_dir(job_id) / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"Job not found: {job_id}")

    return read_json_file(job_path)


def read_run(run_id: str) -> dict:
    """Load a run by id from the filesystem."""
    run_path = get_run_dir(run_id) / "run.json"
    if not run_path.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")

    return read_json_file(run_path)


def append_job_runs(job_id: str, run_ids: list[str]) -> None:
    """Append created run ids to the job-local derived runs index."""
    runs_path = get_job_dir(job_id) / "runs.json"
    if runs_path.exists():
        existing = read_json_file(runs_path)
    else:
        existing = []

    existing.extend(run_ids)
    write_json_file(runs_path, existing)
