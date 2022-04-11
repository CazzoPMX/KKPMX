# Nuthouse01 - 10/10/2020 - v5.03
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################


########################################
# bones are used when:
# 	other !used! bones use as parent, AKA has children
# 	other !used! bones use as link point
# 	other !used! bones use for "append" (partial parent)
# 	is IK
#	is the target of an IK bone
# 	connected to rigid bodies
# 	any vertex has nonzero weight for that bone

# read b.csv, v.csv, rb.csv, print results
#	output list of useless bones



# first, system imports
from typing import List, Tuple

# second, wrap custom imports with a try-except to catch it if files are missing
try:
	# these imports work if running from GUI
	from . import nuthouse01_core as core
	from . import nuthouse01_pmx_parser as pmxlib
	from . import nuthouse01_pmx_struct as pmxstruct
	from ._prune_unused_vertices import newval_from_range_map, delme_list_to_rangemap
except ImportError as eee:
	try:
		# these imports work if running from double-click on THIS script
		import nuthouse01_core as core
		import nuthouse01_pmx_parser as pmxlib
		import nuthouse01_pmx_struct as pmxstruct
		from _prune_unused_vertices import newval_from_range_map, delme_list_to_rangemap
	except ImportError as eee:
		print(eee.__class__.__name__, eee)
		print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
		print("...press ENTER to exit...")
		input()
		exit()
		core = pmxlib = pmxstruct = None
		newval_from_range_map = delme_list_to_rangemap = None


# when debug=True, disable the catchall try-except block. this means the full stack trace gets printed when it crashes,
# but if launched in a new window it exits immediately so you can't read it.
DEBUG = False


# when this is true, it also prints a list of the number of vertices controlled by each bone. not recommended.
PRINT_VERTICES_CONTROLLED_BY_EACH_BONE = False


# when this is true, list the number and names of each bone i am deleting
PRINT_FOUND_UNUSED_BONES = False


# these are common bones that are unused but should not be deleted
# glasses, dummy_L, dummy_R, view cnt, motherbone, edge adjust
BONES_TO_PROTECT = ["メガネ", "左ダミー", "右ダミー", "操作中心", "全ての親", "エッジ調整"]

helptext = '''====================
prune_unused_bones:
This file identifies and deletes all bones in a PMX model that are NOT being used.
A bone is USED if any of the following are true:
    any vertex has nonzero weight with that bone
    rigid bodies use it as an anchor
    other used bones use it as parent, AKA it has children
    other used bones use it as a visual link point
    other used bones use it for 'append' (inherit movement and/or rotation)
    it is an IK bone or a link in the IK chain of an IK bone
A bone is UNUSED if none of these conditions are met.
All unused bones can be safely removed without affecting the current function of the model.
The common bones "dummy_L","dummy_R","glasses" are exceptions: they are semistandard accessory attachment points so they will not be removed even if they otherwise fit the definition of "unused" bones.
'''

iotext = '''Inputs:  PMX file "[model].pmx"\nOutputs: PMX file "[model]_boneprune.pmx"
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
	
	
	
def insert_single_bone(pmx: pmxstruct.Pmx, newbone: pmxstruct.PmxBone, newindex: int):
	"""
	Wrapper function to make inserting bones simpler.
	(!) No existing bones should refer to this bone before it is inserted. (!) When constructing newbone, it should
	refer to already-existing bones by using their indices BEFORE this insert happens. (!) If you want to refer to
	bones that haven't yet been created, too bad, come back and modify it after all insertions are done.
	
	:param pmx: PMX object
	:param newbone: PMX Bone object to be inserted
	:param newindex: position to insert it
	"""
	if newindex > len(pmx.bones) or newindex < 0:
		raise ValueError("invalid index %d for inserting bone, current bonelist len= %d" % (newindex, len(pmx.bones)))
	elif newindex == len(pmx.bones):
		pmx.bones.append(newbone)
	else:
		# insert the bone at the new location
		pmx.bones.insert(newindex, newbone)
		# create the shiftmap for inserting things
		bone_shiftmap = ([newindex], [-1])
		# apply the shiftmap
		# this also changes any references inside newbone to refer to the correct indices after the insertion
		apply_bone_remapping(pmx, [], bone_shiftmap)
	return
	

def delete_multiple_bones(pmx: pmxstruct.Pmx, bone_dellist: List[int]):
	"""
	Wrapper function to make deleting bones simpler.
	
	:param pmx: PMX object
	:param bone_dellist: list of bone indices to delete
	"""
	# force it to be sorted, just to be safe
	bone_dellist2 = sorted(bone_dellist)
	# build the rangemap to determine how index references will be modified from this deletion
	bone_shiftmap = delme_list_to_rangemap(bone_dellist2)
	# acutally delete the bones
	for f in reversed(bone_dellist):
		pmx.bones.pop(f)
	# apply remapping scheme to all remaining bones
	apply_bone_remapping(pmx, bone_dellist2, bone_shiftmap)
	return



def identify_unused_bones(pmx: pmxstruct.Pmx, moreinfo: bool) -> List[int]:
	"""
	Process the PMX and return a list of all unused bone indicies in the model.
	1. get bones used by a rigidbody.
	2. get bones that have weight on at least 1 vertex.
	3. mark "exception" bones, done here so parents of exception bones are kept too.
	4. inheritance, aka "bones used by bones", recursively climb the tree & get all bones the "true" used bones depend on.
	5. tails or point-ats.
	6. invert used to get set of unused.

	:param pmx: PMX list-of-lists object
	:param moreinfo: print extra info for debug or whatever
	:return: list of bone indices that are not used
	"""
	# python set: no duplicates! .add(newbone), "in", .discard(delbone)
	# true_used_bones is set of BONE INDEXES
	true_used_bones = set()  # exception bones + rigidbody bones + vertex bones
	vertex_ct = {}  # how many vertexes does each bone control? sometimes useful info

	# first: bones used by a rigidbody
	for body in pmx.rigidbodies:
		true_used_bones.add(body.bone_idx)

	# second: bones used by a vertex i.e. has nonzero weight
	# any vertex that has nonzero weight for that bone
	for vert in pmx.verts:
		weighttype = vert.weighttype
		weights = vert.weight
		if weighttype==0:
			true_used_bones.add(weights[0])
			core.increment_occurance_dict(vertex_ct,weights[0])
		elif weighttype==1 or weighttype==3:
			# b1, b2, b1w
			# if b1w = 0, then skip b1
			if weights[2] != 0:
				true_used_bones.add(weights[0])
				core.increment_occurance_dict(vertex_ct,weights[0])
			# if b1w = 1, then skip b2
			if weights[2] != 1:
				true_used_bones.add(weights[1])
				core.increment_occurance_dict(vertex_ct,weights[1])
		elif weighttype==2 or weighttype==4:
			for i in range(4):
				if weights[i+4] != 0:
					true_used_bones.add(weights[i])
					core.increment_occurance_dict(vertex_ct, weights[i])
		
	# NOTE: some vertices/rigidbodies depend on "invalid" (-1) bones, clean that up here
	true_used_bones.discard(-1)
	
	# third: mark the "exception" bones as "used" if they are in the model
	for protect in BONES_TO_PROTECT:
		# get index from JP name
		i = core.my_list_search(pmx.bones, lambda x: x.name_jp == protect)
		if i is not None:
			true_used_bones.add(i)
	
	# build ik groups here
	# IKbone + chain + target are treated as a group... if any 1 is used, all of them are used. build those groups now.
	ik_groups = [] # list of sets
	for d,bone in enumerate(pmx.bones):
		if bone.has_ik:  # if ik enabled for this bone,
			ik_set = set()
			ik_set.add(d)  # this bone
			ik_set.add(bone.ik_target_idx)  # this bone's target
			for link in bone.ik_links:
				ik_set.add(link.idx)  # all this bone's IK links
			ik_groups.append(ik_set)
	
	# fourth: NEW APPROACH FOR SOLVING INHERITANCE: RECURSION!
	# for each bone that we know to be used, run UP the inheritance tree and collect everything that it depends on
	# recursion inputs: pmx bonelist, ik groups, set of already-known-used, and the bone to start from
	# bonelist is readonly, ik groups are readonly
	# set of already-known-used overlaps with set-being-built, probably just use one global ref to save time merging sets
	# standard way: input is set-of-already-known, return set-built-from-target, that requires merging results after each call tho
	# BUT each function level adds exactly 1 or 0 bones to the set, therefore can just modify the set that is being passed around
	
	def recursive_climb_inherit_tree(target: int, set_being_built):
		# implicitly inherits variables pmx, ik_groups from outer scope
		if target in set_being_built or target == -1:
			# stop condition: if this bone idx is already known to be used, i have already ran recursion from this node. don't do it again.
			# also abort if the target is -1 which means invalid bone
			return
		# if not already in the set, but recursion is being called on this, then this bone is a "parent" of a used bone and should be added.
		set_being_built.add(target)
		# now the parents of THIS bone are also used, so recurse into those.
		bb = pmx.bones[target]
		# acutal parent
		recursive_climb_inherit_tree(bb.parent_idx, set_being_built)
		# partial inherit: if partial rot or partial move, and ratio is nonzero and parent is valid
		if (bb.inherit_rot or bb.inherit_trans) and bb.inherit_ratio != 0 and bb.inherit_parent_idx != -1:
			recursive_climb_inherit_tree(bb.inherit_parent_idx, set_being_built)
		# IK groups: if in an IK group, recurse to all members of that IK group
		for group in ik_groups:
			if target in group:
				for ik_member in group:
					recursive_climb_inherit_tree(ik_member, set_being_built)
					
	parent_used_bones = set()  # true_used_bones + parents + point-at links
	# now that the recursive function is defined, actually invoke the function from every truly-used bone
	for tu in true_used_bones:
		recursive_climb_inherit_tree(tu, parent_used_bones)
	
	# fifth: "tail" or point-at links
	# propogate DOWN the inheritance tree exactly 1 level, no more.
	# also get all bones these tails depend on, it shouldn't depend on anything new but it theoretically can.
	final_used_bones = set()
	for bidx in parent_used_bones:
		b = pmx.bones[bidx]
		# if this bone has a tail,
		if b.tail_usebonelink:
			# add it and anything it depends on to the set.
			recursive_climb_inherit_tree(b.tail, final_used_bones)
	# now merge the two sets
	final_used_bones = final_used_bones.union(parent_used_bones)
	
	# sixth: assemble the final "unused" set by inverting
	# set of all bones, for inverting purposes
	all_bones_list = list(range(len(pmx.bones)))
	all_bones_set = set(all_bones_list)
	
	unused_bones = all_bones_set.difference(final_used_bones)
	unused_bones_list = sorted(list(unused_bones))
	
	# print neat stuff
	if moreinfo:
		if unused_bones_list:
			core.MY_PRINT_FUNC("Bones: total=%d, true_used=%d, parents=%d, tails=%d, unused=%d" %
							   (len(pmx.bones), len(true_used_bones), len(parent_used_bones)-len(true_used_bones),
								len(final_used_bones)-len(parent_used_bones), len(unused_bones_list)))
		# debug aid
		if PRINT_VERTICES_CONTROLLED_BY_EACH_BONE:
			core.MY_PRINT_FUNC("Number of vertices controlled by each bone:")
			for bp in all_bones_list:
				if bp in vertex_ct:
					core.MY_PRINT_FUNC("#: %d    ct: %d" % (bp, vertex_ct[bp]))
	
	return unused_bones_list
	

def apply_bone_remapping(pmx: pmxstruct.Pmx, bone_dellist: List[int], bone_shiftmap: Tuple[List[int],List[int]]):
	"""
	Given a list of bones to delete, delete them, and update the indices for all references to all remaining bones.
	PMX is modified in-place. Behavior is undefined if the dellist bones are still in use somewhere!
	References include: vertex weight, bone morph, display frame, rigidbody anchor, bone tail, bone partial inherit,
	bone IK target, bone IK link.
	
	:param pmx: PMX object
	:param bone_dellist: list of bone indices to delete
	:param bone_shiftmap: created by delme_list_to_rangemap() before calling
	"""
	
	core.print_progress_oneline(0 / 5)
	# VERTICES:
	# just remap the bones that have weight
	# any references to bones being deleted will definitely have 0 weight, and therefore it doesn't matter what they reference afterwards
	for d, vert in enumerate(pmx.verts):
		weighttype = vert.weighttype
		weights = vert.weight
		if weighttype == 0:
			# just remap, this cannot have 0 weight
			weights[0] = newval_from_range_map(weights[0], bone_shiftmap)
		elif weighttype == 1 or weighttype == 3:
			# b1, b2, b1w
			# if b1w == 0, zero out b1
			if weights[2] == 0:
				weights[0] = 0
			else:
				weights[0] = newval_from_range_map(weights[0], bone_shiftmap)
			# if b1w == 1, then b2w == 0 so zero out b2
			if weights[2] == 1:
				weights[1] = 0
			else:
				weights[1] = newval_from_range_map(weights[1], bone_shiftmap)
		elif weighttype == 2 or weighttype == 4:
			for i in range(4):
				# if weight == 0, then change its bone to 0. otherwise, remap
				if weights[i + 4] == 0:
					weights[i] = 0
				else:
					weights[i] = newval_from_range_map(weights[i], bone_shiftmap)
	# done with verts
	
	core.print_progress_oneline(1 / 5)
	# MORPHS:
	for d, morph in enumerate(pmx.morphs):
		# only operate on bone morphs
		if morph.morphtype != 2: continue
		# first, it is plausible that bone morphs could reference otherwise unused bones, so I should check for and delete those
		i = 0
		while i < len(morph.items):
			# if the bone being manipulated is in the list of bones being deleted, delete it here too. otherwise remap.
			if core.binary_search_isin(morph.items[i].bone_idx, bone_dellist):
				morph.items.pop(i)
			else:
				morph.items[i].bone_idx = newval_from_range_map(morph.items[i].bone_idx, bone_shiftmap)
				i += 1
	# done with morphs
	
	core.print_progress_oneline(2 / 5)
	# DISPLAY FRAMES
	for d, frame in enumerate(pmx.frames):
		i = 0
		while i < len(frame.items):
			item = frame.items[i]
			# if this item is a morph, skip it
			if item[0]:
				i += 1
			else:
				# if this is one of the bones being deleted, delete it here too. otherwise remap.
				if core.binary_search_isin(item[1], bone_dellist):
					frame.items.pop(i)
				else:
					item[1] = newval_from_range_map(item[1], bone_shiftmap)
					i += 1
	# done with frames
	
	core.print_progress_oneline(3 / 5)
	# RIGIDBODY
	for d, body in enumerate(pmx.rigidbodies):
		# only remap, no possibility of one of these bones being deleted
		body.bone_idx = newval_from_range_map(body.bone_idx, bone_shiftmap)
	# done with bodies
	
	core.print_progress_oneline(4 / 5)
	# BONES: point-at target, true parent, external parent, partial append, ik stuff
	for d, bone in enumerate(pmx.bones):
		# point-at link:
		if bone.tail_usebonelink:
			if core.binary_search_isin(bone.tail, bone_dellist):
				# if pointing at a bone that will be deleted, instead change to offset with offset 0,0,0
				bone.tail_usebonelink = False
				bone.tail = [0, 0, 0]
			else:
				# otherwise, remap
				bone.tail = newval_from_range_map(bone.tail, bone_shiftmap)
		# other 4 categories only need remapping
		# true parent:
		bone.parent_idx = newval_from_range_map(bone.parent_idx, bone_shiftmap)
		# partial append:
		if (bone.inherit_rot or bone.inherit_trans) and bone.inherit_parent_idx != -1:
			if core.binary_search_isin(bone.inherit_parent_idx, bone_dellist):
				# if a bone is getting partial append from a bone getting deleted, break that relationship
				# shouldn't be possible but whatever i'll support the case
				bone.inherit_rot = False
				bone.inherit_trans = False
				bone.inherit_parent_idx = -1
			else:
				bone.inherit_parent_idx = newval_from_range_map(bone.inherit_parent_idx, bone_shiftmap)
		# ik stuff:
		if bone.has_ik:
			bone.ik_target_idx = newval_from_range_map(bone.ik_target_idx, bone_shiftmap)
			for link in bone.ik_links:
				link.idx = newval_from_range_map(link.idx, bone_shiftmap)
	# done with bones
	return


def prune_unused_bones(pmx: pmxstruct.Pmx, moreinfo=False):
	# first build the list of bones to delete
	unused_list = identify_unused_bones(pmx, moreinfo)
	
	if not unused_list:
		core.MY_PRINT_FUNC("No changes are required")
		return pmx, False
	
	if moreinfo:
		# convert the list of individual bones to remove into a list of ranges
		delme_rangemap = delme_list_to_rangemap(unused_list)
		core.MY_PRINT_FUNC("Detected %d unused bones arranged in %d contiguous blocks" % (len(unused_list), len(delme_rangemap[0])))
		for d in unused_list:
			core.MY_PRINT_FUNC("bone #{:<3} JP='{}' / EN='{}'".format(
				d, pmx.bones[d].name_jp, pmx.bones[d].name_en))
	
	num_bones_before = len(pmx.bones)
	delete_multiple_bones(pmx, unused_list)
	
	# print("Done deleting unused bones")
	core.MY_PRINT_FUNC("Found and deleted {} / {} = {:.1%} unused bones".format(
		len(unused_list), num_bones_before, len(unused_list) / num_bones_before))
	
	return pmx, True


def end(pmx, input_filename_pmx):
	# write out
	# output_filename_pmx = "%s_boneprune.pmx" % core.get_clean_basename(input_filename_pmx)
	output_filename_pmx = input_filename_pmx[0:-4] + "_boneprune.pmx"
	output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	pmxlib.write_pmx(output_filename_pmx, pmx, moreinfo=True)
	return None


def main():
	showhelp()
	pmx, name = showprompt()
	pmx, is_changed = prune_unused_bones(pmx, PRINT_FOUND_UNUSED_BONES)
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
			core.MY_PRINT_FUNC(ee.__class__.__name__, ee)
			core.pause_and_quit("ERROR: something truly strange and unexpected has occurred, sorry, good luck figuring out what tho")
