#!/usr/bin/python3

# XML document comparison tool
# ============================
#
# Compares the text (only) of two XML documents and inserts <ins>
# and <del> tags into the documents indicating changes.

import re
import lxml.etree
from io import StringIO

import diff_match_patch

def compare(doc1, doc2, make_tag_func=None, tags=('del', 'ins')):
	# Serialize the text content of the two documents.
	doc1data = serialize_document(doc1)
	doc2data = serialize_document(doc2)

	# Compute the differences in the serialized text.
	diff = perform_diff(doc1data.text, doc2data.text)
	diff = simplify_diff(diff)
	diff = reformat_diff(diff)

	# Add <ins>/<del> tags. The documents are modified in-place.
	if make_tag_func == None:
		def make_tag_func(tag):
			if tag == 'del': tag = tags[0]
			if tag == 'ins': tag = tags[1]
			return lxml.etree.Element(tag)

	add_ins_del_tags(doc1data, doc2data, diff, make_tag_func)

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
		if not text: return # node.text or node.tail may be None
		if text.strip() == "": return # probably not semantic, not worth comparing
		textlen = len(text)
		state.text.write(text)
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

	# Replace the io.StringIO with just the string content.
	state.text = state.text.getvalue()

	# Return the serialized data.
	return state

def perform_diff(text1, text2):
	# Do a word-by-word comparison, which produces more semantically sensible
	# results.

	word_map = { }

	def text_to_words(text):
		words = re.split(r"(\s+|[^\s\w])", text)
		encoded_text = StringIO()
		for wd in words:
			wd_code = word_map.setdefault(wd, chr(255 + len(word_map)) )
			encoded_text.write(wd_code)
		return encoded_text.getvalue()

	# Map the text strings to a hacky Unicode character array where characters
	# map to words in the original.
	text1 = text_to_words(text1)
	text2 = text_to_words(text2)

	# Perform the diff on the hacky Unicode string.
	wdiff = diff_match_patch.diff(
		text1, text2,
		timelimit=0,
        checklines=False)

	# Map everything back to real characters.
	word_map_inv = dict((v, k) for (k, v) in word_map.items())
	diff = []
	i1 = 0
	i2 = 0
	for op, woplen in wdiff:
		oplen = 0
		if op == "-":
			for i in range(woplen):
				oplen += len(word_map_inv[text1[i1 + i]])
			i1 += woplen
		elif op == "+":
			for i in range(woplen):
				oplen += len(word_map_inv[text2[i2 + i]])
			i2 += woplen
		elif op == "=":
			for i in range(woplen):
				oplen += len(word_map_inv[text2[i2 + i]])
			i1 += woplen
			i2 += woplen
		diff.append( (op, oplen) )

	return diff

	
def simplify_diff(diff_iter):
	# Simplify the diff by collapsing any regions with more changes than
	# similarities, so that small unchanged regions appear within the larger
	# set of changes (as changes, not as similarities).
	prev = []
	for op, length in diff_iter:
		if len(prev) < 2:
			prev.append( (op, length) )
		else:
			# If the op two hunks ago is the same as the current hunk and
			# the total lengths of two hunks ago and the current is creater
			# than the length of the hunk in the middle...
			if op in ('-', '+') and prev[0][0] == op and prev[1][0] == '=' \
				and prev[1][1] > 0 and prev[0][1] + length > (prev[1][1]-1)**1.4:
				prev.append( (op, prev[0][1] + prev[1][1] + length) )
				prev.append( ('-' if op == '+' else '+', prev[1][1]) )
				prev.pop(0)
				prev.pop(0)
				
			# If the two hunks differ in op, combine them a different way.
			elif op in ('-', '+') and prev[0][0] in ('-', '+') and prev[1][0] == '=' \
				and prev[1][1] > 0 and prev[0][1] + length > (prev[1][1]-1)**1.4:
				prev.append( (prev[0][0], prev[0][1] + prev[1][1]) )
				prev.append( (op, prev[1][1] + length) )
				prev.pop(0)
				prev.pop(0)
			
			else:
				yield prev.pop(0)
				prev.append( (op, length) )
	for p in prev:
		yield p

def reformat_diff(diff_iter):
	# Re-format the operations of the diffs to indicate the byte
	# offsets on the left and right rather than op and length.
	left_pos = 0
	right_pos = 0
	for op, length in diff_iter:
		left_len = length if op in ("-", "=") else 0
		right_len = length if op in ("+", "=") else 0
		yield (op, left_pos, left_len, right_pos, right_len)
		left_pos += left_len
		right_pos += right_len
	   
def add_ins_del_tags(doc1data, doc2data, diff, make_tag_func):
	# Iterate through the changes...
	idx = 0
	for op, left_pos, left_len, right_pos, right_len in diff:
		idx += 1

		if op == "=":
			# Don't mark regions that are unchanged. Not sure why I'm
			# double-checking that the text hasn't changed.
			if doc1data.text[left_pos:left_pos+left_len] == doc2data.text[right_pos:right_pos+right_len]:
				continue

		# Wrap the text on the left side in <del>.
		if left_len > 0:
			mark_text(doc1data, left_pos, left_len, "del", make_tag_func)

		# Wrap the text on the right side in <ins>.
		if right_len > 0:
			mark_text(doc2data, right_pos, right_len, "ins", make_tag_func)

def mark_text(doc, offset, length, mode, make_tag_func):
   # Wrap the text in doc starting at pos and for length characters
   # in tags.

	# Discard text ranges that are entirely before this changed region.
	while len(doc.offsets) > 0 and (doc.offsets[0][0] + doc.offsets[0][1]) <= offset:
		doc.offsets.pop(0)

	# Process the text ranges that intersect this changed region.
	while len(doc.offsets) > 0 and doc.offsets[0][0] < offset + length:
		# Add the tag.
		add_tag(doc.offsets[0], offset, length, mode, make_tag_func)

		# If this node is entirely consumed by the change, pop it and iterate.
		if doc.offsets[0][0] + doc.offsets[0][1] <= offset + length:
			doc.offsets.pop(0)
		else:
			# There is nothing more to mark in the document for this changed
			# region (the changed region was entirely within that node), but
			# keep the node for next time because there might be other changes
			# in this node.
			break

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

def add_tag_to_text(node, wrapper, offset, length):
	# node.text is the text that appears before node's first child.
	# We are to wrap some substring within a new node.

	# Copy the wrapped text inside the wrapper.
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
	wrapper.text = node.tail[offset:offset+length]

	# Copy the text that follows the wrapped text into the wrapper's tail.
	wrapper.tail = node.tail[offset+length:]

	# Delete the text that's been copied from the node.
	node.tail = node.tail[0:offset]

	# Append the wrapper so that it immediately follows node.
	p = node.getparent()
	p.insert(p.index(node)+1, wrapper)


