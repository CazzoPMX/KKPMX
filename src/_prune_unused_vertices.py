# Nuthouse01 - 12/20/2020 - v5.04
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################

# first, system imports
from typing import List, Tuple, TypeVar

# second, wrap custom imports with a try-except to catch it if files are missing
try:
	# these imports work if running from GUI
	from . import nuthouse01_core as core
	from . import nuthouse01_pmx_parser as pmxlib
	from . import nuthouse01_pmx_struct as pmxstruct
except ImportError as eee:
	try:
		# these imports work if running from double-click on THIS script
		import nuthouse01_core as core
		import nuthouse01_pmx_parser as pmxlib
		import nuthouse01_pmx_struct as pmxstruct
	except ImportError as eee:
		print(eee.__class__.__name__, eee)
		print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
		print("...press ENTER to exit...")
		input()
		exit()
		core = pmxlib = pmxstruct = None


# when debug=True, disable the catchall try-except block. this means the full stack trace gets printed when it crashes,
# but if launched in a new window it exits immediately so you can't read it.
DEBUG = False


helptext = '''====================
prune_unused_vertices:
This script will delete any unused vertices from the model, sometimes causing massive file size improvements.
An unused vertex is one which is not used to define any faces.
'''

iotext = '''Inputs:  PMX file "[model].pmx"\nOutputs: PMX file "[model]_vertprune.pmx"
'''


INT_OR_INTLIST = TypeVar("INT_OR_INTLIST", int, List[int])
def newval_from_range_map(v: INT_OR_INTLIST, range_map: Tuple[List[int], List[int]]) -> INT_OR_INTLIST:
	"""
	Given a rangemap from delme_list_to_rangemap(), determine the resulting index for an input or set of inputs.
	If v is a list, it must be in ascending sorted order. Returns same type as v type.
	
	:param v: int or list of ints in ascending sorted order
	:param range_map: result from delme_list_to_rangemap()
	:return: int if v is int, list[int] if v is list[int]
	"""
	# support both int and list-of-int inputs... do basically the same thing, just looped
	# if input is list, IT MUST BE IN ASCENDING SORTED ORDER
	# core idea: walk BACKWARDS along the range_map until i find the start that is CLOSEST BELOW the input v
	if isinstance(v, int):
		# # bisect_right: same as bisect_left but when matching something already in it it goes one to the right
		pos = core.bisect_right(range_map[0], v)
		if pos == 0:
			# if it doesnt find a block starting below v, then the offset is 0
			return v
		else:
			# return the input value minus the applicable offset
			return v - range_map[1][pos-1]
	else:
		# if given a list, the list is ordered so take advantage of that to pick up where the previous item left off
		# walk backwards along both lists side-by-side
		retme = []
		input_idx = len(v) - 1
		idx = len(range_map[0]) - 1
		while idx >= 0 and input_idx >= 0:
			if range_map[0][idx] <= v[input_idx]:
				# return the input value minus the applicable offset
				retme.append(v[input_idx] - range_map[1][idx])
				input_idx -= 1
			else:
				idx -= 1
		if input_idx != -1:
			# if it finished walking down the range-list before it finished the input-list, all remaining inputs are unchanged
			retme += reversed(v[0:input_idx+1])
		retme.reverse()
		return retme
	
def delme_list_to_rangemap(delme_verts: List[int]) -> Tuple[List[int],List[int]]:
	"""
	Given an ascending sorted list of ints, build a pair of lists that let me know what indices OTHER things will map
	to when THESE indices are deleted. list1 is the index each cluster starts at, list2 is where that index will map
	to after the deletion happens.
	Exclusively used with newval_from_range_map().
	
	:param delme_verts: ascending sorted list of ints
	:return: tuple(list-of-starts, list-of-cumulativelength)
	"""
	
	if delme_verts and not all(delme_verts[i] <= delme_verts[i + 1] for i in range(len(delme_verts) - 1)):
		core.MY_PRINT_FUNC("BUG DETECTED: delme_list_to_rangemap() received argument not in sorted order!!")
		raise ValueError("BUG DETECTED: delme_list_to_rangemap() received argument not in sorted order!!")
	delme_range = []
	start_idx = 0
	for end_idx in range(1, len(delme_verts)+1):
		if (end_idx == len(delme_verts)) or (delme_verts[end_idx] != (delme_verts[end_idx-1] + 1)):
			# if the next vert ID is non-contiguous, or is the end of the list, that defines a breakpoint between ranges
			# that means that everything from start to end IS contiguous
			# so save the VALUE of the start, and the LENGTH of the range (which equals the length of the block)
			delme_range.append([delme_verts[start_idx], end_idx - start_idx])
			start_idx = end_idx
	# convert from [start-length] to [start-cumulativelength]
	for i in range(1, len(delme_range)):
		delme_range[i][1] += delme_range[i-1][1]
	# convert from [[start,len],[start,len],[start,len]] to [[start,start,start],[len,len,len]]
	a,b = zip(*delme_range)
	return a,b


def showhelp():
	# print info to explain the purpose of this file
	core.MY_PRINT_FUNC(helptext)
def showprompt():
	# print info to explain what inputs/outputs it needs/creates
	core.MY_PRINT_FUNC(iotext)
	
	# prompt PMX name
	core.MY_PRINT_FUNC("Please enter name of PMX model file:")
	input_filename_pmx = core.prompt_user_filename(".pmx")
	pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=True)
	return pmx, input_filename_pmx

def prune_unused_vertices(pmx: pmxstruct.Pmx, moreinfo=False):
	#############################
	# ready for logic

	# vertices are referenced in faces, morphs (uv and vertex morphs), and soft bodies (should be handled just for completeness' sake)
	
	# find individual vertices to delete
	#		build set of vertices used in faces
	#		build set of all vertices (just a range)
	#		subtract
	#		convert to sorted list
	# convert to list of [begin, length]
	#		iterate over delvertlist, identify contiguous blocks
	# convert to list of [begin, cumulative size]
	
	# build set of USED vertices
	used_verts = set()
	for face in pmx.faces:
		used_verts.add(face[0])
		used_verts.add(face[1])
		used_verts.add(face[2])
	# build set of ALL vertices
	all_verts = set(list(range(len(pmx.verts))))
	# derive set of UNUSED vertices
	unused_verts = all_verts.difference(used_verts)
	# convert to ordered list
	delme_verts = sorted(list(unused_verts))
	
	numdeleted = len(delme_verts)
	prevtotal = len(pmx.verts)
	if numdeleted == 0:
		core.MY_PRINT_FUNC("No changes are required")
		return pmx, False
	
	delme_range = delme_list_to_rangemap(delme_verts)
	
	if moreinfo:
		core.MY_PRINT_FUNC("Detected %d orphan vertices arranged in %d contiguous blocks" % (len(delme_verts), len(delme_range[0])))
	
	# need to update places that reference vertices: faces, morphs, softbody
	# first get the total # of iterations I need to do, for progress purposes: #faces + sum of len of all UV and vert morphs
	totalwork = len(pmx.faces) + sum([len(m.items) for m in pmx.morphs if (m.morphtype in (1,3,4,5,6,7))])
	
	# faces:
	d = 0
	for d,face in enumerate(pmx.faces):
		# vertices in a face are not guaranteed sorted, and sorting them is a Very Bad Idea
		# therefore they must be remapped individually
		face[0] = newval_from_range_map(face[0], delme_range)
		face[1] = newval_from_range_map(face[1], delme_range)
		face[2] = newval_from_range_map(face[2], delme_range)
		# display progress printouts
		core.print_progress_oneline(d / totalwork)
		
	# core.MY_PRINT_FUNC("Done updating vertex references in faces")
	
	# morphs:
	orphan_vertex_references = 0
	for morph in pmx.morphs:
		# if not a vertex morph or UV morph, skip it
		if not morph.morphtype in (1,3,4,5,6,7): continue
		lenbefore = len(morph.items)
		# it is plausible that vertex/uv morphs could reference orphan vertices, so I should check for and delete those
		i = 0
		while i < len(morph.items):
			# if the vertex being manipulated is in the list of verts being deleted,
			if core.binary_search_isin(morph.items[i].vert_idx, delme_verts):
				# delete it here too
				morph.items.pop(i)
				orphan_vertex_references += 1
			else:
				# otherwise, remap it
				# but don't remap it here, wait until I'm done deleting vertices and then tackle them all at once
				i += 1
		
		# morphs usually contain vertexes in sorted order, but not guaranteed!!! MAKE it sorted, nobody will mind
		morph.items.sort(key=lambda x: x.vert_idx)
		
		# separate the vertices from the morph entries into a list of their own, for more efficient remapping
		vertlist = [x.vert_idx for x in morph.items]
		# remap
		remappedlist = newval_from_range_map(vertlist, delme_range)
		# write the remapped values back into where they came from
		for x, newval in zip(morph.items, remappedlist):
			x.vert_idx = newval
		# display progress printouts
		d += lenbefore
		core.print_progress_oneline(d / totalwork)

	# core.MY_PRINT_FUNC("Done updating vertex references in morphs")
	
	# softbody: probably not relevant but eh
	for soft in pmx.softbodies:
		# anchors
		# first, delete any references to delme verts in the anchors
		i = 0
		while i < len(soft.anchors_list):
			# if the vertex referenced is in the list of verts being deleted,
			if core.binary_search_isin(soft.anchors_list[i][1], delme_verts):
				# delete it here too
				soft.anchors_list.pop(i)
			else:
				# otherwise, remap it
				# but don't remap it here, wait until I'm done deleting vertices and then tackle them all at once
				i += 1
		
		#  MAKE it sorted, nobody will mind
		soft.anchors_list.sort(key=lambda x: x[1])
		# extract the vert indices into a list of their town
		anchorlist = [x[1] for x in soft.anchors_list]
		# remap
		newanchorlist = newval_from_range_map(anchorlist, delme_range)
		# write the remapped values back into where they came from
		for x, newval in zip(soft.anchors_list, newanchorlist):
			x[1] = newval
		
		# vertex pins
		# first, delete any references to delme verts
		i = 0
		while i < len(soft.vertex_pin_list):
			# if the vertex referenced is in the list of verts being deleted,
			if core.binary_search_isin(soft.vertex_pin_list[i], delme_verts):
				# delete it here too
				soft.vertex_pin_list.pop(i)
			else:
				# otherwise, remap it
				# but don't remap it here, wait until I'm done deleting vertices and then tackle them all at once
				i += 1
		#  MAKE it sorted, nobody will mind
		soft.anchors_list.sort()
		# remap
		soft.vertex_pin_list = newval_from_range_map(soft.vertex_pin_list, delme_range)
		# done with softbodies!
		
	# now, finally, actually delete the vertices from the vertex list
	delme_verts.reverse()
	for f in delme_verts:
		pmx.verts.pop(f)
	
	core.MY_PRINT_FUNC("Identified and deleted {} / {} = {:.1%} vertices for being unused".format(
		numdeleted, prevtotal, numdeleted/prevtotal))
	
	return pmx, True

def end(pmx, input_filename_pmx):
	# write out
	# output_filename_pmx = "%s_vertprune.pmx" % core.get_clean_basename(input_filename_pmx)
	output_filename_pmx = input_filename_pmx[0:-4] + "_vertprune.pmx"
	output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	pmxlib.write_pmx(output_filename_pmx, pmx, moreinfo=True)
	return None
	
def main():
	showhelp()
	pmx, name = showprompt()
	pmx, is_changed = prune_unused_vertices(pmx)
	if is_changed:
		end(pmx, name)
	core.pause_and_quit("Done with everything! Goodbye!")


if __name__ == '__main__':
	core.MY_PRINT_FUNC("Nuthouse01 - 12/20/2020 - v5.04")
	if DEBUG:
		main()
	else:
		try:
			main()
		except (KeyboardInterrupt, SystemExit):
			# this is normal and expected, do nothing and die normally
			pass
		except Exception as ee:
			# if an unexpected error occurs, catch it and print it and call pause_and_quit so the window stays open for a bit
			core.MY_PRINT_FUNC(ee)
			core.pause_and_quit("ERROR: something truly strange and unexpected has occurred, sorry, good luck figuring out what tho")
