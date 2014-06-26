import sys
import lxml.etree
from xml_diff import compare

if len(sys.argv) < 3:
	print("Usage: python3 xml_diff.py [--tags del,ins] before.xml after.xml", file=sys.stderr)
	sys.exit(1)

args = sys.argv[1:]

tags = ['del', 'ins']
if args[0] == "--tags":
	args.pop(0)
	tags = args.pop(0).split(",")

# Load the documents and munge them in-place.
dom1 = lxml.etree.parse(args[0]).getroot()
dom2 = lxml.etree.parse(args[1]).getroot()
compare(dom1, dom2, tags=tags)

# Output changed documents.
output = lxml.etree.Element("documents")
output.append(dom1)
output.append(dom2)
print(lxml.etree.tostring(output, encoding=str))