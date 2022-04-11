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
bonedeform_fix:
This function fixes bone deform order issues. This frequently occurs with "finger curl"-type bones.
Ensure that each bone will have its position/rotation calculated after all bones it inherits from.
This can usually be fixed by reordering bones but this script fixes it by modifying the bone deform layers instead.
Specifically this looks at parents, parial-inherit, and IK target/chains, and ensures that either the downstream bone is lower in the list or has a higher deform layer than its parents.
'''

iotext = '''Inputs:  PMX file "[model].pmx"\nOutputs: PMX file "[model]_bonedeform.pmx"
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

def bonedeform_fix(pmx: pmxstruct.Pmx, moreinfo=False):
	# make a parallel list of the deform layers for each bone so I can work there
	# if I encounter a recursive relationship I will have not touched the acutal PMX and can err and return it unchanged
	deforms = [p.deform_layer for p in pmx.bones]
	
	# make a list of the "ik master" for each bone
	# it is possible for a bone to be controlled by multiple IK masters, actually every foot bone of every model is this way
	ikmasters = [set() for x in pmx.bones]
	
	for d,bone in enumerate(pmx.bones):
		# find IK bones
		if bone.has_ik:
			# target uses me as master
			ikmasters[bone.ik_target_idx].add(d)
			for link in bone.ik_links:
				# links use me as master
				ikmasters[link.idx].add(d)
	
	modified_bones = set()
	
	# ASK: does "me" deform after "parent"?
	def good_deform_relationship(me_idx, parent_idx):
		# anything that inherits from an IKCHAIN bone has to be >= that bone's ik master, EXCEPT for bones actually in that ik group
		# if parent has a master AND (parent master != my master): parent=max(parent,master), but need to expand this for sets:
		# if parent has a master AND no overlap between my master and parent master: parent=max(parent,master)=master cuz master >= parent
		# else: parent=parent
		if ikmasters[parent_idx]:
			# is me in the IK group of the parent? me is the ikmaster or me shares an ikmaster with parent
			# if this IS in the ik group then DON'T overwrite parent_idx
			if not (me_idx in ikmasters[parent_idx] or ikmasters[me_idx].intersection(ikmasters[parent_idx])):
				l = list(ikmasters[parent_idx]) # turn set into list
				l.sort() # sort by bone order, tiebreaker
				l.sort(key=lambda x: deforms[x]) # sort by deform level, primary sort
				parent_idx = l[-1] # this means the parent is the last-deforming master of any masters of the bone
		
		# "after" means idx>source and layer >= source or idx<source and layer > source
		# note: if somehow me_idx == parent_idx this returns true to prevent infinite looping
		if me_idx < parent_idx:
			if deforms[me_idx] > deforms[parent_idx]:
				return True
		else: # if me_idx >= parent_idx
			if deforms[me_idx] >= deforms[parent_idx]:
				return True
		return False
	
	# loop until nothing changes, or until 1000 iterations (indicates recursive relationship)
	loops = 0
	while loops < 1000:
		loops += 1
		has_changed = False
		for d,bone in enumerate(pmx.bones):
			# decide if this bone has a good deform layer!
			is_good = True
			# each bone must deform after its parent
			if bone.parent_idx != -1: # -1 is not a valid parent to check
				is_good &= good_deform_relationship(d, bone.parent_idx)
			# each bone must deform after its partial inherit source, if it uses it
			if (bone.inherit_trans or bone.inherit_rot) and bone.inherit_ratio != 0 and bone.inherit_parent_idx != -1:
				is_good &= good_deform_relationship(d, bone.inherit_parent_idx)
			# each ik bone must deform after its target and IK chain
			if bone.has_ik:
				# target
				is_good &= good_deform_relationship(d, bone.ik_target_idx)
				for link in bone.ik_links:
					# links
					is_good &= good_deform_relationship(d, link.idx)
			# if the relationship is NOT good, then raise the deform layer of this bone
			if not is_good:
				has_changed = True
				modified_bones.add(d)
				deforms[d] += 1
			pass  # end for-loop
		
		# this is the while-loop exit condition
		if not has_changed:
			break
		pass  # end while-loop
	
	# did it break because of recursion error?
	if loops == 1000:
		# if yes, warn & return without changes
		core.MY_PRINT_FUNC("ERROR: recursive inheritance relationship among bones!! You must manually investigate and resolve this issue.")
		suspects = [i for i,de in enumerate(deforms) if de > 50]
		core.MY_PRINT_FUNC("Suspicious bones: " + str(suspects))
		core.MY_PRINT_FUNC("Bone deform order not changed")
		return pmx, False
	
	if not modified_bones:
		core.MY_PRINT_FUNC("No changes are required")
		return pmx, False
	
	# if something did change,
	if moreinfo:
		deforms_orig = [p.deform_layer for p in pmx.bones]
		for d, (o, n) in enumerate(zip(deforms_orig, deforms)):
			if o != n:
				core.MY_PRINT_FUNC("bone #{:<3} JP='{}' / EN='{}', deform: {} --> {}".format(
					d, pmx.bones[d].name_jp, pmx.bones[d].name_en, o, n))

	
	core.MY_PRINT_FUNC("Modified deform order for {} / {} = {:.1%} bones".format(
		len(modified_bones), len(pmx.bones), len(modified_bones) / len(pmx.bones)))

	# now actually apply the changes stored in deforms
	for d,v in enumerate(deforms):
		pmx.bones[d].deform_layer = v
	
	return pmx, True

def end(pmx, input_filename_pmx):
	# write out
	# output_filename_pmx = "%s_dispframe.pmx" % core.get_clean_basename(input_filename_pmx)
	output_filename_pmx = input_filename_pmx[0:-4] + "_bonedeform.pmx"
	output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	pmxlib.write_pmx(output_filename_pmx, pmx, moreinfo=True)
	return None

def main():
	showhelp()
	pmx, name = showprompt()
	pmx, is_changed = bonedeform_fix(pmx)
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
