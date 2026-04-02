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
    """lanhu-cli — 蓝湖设计平台命令行工具

    \b
    无需 MCP 协议，直接通过 CLI 访问蓝湖的原型、设计图、消息等数据。
    Cookie 从项目根目录的 .env 文件中读取（LANHU_COOKIE=...）。

    \b
    快速上手：
      lanhu pages list <URL>               # 列出原型文档页面
      lanhu pages analyze <URL>            # 截图 + 文本提取
      lanhu designs list <URL>             # 列出 UI 设计图
      lanhu designs analyze <URL>          # 下载设计图并生成 HTML/CSS
      lanhu messages list all              # 查看所有项目留言
      lanhu members list <URL>             # 查看协作者列表
    """


# ---------------------------------------------------------------------------
# pages group
# ---------------------------------------------------------------------------

@main.group()
def pages():
    """原型文档（Axure）相关命令。

    \b
    子命令：
      list     列出文档中所有页面
      analyze  截图 + 提取文本内容（支持开发/测试/探索三种视角）
    """


@pages.command("list")
@click.argument("url")
@_common_options
def pages_list(url, user_name, user_role):
    """列出 Axure 原型文档的所有页面。

    \b
    URL 格式（含 docId 参数）：
      https://lanhuapp.com/web/#/item/project/product?tid=...&pid=...&docId=...

    \b
    示例：
      lanhu pages list "https://lanhuapp.com/web/#/item/project/product?tid=xxx&pid=xxx&docId=xxx"
    """
    from lanhu_cli.api.pages import get_pages
    result = _run(get_pages(url, user_name=user_name, user_role=user_role))
    _echo_json(result)


@pages.command("analyze")
@click.argument("url")
@click.option("--page-names", default="all", show_default=True,
              help='要分析的页面名称，"all" 或逗号分隔的多个页面名。')
@click.option("--mode", type=click.Choice(["full", "text_only"]), default="full", show_default=True,
              help='full=截图+文本；text_only=仅文本（快速全局扫描）。')
@click.option("--analysis-mode", type=click.Choice(["developer", "tester", "explorer"]),
              default="developer", show_default=True,
              help='分析视角：developer=开发详情，tester=测试用例，explorer=快速评审。')
@_common_options
def pages_analyze(url, page_names, mode, analysis_mode, user_name, user_role):
    """分析 Axure 原型页面（截图 + 文本提取）。

    \b
    推荐工作流（四阶段）：
      STAGE 1  text_only 模式扫描全局，了解结构
      STAGE 2  full 模式逐组深入分析
      STAGE 3  反向校验
      STAGE 4  生成交付物（需求文档/测试用例/评审稿）

    \b
    示例：
      lanhu pages analyze <URL> --mode text_only
      lanhu pages analyze <URL> --page-names "登录页,首页" --analysis-mode tester
    """
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
    """UI 设计图相关命令。

    \b
    子命令：
      list     列出项目中所有设计图
      analyze  下载设计图并生成 HTML+CSS 代码
      slices   获取指定设计图的切图/图标资源列表
    """


@designs.command("list")
@click.argument("url")
@_common_options
def designs_list(url, user_name, user_role):
    """列出项目中的 UI 设计图清单。

    \b
    URL 格式（不含 docId，仅含 tid 和 pid）：
      https://lanhuapp.com/web/#/item/project/stage?tid=...&pid=...

    \b
    示例：
      lanhu designs list "https://lanhuapp.com/web/#/item/project/stage?tid=xxx&pid=xxx"
    """
    from lanhu_cli.api.designs import get_designs
    result = _run(get_designs(url, user_name=user_name, user_role=user_role))
    _echo_json(result)


@designs.command("analyze")
@click.argument("url")
@click.option("--design-names", default="all", show_default=True,
              help='设计图名称或序号（来自 list 的 index）。"all" 或逗号分隔。')
@_common_options
def designs_analyze(url, design_names, user_name, user_role):
    """下载设计图并从 Schema 生成 HTML+CSS 代码。

    \b
    返回内容：
      image_path       本地图片路径
      html_code        从设计数据生成的 HTML+CSS
      design_tokens    高风险元素设计参数（渐变/阴影/边框）
      image_url_mapping  本地路径 ← 远程 CDN URL 映射表

    \b
    示例：
      lanhu designs analyze <URL> --design-names "首页"
      lanhu designs analyze <URL> --design-names "1,3,5"
    """
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
@click.option("--no-metadata", is_flag=True, default=False, help="跳过颜色/阴影元数据")
@_common_options
def designs_slices(url, design_name, no_metadata, user_name, user_role):
    """获取指定设计图的切图/图标资源列表及下载链接。

    \b
    示例：
      lanhu designs slices <URL> "首页设计"
    """
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
    """项目留言板相关命令。

    \b
    子命令：
      post    发布留言（支持 @成员、留言类型）
      list    查看留言列表（可按类型/关键词筛选）
      detail  查看留言详情
      edit    编辑已发布的留言
      delete  删除留言
    """


@messages.command("post")
@click.argument("url")
@click.argument("summary")
@click.argument("content")
@click.option("--type", "msg_type", default="normal",
              type=click.Choice(["normal", "task", "question", "urgent", "knowledge"]),
              show_default=True, help="留言类型：normal普通/task任务/question问题/urgent紧急/knowledge知识库")
@click.option("--mentions", default="", help="逗号分隔的 @成员姓名列表，例如：张三,李四")
@_common_options
def messages_post(url, summary, content, msg_type, mentions, user_name, user_role):
    """发布一条留言到项目留言板。

    \b
    示例：
      lanhu messages post <URL> "接口确认" "登录接口需要确认字段格式" --type question --mentions 张三
    """
    from lanhu_cli.api.messages import say

    mention_list = [m.strip() for m in mentions.split(",") if m.strip()] or None
    result = _run(say(url, summary=summary, content=content,
                      message_type=msg_type, mentions=mention_list,
                      user_name=user_name, user_role=user_role))
    _echo_json(result)


@messages.command("list")
@click.argument("url", default="all")
@click.option("--filter-type", default=None,
              type=click.Choice(["normal", "task", "question", "urgent", "knowledge"]),
              help="按留言类型过滤")
@click.option("--search", default=None, help="正则表达式，在标题/内容中匹配")
@click.option("--limit", default=None, type=int, help="最多返回的留言数量")
@_common_options
def messages_list(url, filter_type, search, limit, user_name, user_role):
    """查看留言列表。URL 传入具体项目 URL 或 "all"（所有项目）。

    \b
    示例：
      lanhu messages list all
      lanhu messages list all --filter-type knowledge
      lanhu messages list <URL> --search "登录" --limit 10
    """
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
    """查看留言详细内容（支持批量，逗号分隔 ID）。

    \b
    示例：
      lanhu messages detail 42 <URL>
      lanhu messages detail 1,2,3 <URL>
    """
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
@click.option("--summary", default=None, help="新标题")
@click.option("--content", default=None, help="新正文内容")
@click.option("--mentions", default=None, help="逗号分隔的 @成员姓名列表")
@_common_options
def messages_edit(url, message_id, summary, content, mentions, user_name, user_role):
    """编辑已发布的留言。

    \b
    示例：
      lanhu messages edit <URL> 42 --summary "新标题" --content "更新内容"
    """
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
    """删除一条留言。

    \b
    示例：
      lanhu messages delete <URL> 42
    """
    from lanhu_cli.api.messages import say_delete
    result = _run(say_delete(url, message_id=message_id,
                             user_name=user_name, user_role=user_role))
    _echo_json(result)


# ---------------------------------------------------------------------------
# members group
# ---------------------------------------------------------------------------

@main.group()
def members():
    """协作者相关命令。

    \b
    子命令：
      list   列出曾访问该项目的协作者及首次/最后访问时间
    """


@members.command("list")
@click.argument("url")
@_common_options
def members_list(url, user_name, user_role):
    """列出项目协作者（本地记录的访问历史）。

    \b
    示例：
      lanhu members list <URL>
    """
    from lanhu_cli.api.messages import get_members
    result = _run(get_members(url, user_name=user_name, user_role=user_role))
    _echo_json(result)


# ---------------------------------------------------------------------------
# resolve command
# ---------------------------------------------------------------------------

@main.command("resolve")
@click.argument("invite_url")
def resolve(invite_url):
    """解析蓝湖邀请/分享链接，返回实际项目 URL 及 tid/pid/docId 参数。

    \b
    示例：
      lanhu resolve "https://lanhuapp.com/link/#/invite?sid=xxx"
    """
    from lanhu_cli.api.members import resolve_invite_link
    result = _run(resolve_invite_link(invite_url))
    _echo_json(result)


if __name__ == "__main__":
    main()
