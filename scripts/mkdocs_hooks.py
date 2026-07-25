"""
Hooks for the mkdocs documentation site.

This module is registered through the hooks option in mkdocs.yml.
"""

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.nav import Navigation


def on_nav(nav: Navigation, config: MkDocsConfig, files: Files) -> Navigation:
    """Show the forks at the top level of the sidebar.

    The specs are copied to docs/specs so that the relative links between the
    markdown files keep working, which leaves the whole sidebar nested inside a
    single specs entry. That entry carries no information, so it is unwrapped
    here and its forks are lifted to the top level.
    """
    if len(nav.items) == 1 and nav.items[0].is_section:
        nav.items[:] = nav.items[0].children
        for item in nav.items:
            item.parent = None

    return nav
