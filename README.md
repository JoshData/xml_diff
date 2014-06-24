xml_diff
========

Compares the text inside two XML documents and marks up the differences with `<del>` and `<ins>` tags.

This is the result of about 7 years of trying to get this right and coded simply. I've used code like this in one form or another to compare bill text on [GovTrack.us](https://www.govtrack).

The comparison is completely blind to the structure of the two XML documents. It does a word-by-word comparison on the text content only, and then it goes back into the original documents and wraps changed text in new `<del>` and `<ins>` wrapper elements.

The documents are then concatenated to form a new document and the new document is printed on standard output. Or use this as a library and call `compare` yourself with two `lxml.etree.Element` nodes (the roots of your documents).

The script is written in Python 3 and uses Google's [Diff Match Patch](https://code.google.com/p/google-diff-match-patch/) library, as [re-written and sped-up by @leutloff](https://github.com/leutloff/diff-match-patch-cpp-stl) and then turned into a [Python extension module](https://github.com/JoshData/diff_match_patch-python) by me. (A great pull request would be to replace that dependency with Python's built-in [difflib](https://docs.python.org/3/library/difflib.html) module. It'll be slower but then won't have any unusual dependencies.)

Example
-------

Comparing these two documents:

	<html>
		Here is <b>some bold</b> text.
	</html>

and

	<html>
		Here is <i>some italic</i> content that shows how <tt>xml_diff</tt> works.
	</html>	

Yields:

	<documents>
		<html>
			Here is <b>some <del>bold</del></b><del> text</del>.
		</html>
		<html>
			Here is <i>some <ins>italic</ins></i><ins> content that shows how </ins><tt><ins>xml_diff</ins></tt><ins> works</ins>.
		</html>
	</documents>


Installation
------------
	
	sudo apt-get install python3-lxml
	# or
	sudo apt-get install libxml2-dev libxslt1-dev
	sudo pip3 install lxml

	# get my Python extension module for the Google Diff Match Patch library
	# so we can compute differences in text very quickly
	git clone --recursive https://github.com/JoshData/diff_match_patch-python
	cd diff_match_patch-python
	sudo apt-get install python3-dev
	python3 setup.py build
	sudo python3 setup.py install

Running
-------

Compare two XML documents:

	python3 xml_diff.py --tags del,ins doc1.xml doc2.xml > with_changes.xml

