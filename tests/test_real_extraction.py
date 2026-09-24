"""Corpus-adapter checks: keep prose and literal names, omit executable samples."""

from evaluation.acquire_real import extract_rst


def test_nested_code_excluded_but_admonition_and_following_prose_survive():
    source = """Heading
========

.. note:: Keep this warning.

    These steps have consequences.

    .. code-block:: python

        secret = execute()

    Return to this prose.

Normal prose::

    >>> execute()
    result

Last paragraph.
"""
    prose, audit = extract_rst(source)
    assert "secret" not in prose and "execute()" not in prose
    assert "Keep this warning." in prose
    assert "These steps have consequences." in prose
    assert "Return to this prose." in prose and "Last paragraph." in prose
    assert audit["passages"][0] == "# Heading"


def test_wildcard_bullets_links_and_shortened_api_names():
    prose, audit = extract_rst("""* Find ``test_*.py`` or ``*_test.py`` files.

Use :class:`~package.Markup`, :ref:`a label <target>`, and `site <https://example.org>`_.

.. _target: https://example.org
""")
    assert audit["passages"][0] == "* Find test_*.py or *_test.py files."
    assert "Use Markup, a label, and site." in prose
    assert "https://" not in prose


def test_prose_after_literal_block_and_separate_colon():
    prose, _ = extract_rst("Text. ::\n\n    code()\n\nRemaining.\n")
    assert prose == "Text.\n\nRemaining.\n"
