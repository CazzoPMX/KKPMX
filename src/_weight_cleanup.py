# Nuthouse01 - 10/10/2020 - v5.03
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################

# first, system imports
from typing import List, Tuple

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
weight_cleanup:
This function will fix the vertex weights that are weighted twice to the same bone, a minor issue that sometimes happens when merging bones.
This also normalizes the weights of all vertices, and normalizes the normal vectors for all vertices.
'''

iotext = '''Inputs:  PMX file "[model].pmx"\nOutputs: PMX file "[model]_weightfix.pmx"
'''


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


def normalize_weights(pmx: pmxstruct.Pmx) -> int:
	"""
	Normalize weights for verts in the PMX object. Also "clean" the weights by removing bones with 0 weight, reducing
	weight type to lowest possible, and sorting them by greatest weight. Return the # of vertices that were modified.
	
	:param pmx: PMX object
	:return: int, # of vertices that were modified
	"""
	# number of vertices fixed
	weight_fix = 0
	
	# for each vertex:
	for d, vert in enumerate(pmx.verts):
		# clean/normalize the weights
		weighttype = vert.weighttype
		w = vert.weight
		# type0=BDEF1, one bone has 100% weight
		# do nothing
		# type1=BDEF2, 2 bones 1 weight (other is implicit)
		# merge, see if it can reduce to BDEF1
		# type2=BDEF4, 4 bones 4 weights
		# normalize, merge, see if it can reduce to BDEF1/2
		# type3=SDEF, 2 bones 1 weight and 12 values i don't understand.
		# nothing
		# type4=QDEF, 4 bones 4 weights
		# normalize, merge
		if weighttype == 0:  # BDEF1
			# nothing to be fixed here
			continue
		elif weighttype == 1:  # BDEF2
			# no need to normalize because the 2nd weight is implicit, not explicit
			# only merge dupes, look for reason to reduce to BDEF1: bones are same, weight is 0/1
			if w[0] == w[1] or w[2] == 1:  # same bones handled the same way as firstbone with weight 1
				weight_fix += 1
				vert.weighttype = 0  # set to BDEF1
				vert.weight = [w[0]]
			elif w[2] == 0:  # firstbone has weight 0
				weight_fix += 1
				vert.weighttype = 0  # set to BDEF1
				vert.weight = [w[1]]
			continue
		elif weighttype == 2 or weighttype == 4:  # BDEF4/QDEF
			# qdef: check for dupes and also normalize
			bones = w[0:4]
			weights = w[4:8]
			is_modified = False
			
			# unify dupes
			usedbones = []
			for i in range(4):
				if not (bones[i] == 0 and weights[i] == 0.0) and (bones[i] in usedbones):
					is_modified = True  # then this is a duplicate bone!
					where = usedbones.index(bones[i])  # find index where it was first used
					weights[where] += weights[i]  # combine this bone's weight with the first place it was used
					bones[i] = 0  # set this bone to null
					weights[i] = 0.0  # set this weight to 0
				# add to list of usedbones regardless of whether first or dupe
				usedbones.append(bones[i])
				
			# sort by greatest weight
			before = tuple(bones)
			together = list(zip(bones, weights))  # zip
			together.sort(reverse=True, key=lambda x: x[1])  # sort
			a, b = zip(*together)  # unzip
			if hash(before) != hash(a):  # did the order change?
				is_modified = True
				bones = list(a)
				weights = list(b)
				
			# normalize if needed
			s = sum(weights)
			if round(s, 6) != 1.0:
				if s == 0:
					core.MY_PRINT_FUNC("Error: vert %d has BDEF4 weights that sum to 0, cannot normalize" % d)
					continue
				# it needs it, do it
				weights = [t / s for t in weights]
				is_modified = True
				
				try:
					# where is the first 0 in the weight list? i know it is sorted descending
					i = weights.index(0)
					if i == 1:  # first zero at 1, therefore has 1 entry, therefore force to be BDEF1!
						weight_fix += 1
						vert.weighttype = 0  # set to BDEF1
						vert.weight = [bones[0]]
						continue
					if weighttype == 2:  # BDEF4 ONLY: check if it can be reduced to BDEF2
						if i == 2:  # first zero at 2, therefore has 2 nonzero entries, therefore force to be BDEF2!
							weight_fix += 1
							vert.weighttype = 1  # set to BDEF2
							vert.weight = [bones[0], bones[1], weights[0]]
							continue
						# if i == 3, fall thru
				except ValueError:
					pass  # if '0' not found in list, it is using all 4, fall thru
			
			# is QDEF, or was BDEF and determined to still be BDEF4
			# type stays the same, but have i changed the values? if so store and increment
			if is_modified:
				w[0:4] = bones
				w[4:8] = weights
				weight_fix += 1
		elif weighttype == 3:  # SDEF
			# the order of the bones makes a very very slight difference, so dont try to reorder them
			# do try to compress to BDEF1 if the bones are the same or if one has 100 or 0 weight
			if w[0] == w[1] or w[2] == 1:  # same bones handled the same way as firstbone with weight 1
				weight_fix += 1
				vert.weighttype = 0  # set to BDEF1
				vert.weight = [w[0]]
			elif w[2] == 0:  # firstbone has weight 0
				weight_fix += 1
				vert.weighttype = 0  # set to BDEF1
				vert.weight = [w[1]]
			continue
		else:
			core.MY_PRINT_FUNC("ERROR: invalid weight type for vertex %d" % d)
		pass  # close the for-each-vert loop
	# how many did I change? printing is handled outside
	return weight_fix

def normalize_normals(pmx: pmxstruct.Pmx) -> Tuple[int,List[int]]:
	"""
	Normalize normal vectors for each vertex in the PMX object. Return # of verts that were modified, and also a list
	of all vert indexes that have 0,0,0 normals and need special handling.
	
	:param pmx: PMX list-of-lists object
	:return: # verts modified + list of all vert idxs that have 0,0,0 normals
	"""
	norm_fix = 0
	
	normbad = []
	for d,vert in enumerate(pmx.verts):
		# normalize the normal
		if vert.norm == [0, 0, 0]:
			# invalid normals will be taken care of below
			normbad.append(d)
		else:
			norm_L = core.my_euclidian_distance(vert.norm)
			if round(norm_L, 6) != 1.0:
				norm_fix += 1
				vert.norm = [n / norm_L for n in vert.norm]
	# printing is handled outside
	return norm_fix, normbad

def repair_invalid_normals(pmx: pmxstruct.Pmx, normbad: List[int]) -> int:
	"""
	Repair all 0,0,0 normals in the model by averaging the normal vector for each face that vertex is a member of.
	It is theoretically possible for a vertex to be a member in two faces with exactly opposite normals, and therefore
	the average would be zero; in this case one of the faces is arbitrarily chosen and its normal is used. Therefore,
	after this function all invalid normals are guaranteed to be fixed.
	Returns the number of times this fallback method was used.
	
	:param pmx: PMX list-of-lists object
	:param normbad: list of vertex indices so I don't need to walk all vertices again
	:return: # times fallback method was used
	"""
	normbad_err = 0
	# create a list in parallel with the faces list for holding the perpendicular normal to each face
	facenorm_list = [list() for i in pmx.faces]
	# create a list in paralle with normbad for holding the set of faces connected to each bad-norm vert
	normbad_linked_faces = [list() for i in normbad]
	
	# goal: build the sets of faces that are associated with each bad vertex
	
	# first, flatten the list of face-vertices, probably faster to search that way
	flatlist = [item for sublist in pmx.faces for item in sublist]
	
	# second, for each face-vertex, check if it is a bad vertex
	# (this takes 70% of time)
	for d, facevert in enumerate(flatlist):
		core.print_progress_oneline(.7 * d / len(flatlist))
		# bad vertices are unique and in sorted order, can use binary search to further optimize
		whereinlist = core.binary_search_wherein(facevert, normbad)
		if whereinlist != -1:
			# if it is a bad vertex, int div by 3 to get face ID
			(normbad_linked_faces[whereinlist]).append(d // 3)
	
	# for each bad vert:
	# (this takes 30% of time)
	for d, (badvert_idx, badvert_faces) in enumerate(zip(normbad, normbad_linked_faces)):
		newnorm = [0, 0, 0]  # default value in case something goes wrong
		core.print_progress_oneline(.7 + (.3 * d / len(normbad)))
		# iterate over the faces it is connected to
		for face_id in badvert_faces:
			# for each face, does the perpendicular normal already exist in the parallel list? if not, calculate and save it for reuse
			facenorm = facenorm_list[face_id]
			if not facenorm:
				# need to calculate it! use cross product or whatever
				# q,r,s order of vertices is important!
				q = pmx.verts[ pmx.faces[face_id][0] ].pos
				r = pmx.verts[ pmx.faces[face_id][1] ].pos
				s = pmx.verts[ pmx.faces[face_id][2] ].pos
				# qr, qs order of vertices is critically important!
				qr = [r[i] - q[i] for i in range(3)]
				qs = [s[i] - q[i] for i in range(3)]
				facenorm = core.my_cross_product(qr, qs)
				# then normalize the fresh normal
				norm_L = core.my_euclidian_distance(facenorm)
				try:
					facenorm = [n / norm_L for n in facenorm]
				except ZeroDivisionError:
					# this should never happen in normal cases
					# however it can happen when the verts are at the same position and therefore their face has zero surface area
					facenorm = [0, 1, 0]
				# then save the result so I don't have to do this again
				facenorm_list[face_id] = facenorm
			# once I have the perpendicular normal for this face, then accumulate it (will divide later to get avg)
			for i in range(3):
				newnorm[i] += facenorm[i]
		# error case check, theoretically possible for this to happen if there are no connected faces or their normals exactly cancel out
		if newnorm == [0, 0, 0]:
			if len(badvert_faces) == 0:
				# if there are no connected faces, set the normal to 0,1,0 (same handling as PMXE)
				pmx.verts[badvert_idx].norm = [0, 1, 0]
			else:
				# if there are faces that just so happened to perfectly cancel, choose the first face and use its normal
				pmx.verts[badvert_idx].norm = facenorm_list[badvert_faces[0]]
			normbad_err += 1
			continue
		# when done accumulating, divide by # to make an average
		# zerodiv err not possible: if there are no connected faces then it will hit [0,0,0] branch above
		newnorm = [n / len(badvert_faces) for n in newnorm]
		# then normalize this, again
		norm_L = core.my_euclidian_distance(newnorm)
		newnorm = [n / norm_L for n in newnorm]
		# finally, apply this new normal
		pmx.verts[badvert_idx].norm = newnorm
	return normbad_err



# TODO: rename this script & this function
def weight_cleanup(pmx: pmxstruct.Pmx, moreinfo=False):
	
	#############################
	# part 1: fix all the weights, get an answer for how many i changed
	weight_fix = normalize_weights(pmx)
	
	if weight_fix:
		core.MY_PRINT_FUNC("Fixed weights for {} / {} = {:.1%} of all vertices".format(
			weight_fix, len(pmx.verts), weight_fix/len(pmx.verts)))
	
	#############################
	# part 2: normalize all normals that aren't invalid, also count how many are invalid
	# also build 'normbad' to identify all verts w/ 0,0,0 normals so I can get a progress % in following step
	norm_fix, normbad = normalize_normals(pmx)
	
	if norm_fix:
		core.MY_PRINT_FUNC("Normalized normals for {} / {} = {:.1%} of all vertices".format(
			norm_fix, len(pmx.verts), norm_fix / len(pmx.verts)))
	
	#############################
	# part 3: normalize all the normals that were invalid
	if normbad:
		normbad_err = repair_invalid_normals(pmx, normbad)
		core.MY_PRINT_FUNC("Repaired invalid normals for {} / {} = {:.1%} of all vertices".format(
			len(normbad), len(pmx.verts), len(normbad) / len(pmx.verts)))
		if normbad_err and moreinfo:
			core.MY_PRINT_FUNC("WARNING: used fallback vertex repair method for %d vertices" % normbad_err)
	
	if weight_fix == 0 and norm_fix == 0 and len(normbad) == 0:
		core.MY_PRINT_FUNC("No changes are required")
		return pmx, False
	
	return pmx, True
	
def end(pmx, input_filename_pmx):
	# write out
	# output_filename_pmx = "%s_weightfix.pmx" % core.get_clean_basename(input_filename_pmx)
	output_filename_pmx = input_filename_pmx[0:-4] + "_weightfix.pmx"
	output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	pmxlib.write_pmx(output_filename_pmx, pmx, moreinfo=True)
	return None
	
def main():
	showhelp()
	pmx, name = showprompt()
	pmx, is_changed = weight_cleanup(pmx)
	if is_changed:
		end(pmx, name)
	core.pause_and_quit("Done with everything! Goodbye!")


if __name__ == '__main__':
	core.MY_PRINT_FUNC("Nuthouse01 - 10/10/2020 - v5.03")
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

