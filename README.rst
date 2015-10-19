xml_diff
========

Compares the text inside two XML documents and marks up the differences with ``<del>`` and ``<ins>`` tags.

This is the result of about 7 years of trying to get this right and coded simply. I've used code like this in one form or another to compare bill text on GovTrack.us <https://www.govtrack.us>.

The comparison is completely blind to the structure of the two XML documents. It does a word-by-word comparison on the text content only, and then it goes back into the original documents and wraps changed text in new ``<del>`` and ``<ins>`` wrapper elements.

The documents are then concatenated to form a new document and the new document is printed on standard output. Or use this as a library and call ``compare`` yourself with two ``lxml.etree.Element`` nodes (the roots of your documents).

The script is written in Python 3.

Example
-------

Comparing these two documents::

	<html>
		Here is <b>some bold</b> text.
	</html>

and::

	<html>
		Here is <i>some italic</i> content that shows how <tt>xml_diff</tt> works.
	</html>	

Yields::

	<documents>
		<html>
			Here is <b>some <del>bold</del></b><del> text</del>.
		</html>
		<html>
			Here is <i>some <ins>italic</ins></i><ins> content that shows how </ins><tt><ins>xml_diff</ins></tt><ins> works</ins>.
		</html>
	</documents>

On Ubuntu, get dependencies with::

	apt-get install python3-lxml libxml2-dev libxslt1-dev

For really fast comparisons, get Google's Diff Match Patch library <https://code.google.com/p/google-diff-match-patch/>, as re-written and sped-up by @leutloff <https://github.com/leutloff/diff-match-patch-cpp-stl> and then turned into a Python extension module by me <https://github.com/JoshData/diff_match_patch-python>::

	pip3 install diff_match_patch_python

Or if you can't install that for any reason, use the pure-Python library::

	pip3 install diff-match-patch

This is also at <https://code.google.com/p/google-diff-match-patch/source/browse/trunk/python3/diff_match_patch.py>. xml_diff will use whichever is installed.

Finally, install this module::

	pip3 install xml_diff

Then call the module from the command line::

	python3 -m xml_diff  --tags del,ins doc1.xml doc2.xml > changes.xml

Or use the module from Python::

	import lxml.etree
	from xml_diff import compare

	dom1 = lxml.etree.parse("doc1.xml").getroot()
	dom2 = lxml.etree.parse("doc2.xml").getroot()
	comparison = compare(dom1, dom2)

The two DOMs are modified in-place.

Optional Arguments
------------------

The ``compare`` function takes other optional keyword arguments:

``merge`` is a boolean (default false) that indicates whether the comparison function should perform a merge. If true, ``dom1`` will contain not just ``<del>`` nodes but also ``<ins>`` nodes and, similarly, ``dom2`` will contain not just ``<ins>`` nodes but also ``<del>`` nodes. Although the two DOMs will now contain the same semantic information about changes, and the same text content, each preserves their original structure --- since the comparison is only over text and not structure. The new ``ins``/``del`` nodes contain content from the other document (including whole subtrees), and so there's no guarantee that the final documents will conform to any particular structural schema after this operation.

``word_separator_regex`` (default ``r"\s+|[^\s\w]"``) is a regular expression for how to separate words. The default splits on one or more spaces in a row and single instances of non-word characters.

``differ`` is a function that takes two arguments ``(text1, text2)`` and returns an iterator over difference operations given as tuples of the form ``(operation, text_length)``, where ``operation`` is one of ``"="`` (no change in text), ``"+"`` (text inserted into ``text2``), or ``"-"`` (text deleted from ``text1``). (See xml_diff/__init__.py's ``default_differ`` function for how the default differ works.)

``tags`` is a two-tuple of tag names to use for deleted and inserted content. The default is ``('del', 'ins')``.

``make_tag_func`` is a function that takes one argument, which is either ``"ins"`` or ``"del"``, and returns a new ``lxml.etree.Element`` to be inserted into the DOM to wrap changed content. If given, the ``tags`` argument is ignored.

