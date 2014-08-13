#!/usr/bin/python3

# XML document comparison tool
# ============================
#
# Compares the text (only) of two XML documents and inserts <ins>
# and <del> tags into the documents indicating changes.

import re
import lxml.etree
from io import StringIO
from copy import deepcopy

# See below. This is a code point in the Unicode private use area.
node_end_sentinel = "\uE000"

def default_differ(text1, text2):
	try:
		import diff_match_patch
		if hasattr(diff_match_patch, "diff_match_patch"):
			# https://code.google.com/p/google-diff-match-patch/source/browse/trunk/python3/diff_match_patch.py
			for op, oplen in diff_match_patch.diff_match_patch().diff_main(text1, text2):
				if op == -1: op = "-"
				if op == +1: op = "+"
				if op ==  0: op = "="
				yield (op, len(oplen))
		else:
			# https://pypi.python.org/pypi/diff_match_patch_python/1.0.1
			for x in diff_match_patch.diff(text1, text2):
				yield x
	except ImportError:
		import difflib
		diff = difflib.SequenceMatcher(text1, text2, autojunk=False)
		for (tag, i1, i2, j1, j2) in diff.get_opcodes():
			if tag == "equal":
				yield ("=", i2-i1)
			elif tag == "insert":
				yield ("+", j2-j1)
			elif tag == "delete":
				yield ("-", i2-i1)
			elif tag == "replace":
				yield ("-", i2-i1)
				yield ("+", j2-j1)

def compare(
	doc1, doc2,
	differ=default_differ,
	make_tag_func=None,
	tags=('del', 'ins'),
	merge=False,
	word_separator_regex=r"\s+|[^\s\w]", # spaces and punctuation
	):

	# Serialize the text content of the two documents.
	doc1data = serialize_document(doc1)
	doc2data = serialize_document(doc2)

	# Compute the differences in the serialized text.
	diff = perform_diff(
		differ,
		doc1data.text, doc2data.text,
		word_separator_regex=word_separator_regex)
	diff = simplify_diff(diff)
	diff = remove_node_end_sentinels(diff)
	diff = reformat_diff(diff)

	# Add <ins>/<del> tags. The documents are modified in-place.
	if make_tag_func == None:
		def make_tag_func(tag):
			if tag == 'del': tag = tags[0]
			if tag == 'ins': tag = tags[1]
			return lxml.etree.Element(tag)

	add_ins_del_tags(doc1data, doc2data, diff, make_tag_func, merge)

def serialize_document(doc):
	# Takes an etree.Element and returns serialized text,
	# remembering which character ranges corresponded to
	# which nodes in the document

	class State(object):
		pass
	state = State()
	state.dom = doc
	state.text = StringIO()
	state.offsets = list()
	state.charcount = 0

	def append_text(text, node, texttype, state):
		# node.text or node.tail may be None or may be the empty string if there
		# is no actual content there.
		if text is None or len(text) == 0:
			return

		# The XML document may not have whitespace between adjacent elements.
		# When we do a word-by-word diff, the text of one element may abutt
		# the text of the next element and form a "word". To prevent this, add
		# a sentinel after each element that we remove during the diff step.

		textlen = len(text)
		state.text.write(text)
		state.text.write(node_end_sentinel)
		state.offsets.append([state.charcount, textlen, node, texttype])
		state.charcount += textlen

	def recurse_on(node, state):
		# etree handles text oddly: node.text contains the text of the element, but if
		# the element has children then only the text up to its first child, and node.tail
		# contains the text after the element but before the next sibling. To iterate the
		# text in document order, we cannot use node.iter().
		append_text(node.text, node, 0, state) # 0 == .text
		for child in node:
			recurse_on(child, state)
		append_text(node.tail, node, 1, state) # 1 == .tail

	# Recursively serialize the document.
	recurse_on(doc, state)

	if len(state.offsets) == 0:
		# The document may be empty. This will cause problems for
		# inserting merged content. Add a record for the empty text
		# of the root element.
		if doc.text == None: doc.text = ""
		state.offsets.append([0, 0, doc, 0])

	# Replace the io.StringIO with just the string content.
	state.text = state.text.getvalue()

	# Return the serialized data.
	return state

def perform_diff(differ, text1, text2, word_separator_regex):
	# Do a word-by-word comparison, which produces more semantically sensible
	# results. Remove the node_end_sentinel here.

	word_map = { }
	word_map[node_end_sentinel] = chr(254) # ensure it's in there

	def text_to_words(text):
		words = re.split('(' + re.escape(node_end_sentinel) + '|' + word_separator_regex + ')', text)
		encoded_text = StringIO()
		for wd in words:
			if wd == "": continue # when there are multiple delimiters in a row, we may get blanks from re.split
			if wd != node_end_sentinel and node_end_sentinel in wd: raise ValueError(wd)
			wd_code = word_map.setdefault(wd, chr(255 + len(word_map)) )
			encoded_text.write(wd_code)
		return encoded_text.getvalue()

	# Map the text strings to a hacky Unicode character array where characters
	# map to words in the original.
	text1 = text_to_words(text1)
	text2 = text_to_words(text2)

	# Perform the diff on the hacky Unicode string.
	wdiff = differ(text1, text2)

	# Map everything back to real characters.
	word_map_inv = dict((v, k) for (k, v) in word_map.items())
	diff = []
	i1 = 0
	i2 = 0
	for op, oplen in wdiff:
		if op == "-":
			text = text1[i1:i1+oplen]
			i1 += oplen
		elif op == "+":
			text = text2[i2:i2+oplen]
			i2 += oplen
		elif op == "=":
			text = text2[i2:i2+oplen]
			i1 += oplen
			i2 += oplen
		else:
			raise ValueError("differ returned an invalid op code: " + repr(op))
		text = "".join(word_map_inv[c] for c in text)
		for t in re.split("(" + re.escape(node_end_sentinel) + ")", text):
			if t != "":
				yield (op, t)

def remove_node_end_sentinels(diff):
	for op, text in diff:
		text = text.replace(node_end_sentinel, "")
		if len(text) == 0: continue
		yield (op, text)
	
def simplify_diff(diff_iter):
	# Simplify the diff by collapsing any regions with more changes than
	# similarities, so that small unchanged regions appear within the larger
	# set of changes (as changes, not as similarities).
	
	prev = []

	def opposite_op(op):
		return '-' if op == '+' else '+'

	for op, text in diff_iter:
		if len(text) == 0: raise Exception()

		prev.append( (op, text) )

		cycle = True
		while cycle:
			cycle = False

			if len(prev) >= 3 and prev[-1][0] in ('-', '+') and prev[-2][0] == '=':
				threshold = (len(prev[-2][1])-1)**1.5
				if node_end_sentinel in text:
					threshold = 1000

				if len(prev[-3][1]) + len(prev[-1][1]) > threshold:

					# Replace <DEL:a> <EQ:b> <DEL:c> with <DEL:abc> <INS:b>
					if prev[-3][0] == prev[-1][0]:
						prev[-3] = (prev[-1][0], prev[-3][1] + prev[-2][1] + prev[-1][1])
						prev[-2] = (opposite_op(prev[-1][0]), prev[-2][1])
						prev.pop()
						cycle = True

					# If the two hunks differ in prev[-1][0], combine them a different way.
					# Replace <DEL:a> <EQ:b> <INS:c> with <DEL:ab> <INS:bc>
					elif prev[-3][0] == opposite_op(prev[-1][0]):
						prev[-3] = (prev[-3][0], prev[-3][1] + prev[-2][1])
						prev[-2] = (prev[-1][0], prev[-2][1] + prev[-1][1])
						prev.pop()
						cycle = True

			# Because of the above, we may end up with alternating <DEL> <INS> <DEL>
			# which we can collapse too.
			# Replace <DEL:a> <INS:b> <DEL:c> with <DEL:ac> <INS:b>
			if len(prev) >= 3 and prev[-1][0] in ('-', '+') and prev[-3][0] == prev[-1][0] and prev[-2][0] == opposite_op(prev[-1][0]):
				prev[-3] = (prev[-3][0], prev[-3][1] + prev[-1][1])
				prev.pop()
				cycle = True

			# And then replace two of the same ops in a row.
			if len(prev) >= 2 and prev[-2][0] == prev[-1][0]:
				prev[-2] = (prev[-1][0], prev[-2][1] + prev[-1][1])
				prev.pop()
				cycle = True
			
		while len(prev) >= 4:
			yield prev.pop(0)

	for p in prev:
		yield p

def reformat_diff(diff_iter):
	# Re-format the operations of the diffs to indicate the byte
	# offsets on the left and right rather than op and text.
	left_pos = 0
	right_pos = 0
	for op, text in diff_iter:
		length = len(text)
		if length == 0: raise Exception()
		left_len = length if op in ("-", "=") else 0
		right_len = length if op in ("+", "=") else 0
		yield (op, left_pos, left_len, right_pos, right_len)
		left_pos += left_len
		right_pos += right_len
	   
def add_ins_del_tags(doc1data, doc2data, diff, make_tag_func, merge):
	# Iterate through the changes...
	idx = 0
	for op, left_pos, left_len, right_pos, right_len in diff:
		idx += 1

		if op == "=":
			continue

		# Wrap the text on the left side in <del>. Insert it into the right side too.
		if left_len > 0:
			content = mark_text(doc1data, left_pos, left_len, "del", make_tag_func)
			if merge: insert_text(doc2data, right_pos, content, "del", make_tag_func)

		# Wrap the text on the right side in <ins>. Insert it into left side too.
		if right_len > 0:
			content = mark_text(doc2data, right_pos, right_len, "ins", make_tag_func)
			if merge: insert_text(doc1data, left_pos, content, "ins", make_tag_func)

def mark_text(doc, offset, length, mode, make_tag_func):
	# Wrap the text in doc starting at pos and for length characters
	# in tags.

	content = []

	# Discard text ranges that are entirely before this changed region.
	# Don't pop the very last node, though, since we may want to insert merged
	# content at the very end of the document.
	while len(doc.offsets) > 1 and (doc.offsets[0][0] + doc.offsets[0][1]) <= offset:
		doc.offsets.pop(0)

	# Process the text ranges that intersect this changed region.
	while len(doc.offsets) > 0 and ((doc.offsets[0][0] < offset + length) or (length == 0 and doc.offsets[0][0] == offset)):

		# Add the tag.
		wrapper = add_tag(doc.offsets[0], offset, length, mode, make_tag_func)
		content.append(wrapper)

		# If this node is entirely consumed by the change, pop it and iterate.
		if doc.offsets[0][0] + doc.offsets[0][1] <= offset + length:
			# Don't pop the last node in case we need to insert content at
			# the very end of the document. See above.
			if len(doc.offsets) == 1:
				break

			doc.offsets.pop(0)

			# Merge and percolate the wrapper up the tree. If we make either
			# operation, iterate and try again.
			while True:
				if merge_with_previous(wrapper): continue
				if perculate_up(wrapper, doc): continue
				break # no more changes

		else:
			# There is nothing more to mark in the document for this changed
			# region (the changed region was entirely within that node), but
			# keep the node for next time because there might be other changes
			# in this node.
			break

	if len(content) == 0:
		raise Exception("Content did not get marked up (%d+%d): '%s'" % (offset, length, doc.text[offset:offset+length]))

	return content

def merge_with_previous(wrapper):
	p = wrapper.getparent()
	i = p.index(wrapper)

	# Only if the wrapper immediately follows a wrapper element, merge them.
	if i == 0 or p[i-1].tag != wrapper.tag or p[i-1].tail not in ("", None):
		return False

	# Move all of the content of p[i-1] to the beginning of wrapper
	# and then delete p[i-1].
	if wrapper.text is None: wrapper.text = ""
	prev = p[i-1]
	while len(prev) > 0:
		n = prev[-1]
		if n.tail is None: n.tail = ""
		n.tail += wrapper.text
		wrapper.text = ""
		wrapper.insert(0, n)
	if prev.text is not None:
		wrapper.text = prev.text + wrapper.text
	prev.text = None
	p.remove(prev)

	return True

def perculate_up(wrapper, doc):
	# Percolate the wrapper element up so that it contains its parent if
	# a) the wrapper is the only child of the parent
	#   i) the parent has no other children
	#   ii) the wrapper has no tail (would be text within the parent)
	#   iii) the parent has no text itself
	# b) if the parent has a tail, it must be the next thing in the serialization stack
	# c) the parent is not a root element of a document

	p = wrapper.getparent()
	pp = p.getparent()
	i = p.index(wrapper)

	if len(p) > 1 or wrapper.tail not in (None, "") or p.text not in (None, "") \
	 or (p.tail not in (None, "") and (len(doc.offsets) == 0 or doc.offsets[0][2] != p or doc.offsets[0][3] != 1)) \
	 or pp is None:
	 	return False

 	# where is the parent node?
	i = pp.index( wrapper.getparent() )

	# disentagle the hierarchy
	p.remove(wrapper)

	# move the text back down
	p.text = wrapper.text
	wrapper.text = None
	# move the elements back down (the wrapper element may have structure inside of it)
	for n in wrapper:
		p.append(n)
	# move the tail back up
	if p.tail not in (None, ""):
		doc.offsets[0][2] = wrapper
	wrapper.tail = p.tail
	p.tail = None
	# put it back together
	wrapper.append(p)
	pp.insert(i, wrapper)
	return True

def add_tag(node_ref, offset, length, mode, make_tag_func):
	# Get relative character position of start of change, might be negative.
	# If it's negative, adjust offset and length accordingly.
	offset -= node_ref[0]
	if offset < 0:
		length += offset # reduce by the part before the node
		offset = 0

	# Make the new wrapper node.
	wrapper = make_tag_func(mode)

	# Munge the DOM.
	if node_ref[3] == 0:
		add_tag_to_text(node_ref[2], wrapper, offset, length)
	else:
		add_tag_to_tail(node_ref[2], wrapper, offset, length)

	# Unfortunately now we've made the document offsets data
	# inconsistent with the state of the DOM. We can fix this
	# though by saying that any characters after this part
	# are now a part of wrapper's tail.
	node_ref[0] += (offset + length); # shift offset forward
	node_ref[1] -= (offset + length); # reduce length by amount just consumed
	node_ref[2] = wrapper # this text is now tied to the new wrapper element
	node_ref[3] = 1 # whether it was a text or tail before, it's a tail on the wrapper now

	# Return the marked content.
	return wrapper

def add_tag_to_text(node, wrapper, offset, length):
	# node.text is the text that appears before node's first child.
	# We are to wrap some substring within a new node.

	# Copy the wrapped text inside the wrapper. Unless length == 0,
	# which happens just when we're performing a merge and we're
	# copying content from one document into the other. In that case,
	# we've already set wrapper.text to something; don't overwrite it.
	if length > 0:
		wrapper.text = node.text[offset:offset+length]

	# Copy the text that follows the wrapped text into the wrapper's tail.
	wrapper.tail = node.text[offset+length:]

	# Delete the text that's been copied from the node.
	node.text = node.text[0:offset]

	# Append the node so that it is now the first child.
	node.insert(0, wrapper)

def add_tag_to_tail(node, wrapper, offset, length):
	# node.tail is the text that appears after the node's close tag.
	# We are to wrap some substring within a new node.

	# Copy the wrapped text inside the wrapper.
	if length > 0:
		wrapper.text = node.tail[offset:offset+length]

	# Copy the text that follows the wrapped text into the wrapper's tail.
	wrapper.tail = node.tail[offset+length:]

	# Delete the text that's been copied from the node.
	node.tail = node.tail[0:offset]

	# Append the wrapper so that it immediately follows node.
	p = node.getparent()
	p.insert(p.index(node)+1, wrapper)

def insert_text(doc, offset, content, mode, make_tag_func):
	# Insert text from one document into the other. E.g., inserted
	# deleted text (from the left document) into the corresponding
	# position in the right document.
	#
	# We do this by hacking back into mark_text. We ask it to mark
	# a zero-length region using a wrapper node for which we provide
	# the content.

	def make_tag_func_2(mode):
		# Make an ins/del node, and then put inside it the contents
		# of the ins/del nodes marked in the other document.
		n = make_tag_func(mode)
		n.text = ""
		for c in content:
			# c is an ins or del node from the other document
			if c.tag != n.tag: raise ValueError()

			# copy its contents here
			if c.text:
				if len(n) == 0:
					n.text += c.text
				else:
					n[-1].tail += c.text
			for cc in c:
				cc = deepcopy(cc)
				n.append(cc)
				if cc.tail == None: cc.tail = ""

		return n

	mark_text(doc, offset, 0, mode, make_tag_func_2)

