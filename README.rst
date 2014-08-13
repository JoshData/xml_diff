xml_diff
========

Compares the text inside two XML documents and marks up the differences with ``<del>`` and ``<ins>`` tags.

This is the result of about 7 years of trying to get this right and coded simply. I've used code like this in one form or another to compare bill text on GovTrack.us <https://www.govtrack.us>.

The comparison is completely blind to the structure of the two XML documents. It does a word-by-word comparison on the text content only, and then it goes back into the original documents and wraps changed text in new ``<del>`` and ``<ins>`` wrapper elements.

The documents are then concatenated to form a new document and the new document is printed on standard output. Or use this as a library and call ``compare`` yourself with two ``lxml.etree.Element`` nodes (the roots of your documents).

The script is written in Python 3. The module works with any Google Diff Match Patch-compatible differencing library. You provide it a differ function which takes two strings and returns a list of (op, length) tuples, where op is "+" (insertion), "-" (deletion), or "0" (no change). If will use my extension module <https://github.com/JoshData/diff_match_patch-python> if it is available, falling back on the pure-Python <https://code.google.com/p/google-diff-match-patch/source/browse/trunk/python3/diff_match_patch.py> if it is available, or else the not very useful Python built-in difflib.

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

On Ubuntu, apt-get installing ``python3-lxml`` or ``libxml2-dev`` and ``libxslt1-dev`` might be necessary. When installing from source, you'll need ``lxml`` too (but pip will get it for you automatically).

Then call the module from the command line::

	python -m xml_diff  --tags del,ins doc1.xml doc2.xml > changes.xml

For really fast comparisons, get Google's Diff Match Patch library <https://code.google.com/p/google-diff-match-patch/>, as re-written and sped-up by @leutloff <https://github.com/leutloff/diff-match-patch-cpp-stl> and then turned into a Python extension module by me <https://github.com/JoshData/diff_match_patch-python>::

	pip install diff_match_patch_python

The command-line tool (above) will use this library if it is available.

Use the module from Python like so::

	import lxml.etree
	from xml_diff import compare

	dom1 = lxml.etree.parse("doc1.xml").getroot()
	dom2 = lxml.etree.parse("doc2.xml").getroot()
	compare(dom1, dom2)

The two DOMs are modified in-place.

If you can't install diff_match_patch_python, you can also get the pure-Python version of diff_match_patch.py from <https://code.google.com/p/google-diff-match-patch/source/browse/trunk/python3/diff_match_patch.py>. (The command-line tool will fall back to this library if it is available.)

Or you can pass in your own comparison library as the third argument. (See xml_diff/__init__.py's default_differ function for how it would work.)
