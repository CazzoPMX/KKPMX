# Nuthouse01 - 10/10/2020 - v5.03
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################

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
prune_invalid_faces:
This script will delete any invalid faces in the model, a simple operation.
An invalid face is any face whose 3 defining vertices are not unique with respect to eachother.
This also deletes any duplicate faces within material units (faces defined by the same 3 vertices) and warns about (but doesn not fix) duplicates spanning material units.
'''

iotext = '''Inputs:  PMX file "[model].pmx"\nOutputs: PMX file "[model]_faceprune.pmx"
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

def delete_faces(pmx: pmxstruct.Pmx, faces_to_remove):
	# each material has some number of faces associated with it, those values must be changed when faces are deleted!
	# the question simply becomes, "how many faces within range [start, end] are being deleted"
	# the list of faces being deleted is in known-sorted order
	end_del_face_idx = 0
	start_del_face_idx = 0
	face_id_end = 0
	for mat in pmx.materials:
		face_id_end += mat.faces_ct  # this tracks the id of the final face in this material
		# walk thru the list of faces to remove until i find one that isn't part of the current material,
		# or until i reach the end of the list
		while end_del_face_idx < len(faces_to_remove) and faces_to_remove[end_del_face_idx] < face_id_end:
			end_del_face_idx += 1
		# within the list of faces to be deleted,
		# start_del_face_idx is the idx of the first face that falls within this material's scope,
		# end_del_face_idx is the idx of the first face that falls within THE NEXT material's scope
		# therefore their difference is the number of faces to remove from the current material
		num_remove_from_this_material = end_del_face_idx - start_del_face_idx
		mat.faces_ct -= num_remove_from_this_material
		# update the start idx for next material
		start_del_face_idx = end_del_face_idx
	
	# now, delete the acutal faces
	for f in reversed(faces_to_remove):
		pmx.faces.pop(f)


def prune_invalid_faces(pmx: pmxstruct.Pmx, moreinfo=False):
	#############################
	# ready for logic
	
	faces_to_remove = []
	# identify faces which need removing
	for i,face in enumerate(pmx.faces):
		# valid faces are defined by 3 unique vertices, if the vertices are not unique then the face is invalid
		if 3 != len(set(face)):
			faces_to_remove.append(i)
	
	numinvalid = len(faces_to_remove)
	prevtotal = len(pmx.faces)
	
	if faces_to_remove:
		# do the actual face deletion
		delete_faces(pmx, faces_to_remove)
		
	if numinvalid != 0:
		core.MY_PRINT_FUNC("Found & deleted {} / {} = {:.1%} faces for being invalid".format(
			numinvalid, prevtotal, numinvalid / prevtotal))
	
	#################
	# NEW: delete duplicate faces within materials
	
	# first iter over all faces and comparable hashes from each
	# PROBLEM: faces from the same vertices but reversed are considered different faces, so sorting is not a valid way to differentiate
	# the order of the vertices within the face are what matters, but they can start from any of the 3 points
	# ABC === BCA === CAB
	# therefore I will silently apply a "lowest index first" rule to all faces in the model, to make future runs of this script faster
	# "rotating" the verts within a face shouldn't matter to any rendering mechanisms in any program
	donothing = lambda x: x							# if i==0, don't change it
	headtotail = lambda x: x.append(x.pop(0))		# if i==1, pop the head & move it to the tail
	tailtohead = lambda x: x.insert(0, x.pop(2))	# if i==2, pop the tail & move it to the head
	opdict = {0: donothing, 1: headtotail, 2: tailtohead}
	for f in pmx.faces:
		# for each face, find the index of the minimum vert within the face
		i = f.index(min(f))
		# this can be extremely slow, for maximum efficiency use dict-lambda trick instead of if-else chain.
		# return value isn't used, the pop/append operate on the list reference
		opdict[i](f)
		# now the faces have been rotated in-place and will be saved to file
	
	# now the faces have been rotated so that dupes will align perfectly but mirrors will stay different!!
	# turn each face into a sorted tuple and then hash it, numbers easier to store & compare
	hashfaces = [hash(tuple(f)) for f in pmx.faces]
	# now make a new list where this hashed value is attached to the index of the corresponding face
	f_all_idx = list(range(len(pmx.faces)))
	hashfaces_idx = list(zip(hashfaces, f_all_idx))
	# for each material unit, sort & find dupes
	startidx = 0
	all_dupefaces = []
	for d,mat in enumerate(pmx.materials):
		numfaces = mat.faces_ct
		this_dupefaces = []
		# if there is 1 or 0 faces then there cannot be any dupes, so skip
		if numfaces < 2: continue
		# get the faces for this material & sort by hash so same faces are adjacent
		matfaces = hashfaces_idx[startidx : startidx+numfaces]
		matfaces.sort(key=core.get1st)
		for i in range(1,numfaces):
			# if face i is the same as face i-1,
			if matfaces[i][0] == matfaces[i-1][0]:
				# then save the index of this face
				this_dupefaces.append(matfaces[i][1])
		# always inc startidx after each material
		startidx += numfaces
		# accumulate the dupefaces between each material
		if this_dupefaces:
			all_dupefaces += this_dupefaces
			if moreinfo:
				core.MY_PRINT_FUNC("mat #{:<3} JP='{}' / EN='{}', found {} duplicates".format(
					d, mat.name_jp, mat.name_en, len(this_dupefaces)))
	# this must be in ascending sorted order
	all_dupefaces.sort()
	numdupes = len(all_dupefaces)
	
	# do the actual face deletion
	if all_dupefaces:
		delete_faces(pmx, all_dupefaces)
	
	if numdupes != 0:
		core.MY_PRINT_FUNC("Found & deleted {} / {} = {:.1%} faces for being duplicates within material units".format(
			numdupes, prevtotal, numdupes / prevtotal))
		
	# now find how many duplicates there are spanning material units
	# first delete the dupes we know about from the hash-list
	for f in reversed(all_dupefaces):
		hashfaces.pop(f)
	# then cast hash-list as a set to eliminate dupes and compare sizes to count how many remain
	otherdupes = len(hashfaces) - len(set(hashfaces))
	if otherdupes != 0:
		core.MY_PRINT_FUNC("Warning: Found {} faces which are duplicates spanning material units, did not delete".format(otherdupes))
	
	if numinvalid == 0 and numdupes == 0:
		core.MY_PRINT_FUNC("No changes are required")
		return pmx, False
		
	return pmx, True

def end(pmx, input_filename_pmx):
	# write out
	# output_filename_pmx = "%s_faceprune.pmx" % core.get_clean_basename(input_filename_pmx)
	output_filename_pmx = input_filename_pmx[0:-4] + "_faceprune.pmx"
	output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	pmxlib.write_pmx(output_filename_pmx, pmx, moreinfo=True)
	return None
	
def main():
	showhelp()
	pmx, name = showprompt()
	pmx, is_changed = prune_invalid_faces(pmx)
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

