"""Renderlab CLI entrypoint."""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import lionscliapp as app


VERSION = "0.1.0"
kNANO_BANANA_2 = "gemini-3.1-flash-image-preview"
DEFAULT_MODEL = kNANO_BANANA_2
DEFAULT_ASPECT_RATIO = "2:3"
DEFAULT_IMAGE_SIZE = "2K"

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
    app.declare_key("aspect_ratio", DEFAULT_ASPECT_RATIO)
    app.declare_key("image_size", DEFAULT_IMAGE_SIZE)
    app.declare_key("name", "")
    app.declare_key("job.count", "1")
    app.declare_key("run.parallelism", "6")

    app.describe_key("path.root", "Root directory for renderlab data.")
    app.describe_key("id", "Identifier used by show and execution commands.")
    app.describe_key("model", "Default model for new recipes.")
    app.describe_key("aspect_ratio", "Default aspect ratio (note: model specific)")
    app.describe_key("image_size", "Default image size (note: model specific)")
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
    model = app.ctx["model"]

    recipe = {
        "recipe_id": recipe_id,
        "name": recipe_name,
        "model": model,
        "tags": [],
        "created_at": timestamp_to_iso8601(time.time()),
        "prompt": None,
        "attachments": [],
        "settings": build_default_settings_for_model(model),
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
    copy_referenced_shared_assets_to_snapshot(recipe, snapshot_attachments_dir)

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
    run_parallelism = parse_positive_int(app.ctx["run.parallelism"], "run.parallelism")
    batch_count = parse_positive_int(job["batch"]["count"], "job.batch.count")
    snapshot_recipe = read_job_snapshot_recipe(job_id)

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

    worker_count = min(run_parallelism, len(created_run_ids))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_run_id = {
            executor.submit(execute_run, job_id, run_id, snapshot_recipe): run_id
            for run_id in created_run_ids
        }
        for future in as_completed(future_to_run_id):
            future.result()

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


def build_default_settings_for_model(model: str) -> dict:
    """Build model-specific default settings for a new recipe."""
    settings = {}

    if model == kNANO_BANANA_2:
        if app.ctx["aspect_ratio"]:
            settings["aspect_ratio"] = app.ctx["aspect_ratio"]
        if app.ctx["image_size"]:
            settings["image_size"] = app.ctx["image_size"]

    return settings


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


def read_job_snapshot_recipe(job_id: str) -> dict:
    """Load the frozen snapshot recipe for a job."""
    recipe_path = get_job_dir(job_id) / "snapshot" / "recipe.json"
    if not recipe_path.exists():
        raise FileNotFoundError(f"Job snapshot recipe not found: {job_id}")

    return read_json_file(recipe_path)


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


def execute_run(job_id: str, run_id: str, recipe: dict) -> None:
    """Execute one run from a frozen job snapshot and persist the result."""
    run_dir = get_run_dir(run_id)
    run_path = run_dir / "run.json"
    run = read_run(run_id)

    started_at = timestamp_to_iso8601(time.time())
    run["started_at"] = started_at
    run["status"] = "running"
    write_json_file(run_path, run)

    try:
        outputs, log_text = generate_outputs_for_recipe(job_id, run_id, recipe)
        run["outputs"] = outputs
        run["status"] = "completed"
        if log_text:
            log_path = run_dir / "logs.txt"
            log_path.write_text(log_text, encoding="utf-8")
            run["logs"] = "logs.txt"
        run["error"] = None
    except Exception as exc:
        run["status"] = "failed"
        run["error"] = str(exc)

    run["ended_at"] = timestamp_to_iso8601(time.time())
    write_json_file(run_path, run)


def generate_outputs_for_recipe(job_id: str, run_id: str, recipe: dict) -> tuple[list[str], str]:
    """Call Gemini for a frozen recipe and write any returned image outputs."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    contents = [build_user_content(job_id, recipe, types)]
    config = build_generate_config(recipe, types)

    output_dir = get_run_dir(run_id) / "outputs"
    outputs = []
    text_chunks = []

    for chunk in client.models.generate_content_stream(
        model=recipe["model"],
        contents=contents,
        config=config,
    ):
        chunk_parts = getattr(chunk, "parts", None) or []
        if not chunk_parts and getattr(chunk, "text", None):
            text_chunks.append(chunk.text)
            continue

        for part in chunk_parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and inline_data.data:
                filename = write_output_file(output_dir, inline_data.mime_type, inline_data.data)
                outputs.append(filename)
            elif getattr(part, "text", None):
                text_chunks.append(part.text)

    return outputs, "".join(text_chunks)


def build_user_content(job_id: str, recipe: dict, types_module) -> object:
    """Build the user content payload for Gemini from a frozen recipe."""
    parts = []
    prompt = recipe.get("prompt")
    if prompt is not None:
        parts.append(build_prompt_part(prompt, types_module))

    for attachment in recipe.get("attachments", []):
        parts.append(build_attachment_part(job_id, attachment, types_module))

    if not parts:
        raise ValueError("Recipe has no prompt or attachments to submit")

    return types_module.Content(role="user", parts=parts)


def build_prompt_part(prompt: object, types_module) -> object:
    """Convert a prompt value into a Gemini content part."""
    if isinstance(prompt, str):
        return types_module.Part.from_text(text=prompt)

    payload = json.dumps(prompt, indent=2).encode("utf-8")
    return types_module.Part.from_bytes(data=payload, mime_type="application/json")


def build_attachment_part(job_id: str, attachment: dict, types_module) -> object:
    """Build a Gemini content part from an attachment entry."""
    if not isinstance(attachment, dict):
        raise ValueError("Attachment entries must be objects")

    asset_ref = attachment.get("asset")
    mime_type = attachment.get("mime_type")
    if not asset_ref or not mime_type:
        raise ValueError("Attachment entries require asset and mime_type")

    attachment_path = resolve_attachment_path(job_id, asset_ref)
    data = attachment_path.read_bytes()
    return types_module.Part.from_bytes(data=data, mime_type=mime_type)


def resolve_attachment_path(job_id: str, asset_ref: str) -> Path:
    """Resolve an attachment reference from a job snapshot only."""
    candidate = Path(asset_ref)
    if candidate.is_absolute():
        if not candidate.exists():
            raise FileNotFoundError(f"Attachment not found: {asset_ref}")
        return candidate

    snapshot_path = get_job_dir(job_id) / "snapshot" / "attachments" / candidate
    if snapshot_path.exists():
        return snapshot_path

    raise FileNotFoundError(f"Snapshot attachment not found: {asset_ref}")


def resolve_shared_asset_path(asset_ref: str) -> Path | None:
    """Resolve an attachment reference against the shared assets tree only."""
    candidate = Path(asset_ref)
    if candidate.is_absolute():
        return None

    shared_asset_path = get_root_path() / "assets" / candidate
    if shared_asset_path.exists():
        return shared_asset_path

    return None


def copy_referenced_shared_assets_to_snapshot(recipe: dict, snapshot_attachments_dir: Path) -> None:
    """Copy any shared asset attachments into the job snapshot."""
    for attachment in recipe.get("attachments", []):
        if not isinstance(attachment, dict):
            continue

        asset_ref = attachment.get("asset")
        if not asset_ref:
            continue

        shared_asset_path = resolve_shared_asset_path(asset_ref)
        if shared_asset_path is None:
            continue

        destination_path = snapshot_attachments_dir / Path(asset_ref)
        copy_snapshot_attachment(shared_asset_path, destination_path)


def copy_snapshot_attachment(source_path: Path, destination_path: Path) -> None:
    """Copy one attachment into a snapshot without silently changing existing content."""
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        if source_path.read_bytes() == destination_path.read_bytes():
            return
        raise ValueError(f"Snapshot attachment collision: {destination_path.name}")

    shutil.copy2(source_path, destination_path)


def build_generate_config(recipe: dict, types_module) -> object:
    """Build the GenerateContentConfig from recipe settings."""
    settings = recipe.get("settings") or {}
    image_kwargs = {}

    if "aspect_ratio" in settings:
        image_kwargs["aspectRatio"] = settings["aspect_ratio"]
    if "image_size" in settings:
        image_kwargs["imageSize"] = settings["image_size"]
    if "person_generation" in settings:
        image_kwargs["personGeneration"] = settings["person_generation"]
    if "output_mime_type" in settings:
        image_kwargs["outputMimeType"] = settings["output_mime_type"]
    if "output_compression_quality" in settings:
        image_kwargs["outputCompressionQuality"] = settings["output_compression_quality"]

    config_kwargs = {
        "responseModalities": ["IMAGE", "TEXT"],
    }
    if image_kwargs:
        config_kwargs["imageConfig"] = types_module.ImageConfig(**image_kwargs)

    return types_module.GenerateContentConfig(**config_kwargs)


def write_output_file(output_dir: Path, mime_type: str, data: bytes) -> str:
    """Write one generated output file and return its filename."""
    extension = extension_for_mime_type(mime_type)
    filename = f"{uuid.uuid4().hex}{extension}"
    (output_dir / filename).write_bytes(data)
    return filename


def extension_for_mime_type(mime_type: str) -> str:
    """Return a preferred filename extension for a MIME type."""
    overrides = {
        "image/jpeg": ".jpg",
    }
    if mime_type in overrides:
        return overrides[mime_type]

    return mimetypes.guess_extension(mime_type) or ".bin"
