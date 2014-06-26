xml_diff
========

Compares the text inside two XML documents and marks up the differences with ``<del>`` and ``<ins>`` tags.

This is the result of about 7 years of trying to get this right and coded simply. I've used code like this in one form or another to compare bill text on GovTrack.us <https://www.govtrack.us>.

The comparison is completely blind to the structure of the two XML documents. It does a word-by-word comparison on the text content only, and then it goes back into the original documents and wraps changed text in new ``<del>`` and ``<ins>`` wrapper elements.

The documents are then concatenated to form a new document and the new document is printed on standard output. Or use this as a library and call ``compare`` yourself with two ``lxml.etree.Element`` nodes (the roots of your documents).

The script is written in Python 3 and uses Google's Diff Match Patch library <https://code.google.com/p/google-diff-match-patch/>, as re-written and sped-up by @leutloff <https://github.com/leutloff/diff-match-patch-cpp-stl> and then turned into a Python extension module by me <https://github.com/JoshData/diff_match_patch-python>. (A great pull request would be to replace that dependency with Python's built-in difflib <https://docs.python.org/3/library/difflib.html> module. It'll be slower but then won't have any unusual dependencies.)

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

First install the module::

	pip install xml_diff

On Ubuntu, apt-get installing ``python3-lxml`` or ``libxml2-dev`` and ``libxslt1-dev`` might be necessary. When installing from source, you'll need the dependencies ``lxml`` and ``diff_patch_patch_python``.

To do this you can call the module from the command line::

	python -m xml_diff  --tags del,ins doc1.xml doc2.xml > changes.xml

Or use the module from Python::

	import lxml.etree
	from xml_diff import compare

	dom1 = lxml.etree.parse("doc1.xml").getroot()
	dom2 = lxml.etree.parse("doc2.xml").getroot()
	compare(dom1, dom2)

The two DOMs are modified in-place.