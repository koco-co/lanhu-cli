"""lanhu-cli — standalone CLI for Lanhu design platform."""

from __future__ import annotations

import asyncio
import json
import sys

import click

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _echo_json(data):
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _run(coro):
    return asyncio.run(coro)


def _common_options(f):
    f = click.option("--user-name", default="cli-user", show_default=True,
                     help="Display name for collaborator tracking")(f)
    f = click.option("--user-role", default="开发", show_default=True,
                     help="Role label for AI prompt selection")(f)
    return f


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="lanhu-cli")
def main():
    """Lanhu CLI — interact with Lanhu design/prototype projects."""


# ---------------------------------------------------------------------------
# pages group
# ---------------------------------------------------------------------------

@main.group()
def pages():
    """Lanhu Axure prototype page commands."""


@pages.command("list")
@click.argument("url")
@_common_options
def pages_list(url, user_name, user_role):
    """List all pages in an Axure prototype document."""
    from lanhu_cli.api.pages import get_pages
    result = _run(get_pages(url, user_name=user_name, user_role=user_role))
    _echo_json(result)


@pages.command("analyze")
@click.argument("url")
@click.option("--page-names", default="all", show_default=True,
              help='Page name(s) to analyze. "all" or comma-separated names.')
@click.option("--mode", type=click.Choice(["full", "text_only"]), default="full", show_default=True)
@click.option("--analysis-mode", type=click.Choice(["developer", "tester", "explorer"]),
              default="developer", show_default=True)
@_common_options
def pages_analyze(url, page_names, mode, analysis_mode, user_name, user_role):
    """Analyze Axure prototype pages (screenshot + text extraction)."""
    from lanhu_cli.api.pages import analyze_pages

    names: list | str
    if page_names == "all":
        names = "all"
    elif "," in page_names:
        names = [n.strip() for n in page_names.split(",")]
    else:
        names = page_names

    result = _run(analyze_pages(url, page_names=names, mode=mode,
                                analysis_mode=analysis_mode,
                                user_name=user_name, user_role=user_role))
    _echo_json(result)


# ---------------------------------------------------------------------------
# designs group
# ---------------------------------------------------------------------------

@main.group()
def designs():
    """Lanhu UI design image commands."""


@designs.command("list")
@click.argument("url")
@_common_options
def designs_list(url, user_name, user_role):
    """List UI design images in a project."""
    from lanhu_cli.api.designs import get_designs
    result = _run(get_designs(url, user_name=user_name, user_role=user_role))
    _echo_json(result)


@designs.command("analyze")
@click.argument("url")
@click.option("--design-names", default="all", show_default=True,
              help='Design name(s) or index numbers. "all" or comma-separated.')
@_common_options
def designs_analyze(url, design_names, user_name, user_role):
    """Download designs and generate HTML+CSS code from schema."""
    from lanhu_cli.api.designs import analyze_designs

    names: list | str
    if design_names == "all":
        names = "all"
    elif "," in design_names:
        names = [n.strip() for n in design_names.split(",")]
    else:
        names = design_names

    result = _run(analyze_designs(url, design_names=names,
                                  user_name=user_name, user_role=user_role))
    _echo_json(result)


@designs.command("slices")
@click.argument("url")
@click.argument("design_name")
@click.option("--no-metadata", is_flag=True, default=False, help="Skip color/shadow metadata")
@_common_options
def designs_slices(url, design_name, no_metadata, user_name, user_role):
    """Get slice/asset info from a specific design."""
    from lanhu_cli.api.designs import get_design_slices
    result = _run(get_design_slices(url, design_name=design_name,
                                    include_metadata=not no_metadata,
                                    user_name=user_name, user_role=user_role))
    _echo_json(result)


# ---------------------------------------------------------------------------
# messages group
# ---------------------------------------------------------------------------

@main.group()
def messages():
    """Lanhu project message board commands."""


@messages.command("post")
@click.argument("url")
@click.argument("summary")
@click.argument("content")
@click.option("--type", "msg_type", default="normal",
              type=click.Choice(["normal", "task", "question", "urgent", "knowledge"]),
              show_default=True)
@click.option("--mentions", default="", help="Comma-separated list of person names to @")
@_common_options
def messages_post(url, summary, content, msg_type, mentions, user_name, user_role):
    """Post a message to the project board."""
    from lanhu_cli.api.messages import say

    mention_list = [m.strip() for m in mentions.split(",") if m.strip()] or None
    result = _run(say(url, summary=summary, content=content,
                      message_type=msg_type, mentions=mention_list,
                      user_name=user_name, user_role=user_role))
    _echo_json(result)


@messages.command("list")
@click.argument("url", default="all")
@click.option("--filter-type", default=None,
              type=click.Choice(["normal", "task", "question", "urgent", "knowledge"]))
@click.option("--search", default=None, help="Regex to filter by summary/content")
@click.option("--limit", default=None, type=int, help="Max number of messages to return")
@_common_options
def messages_list(url, filter_type, search, limit, user_name, user_role):
    """List messages (url or 'all' for all projects)."""
    from lanhu_cli.api.messages import say_list
    result = _run(say_list(url if url != "all" else None,
                           filter_type=filter_type, search_regex=search, limit=limit,
                           user_name=user_name, user_role=user_role))
    _echo_json(result)


@messages.command("detail")
@click.argument("message_ids")
@click.argument("url", default="")
@_common_options
def messages_detail(message_ids, url, user_name, user_role):
    """Get full content of messages by ID (comma-separated IDs)."""
    from lanhu_cli.api.messages import say_detail

    ids_parsed: int | list
    if "," in message_ids:
        ids_parsed = [int(i.strip()) for i in message_ids.split(",") if i.strip()]
    else:
        ids_parsed = int(message_ids)

    result = _run(say_detail(url or None, message_ids=ids_parsed,
                             user_name=user_name, user_role=user_role))
    _echo_json(result)


@messages.command("edit")
@click.argument("url")
@click.argument("message_id", type=int)
@click.option("--summary", default=None)
@click.option("--content", default=None)
@click.option("--mentions", default=None, help="Comma-separated names")
@_common_options
def messages_edit(url, message_id, summary, content, mentions, user_name, user_role):
    """Edit a published message."""
    from lanhu_cli.api.messages import say_edit

    mention_list = [m.strip() for m in mentions.split(",") if m.strip()] if mentions else None
    result = _run(say_edit(url, message_id=message_id, summary=summary,
                           content=content, mentions=mention_list,
                           user_name=user_name, user_role=user_role))
    _echo_json(result)


@messages.command("delete")
@click.argument("url")
@click.argument("message_id", type=int)
@_common_options
def messages_delete(url, message_id, user_name, user_role):
    """Delete a message."""
    from lanhu_cli.api.messages import say_delete
    result = _run(say_delete(url, message_id=message_id,
                             user_name=user_name, user_role=user_role))
    _echo_json(result)


# ---------------------------------------------------------------------------
# members group
# ---------------------------------------------------------------------------

@main.group()
def members():
    """Lanhu project collaborator commands."""


@members.command("list")
@click.argument("url")
@_common_options
def members_list(url, user_name, user_role):
    """List project collaborators."""
    from lanhu_cli.api.messages import get_members
    result = _run(get_members(url, user_name=user_name, user_role=user_role))
    _echo_json(result)


# ---------------------------------------------------------------------------
# resolve command
# ---------------------------------------------------------------------------

@main.command("resolve")
@click.argument("invite_url")
def resolve(invite_url):
    """Resolve a Lanhu invite/share link to its actual project URL."""
    from lanhu_cli.api.members import resolve_invite_link
    result = _run(resolve_invite_link(invite_url))
    _echo_json(result)


if __name__ == "__main__":
    main()
