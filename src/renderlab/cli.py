"""Renderlab CLI entrypoint."""

from __future__ import annotations

from pathlib import Path

import lionscliapp as app


VERSION = "0.1.0"

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
    app.declare_key("job.count", "1")
    app.declare_key("run.parallelism", "6")

    app.describe_key("path.root", "Root directory for renderlab data.")
    app.describe_key("job.count", "Default batch count used by job:create.")
    app.describe_key("run.parallelism", "Maximum concurrent runs for job:run.")

    app.set_flag("search_upwards_for_project_dir", True)

    app.declare_cmd(CMD_RECIPE_NEW, cmd_recipe_new)
    app.declare_cmd(CMD_RECIPE_LIST, cmd_recipe_list)
    app.declare_cmd(CMD_RECIPE_SHOW, cmd_recipe_show)
    app.declare_cmd(CMD_RECIPE_CLONE, cmd_recipe_clone)
    app.declare_cmd(CMD_JOB_CREATE, cmd_job_create)
    app.declare_cmd(CMD_JOB_RUN, cmd_job_run)
    app.declare_cmd(CMD_RUN_LIST, cmd_run_list)
    app.declare_cmd(CMD_RUN_SHOW, cmd_run_show)

    app.describe_cmd(CMD_RECIPE_NEW, "Create a new recipe.")
    app.describe_cmd(CMD_RECIPE_LIST, "List recipes.")
    app.describe_cmd(CMD_RECIPE_SHOW, "Show a recipe identified by --id.")
    app.describe_cmd(CMD_RECIPE_CLONE, "Clone a recipe identified by --id.")
    app.describe_cmd(CMD_JOB_CREATE, "Create a job from a recipe identified by --id.")
    app.describe_cmd(CMD_JOB_RUN, "Execute a job identified by --id.")
    app.describe_cmd(CMD_RUN_LIST, "List runs.")
    app.describe_cmd(CMD_RUN_SHOW, "Show a run identified by --id.")


def cmd_recipe_new() -> None:
    print("recipe:new not implemented yet")


def cmd_recipe_list() -> None:
    print("recipe:list not implemented yet")


def cmd_recipe_show() -> None:
    print("recipe:show not implemented yet")


def cmd_recipe_clone() -> None:
    print("recipe:clone not implemented yet")


def cmd_job_create() -> None:
    print("job:create not implemented yet")


def cmd_job_run() -> None:
    print("job:run not implemented yet")


def cmd_run_list() -> None:
    print("run:list not implemented yet")


def cmd_run_show() -> None:
    print("run:show not implemented yet")


def get_root_path() -> Path:
    """Return the configured renderlab root path."""
    return Path(app.ctx["path.root"])
