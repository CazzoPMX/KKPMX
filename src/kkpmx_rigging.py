# Cazoo - 2021-05-15
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
import json
import re
import os
import math
import copy
from typing import List, Union

import nuthouse01_core as core
import nuthouse01_pmx_struct as pmxstruct
import morph_scale
import kkpmx_utils as util
from kkpmx_utils import find_bone, find_mat, find_disp, find_morph, find_rigid
from kkpmx_utils import Vector3, Matrix

# Local debug
DEBUG = util.DEBUG or False
global_state = { }                   # Store argument info
OPT__HAIR = "hair"

def run(pmx, input_filename_pmx, moreinfo=False, write_model=True, _opt={}):
	"""
Rigging Helpers for KK.
- Adjust Body Physics (best guess attempt for butt, adds Torso, Shoulders, and Neck to aid hair collision)
- Transform Skirt Grid from Cubicle to Rectangles (and other things to attempt more fluid movements)
- Untangle merged Materials
-  - Since KKExport loves to merge vertex meshes if they are bound to bones sharing the same name, this also corrects the bone weights
-  - Works by mapping materials with '[:AccId:] XX' in their comment to a bone chain starting with 'ca_slotXX', with XX being a number (and equal in both).
- Rig Hair Joints
-  - Sometimes needs minor optimizations, but also allows a bit of customization (by changing the Rigid Type of the chain segments)
-  - The "normal" rigging can also be reproduced by selecting a linked bone range, and opening [Edit]>[Bone]>[Create Rigid/Linked Joint]
-  - Disclaimer: Might not work in 100% of cases since there is no enforced bone naming convention for plugins (e.g. using 'root' as start)

[Options] '_opt':
- "mode":
-  - 0 -- main run-down
-  - 1 -- ônly rig Hair
-  - 2 -- rig a list of bones together
"""
	### Add some kind of list chooser & ask for int[steps] to execute
	import kkpmx_core as kkcore
	global_state["moreinfo"] = moreinfo or DEBUG
	modes = _opt.get("mode", -1)
	choices = [("Regular Fixes", 0), ("Only rig_hair_joints",1), ("Rig Bone Array", 2)]
	modes = util.ask_choices("Choose Mode", choices, modes)
	if modes == 1:
		rig_hair_joints(pmx)
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", "Modified Rigging (Hair only)")
	if modes == 0:
		adjust_body_physics(pmx)
		transform_skirt(pmx)
		split_merged_materials(pmx, None)
		rig_hair_joints(pmx)
		rig_other_stuff(pmx)
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", "Modified Rigging")
	#######
	print("This will connect a consecutive list of bones and rig them together.")
	print("To skip an accidental input, just type the same number for both steps.")
	def is_valid(value): return util.is_number(value) and int(value) > -1 and int(value) < len(pmx.bones)
	arr_log = ["Modified Rigging (Bone chains)"]
	while(True):
		start = core.MY_GENERAL_INPUT_FUNC(is_valid, "First Bone" + f"?: ")
		end   = core.MY_GENERAL_INPUT_FUNC(is_valid, "Last Bone"  + f"?: ")
		if start != end:
			arr = list(range(int(start), int(end)+1))
			arr_log.append("> " + json.dumps(arr))
			patch_bone_array(pmx, None, arr, pmx.bones[arr[0]].name_jp, 16)
		if util.ask_yes_no("-- Add another one","y") == False: break
	return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", arr_log)
	
###############
### Riggers ###
###############

def adjust_body_physics(pmx):
	mask = 65534 # == [1] is 2^16-1

	## Butt collision
	if find_bone(pmx, "cf_j_waist02", False):
		posX = pmx.bones[find_bone(pmx, "cf_j_waist02")].pos[0]
		posY = pmx.bones[find_bone(pmx, "cf_d_thigh01_L")].pos[1]
		posZ = pmx.bones[find_bone(pmx, "cf_s_siri_L")].pos[2]
		width1 = pmx.bones[find_bone(pmx, "左足")].pos[0]
		width2 = pmx.bones[find_bone(pmx, "右足")].pos[0]
		width  = (abs(width2 - width1) / 1.7693461) ## Distance on default hip
		
		rigid = find_rigid(pmx, "下半身")
		pmx.rigidbodies[rigid].pos = [posX, posY, posZ]
		pmx.rigidbodies[rigid].size[0] = 0.85 * width
		pmx.rigidbodies[rigid].nocollide_mask = mask
		pmx.rigidbodies[rigid].phys_move_damp = 0.999
		pmx.rigidbodies[rigid].phys_rot_damp = 0.999
		pmx.rigidbodies[rigid].phys_repel = 0
		pmx.rigidbodies[rigid].phys_friction = 0.5
	## Hair collision
	if find_rigid(pmx, "RB_upperbody", False) in [-1,None]:
		
		def absarr(arr): return [abs(a) for a in arr]
		
		common = {
			"nocollide_mask": mask, "shape": 1, #"group": 1,
			"phys_move_damp": 0.9999, "phys_rot_damp": 0.9999
			}
		
		bn_shou_L = pmx.bones[find_bone(pmx, "cf_d_shoulder_L")]
		bn_shou_R = pmx.bones[find_bone(pmx, "cf_d_shoulder_R")]
		
		## Torso
		maxX = pmx.bones[find_bone(pmx, "cf_s_shoulder02_L")].pos[0]
		
		tie = find_bone(pmx, "cf_j_spinesk_01",False)
		if tie not in [-1,None]: maxY = pmx.bones[tie].pos[1]
		else:
			up   = bn_shou_R.pos[1]
			down = pmx.bones[find_bone(pmx, "cf_s_bnip01_R")].pos[1]
			maxY = (up + down)/2
		
		maxZ = pmx.bones[find_bone(pmx, "cf_d_sk_03_00")].pos[2]
		
		minX = pmx.bones[find_bone(pmx, "cf_s_shoulder02_R")].pos[0]
		minY = pmx.bones[find_bone(pmx, "下半身")].pos[1]
		minZ = pmx.bones[find_bone(pmx, "cf_s_bnip01_R")].pos[2]
		
		pos = [0, ((maxY+minY)/2), 0]
		#print(f"[TR]size = [({maxX}-{minX}), ({maxY}-{minY}), ({maxZ}-{minZ})]")
		size = absarr([(maxX-minX)/2, (maxY-minY)/2, (maxZ-minZ)/2])
		
		add_rigid(pmx, name_jp="RB_upperbody", pos=pos, size=size, bone_idx=find_bone(pmx, "上半身2"), **common)
		boxY = maxY
		####
		## Left shoulder
		maxX = pmx.bones[find_bone(pmx, "cf_d_arm01_L")].pos[0]
		maxY = bn_shou_L.pos[1] + (bn_shou_L.pos[1] - boxY)
		maxZ = pmx.bones[find_bone(pmx, "cf_s_elbo_L")].pos[2]
		
		minX = bn_shou_L.pos[0]
		minY = boxY
		minZ = pmx.bones[find_bone(pmx, "cf_s_elboback_L")].pos[2]
		
		pos = [((maxX+minX)/2), bn_shou_L.pos[1], bn_shou_L.pos[2]]
		#print(f"[SL]size = [({maxX}-{minX}), ({maxY}-{minY}), ({maxZ}-{minZ})]")
		size = absarr([(maxX-minX)/2, (maxY-minY)/1.5, (maxZ-minZ)/1.5])
		
		add_rigid(pmx, name_jp="RB_shoulder_L", pos=pos, size=size, bone_idx=find_bone(pmx, "左肩"), **common)
		neck_minX = minX
		
		####
		## Right shoulder
		maxX = pmx.bones[find_bone(pmx, "cf_d_arm01_R")].pos[0]
		maxY = bn_shou_R.pos[1] + (bn_shou_R.pos[1] - boxY)
		maxZ = pmx.bones[find_bone(pmx, "cf_s_elbo_R")].pos[2]
		
		minX = bn_shou_R.pos[0]
		minY = boxY
		minZ = pmx.bones[find_bone(pmx, "cf_s_elboback_R")].pos[2]
		
		pos = [((maxX+minX)/2), bn_shou_R.pos[1], bn_shou_R.pos[2]]
		#print(f"[SR]size = [({maxX}-{minX}), ({maxY}-{minY}), ({maxZ}-{minZ})]")
		size = absarr([(maxX-minX)/2, (maxY-minY)/1.5, (maxZ-minZ)/1.5])
		
		add_rigid(pmx, name_jp="RB_shoulder_R", pos=pos, size=size, bone_idx=find_bone(pmx, "右肩"), **common)
		neck_maxX = minX
		
		####
		## Neck
		maxX = get_bone_or_default(pmx, "cf_J_CheekLow_s_R", 0, neck_maxX)
		maxY = pmx.bones[find_bone(pmx, "頭")].pos[1]
		maxZ = maxZ
		
		minX = get_bone_or_default(pmx, "cf_J_CheekLow_s_L", 0, neck_minX)
		minY = minY
		minZ = minZ
		
		pos = [((maxX+minX)/2), (maxY+minY)/2, (maxZ+minZ)/2]
		#print(f"[NK]size = [({maxX}-{minX}), ({maxY}-{minY}), ({maxZ}-{minZ})]")
		size = absarr([(maxX-minX)/2, (maxY-minY)/2, (maxZ-minZ)/1.5])
		
		add_rigid(pmx, name_jp="RB_neck", pos=pos, size=size, bone_idx=find_bone(pmx, "首"), **common)

def transform_skirt(pmx):
	## Skirt is segmented into 7 stripes with 5 segments each
	##-- Their joints are rotated such that Z always faces away from the body
	## -- [Front]: 7,0,1
	## -- [Right]:   2
	## -- [Back]:  3,4,5
	## -- [Left]:    6
	##-- Allow [side] Joints extended movement between these groups
	##-- Rotation of [side]:
	#-- [-Z] = away from body
	#-- [+X] = To the left (roughly previous segment)
	
	for rigid in pmx.rigidbodies:
		## Change width of all but [05] to XX (start at 0.6)
		if not re.match(r"cf_j_sk", rigid.name_jp): continue
		m = re.match(r"cf_j_sk_(\d+)_(\d+)", rigid.name_jp)
		if int(m[2]) == 5: continue
		## Change mode to 1 & set depth to 0.02
		rigid.shape = 1
		rigid.size[0] = 0.6
		rigid.size[2] = 0.02
		#-- Make front / back pieces a bit wider
		if int(m[1]) in [0,4]: rigid.size[0] = 0.7
	
	## Move Side Joints to sides (X + width / 2, Y + height / 2)
	skirt = []
	for joint in pmx.joints:
		if not re.match(r"cf_j_sk", joint.name_jp): continue
		skirt.append(joint)
		if re.match(r"cf_j_sk_\d\d_05", joint.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_\d\d\[side\]", joint.name_jp):
			rigid = pmx.rigidbodies[joint.rb1_idx]
			## X pos requires using triangulation, maybe later
			joint.pos[1] = rigid.pos[1] + rigid.size[1] / 2
			joint.pos[2] = rigid.pos[2] + rigid.size[2] / 2

	#### Make skirt move more like a fluid
	for joint in skirt:
		m = re.match(r"cf_j_sk_(\d+)_(\d+)(\[side\])?", joint.name_jp)
		main = int(m[1])
		sub = int(m[2])
		side = not (m[3] is None)
		corner = main in [1, 2, 5, 6]
		## Adjust main joints
		if not side: continue
		## Adjust side joints
		if   sub == 0: continue ## Ignore Base
		elif sub == 4: (joint.movemin[0], joint.movemax[0]) = (-10, 10)
		elif sub == 5: (joint.movemin[0], joint.movemax[0]) = ( +1,  0)
		##-- Adjust only for corner
		if not corner: continue
		if   sub == 1: (joint.movemin[0], joint.movemax[0]) = ( -5,  5)
		elif sub == 2: (joint.movemin[0], joint.movemax[0]) = (-10, 10)
		elif sub == 3: (joint.movemin[0], joint.movemax[0]) = (-15, 15)
		elif sub == 4: (joint.movemin[0], joint.movemax[0]) = (-20, 20)
		
		## Issue: Still too much collision with body during hectic movements
##########
	pass# To keep trailing comments inside

# --[Fix materials that exist multiple times]-- #

def rig_hair_joints(pmx): #--- Find merged / split hair chains --> apply Rigging to them
	### Add a Head Rigid for the Hair to anchor onto -- return if none
	head = find_bone(pmx, "a_n_headflont", True)
	if head == -1: return
	head_bone = pmx.bones[head]
	## Also return if we already added the whole head stuff
	if find_rigid(pmx, "a_n_headfront", False) != -1: return
	head_body = add_rigid(pmx, name_jp="a_n_headfront", pos=head_bone.pos, bone_idx=head, size=[1,1,1], 
			phys_move_damp=1.0, phys_rot_damp=1.0)
			
	## Get reference point for discard
	try: limit = pmx.bones[find_bone(pmx, "胸親", False)].pos[1]
	except: limit = 0.0

	### The major hair addons use "root" as first anchor for vertices
	__root_Name = "N_move" ## "root" is gone ....
	bones = [i for (i,b) in enumerate(pmx.bones) if b.name_jp.startswith(__root_Name)]
	#### Other things
	# 02: All_Root.001 ++ SCENE_ROOT.001 + ... x3 + AS01_J_kami(RB,B,LB)_01..05, 05_end
	
	grp = 3
	
	_patch_bone_array = lambda x,n: patch_bone_array(pmx, head_body, x, n, grp)
	if len(bones) == 0: print("No hair chain found to rig.")
	else: global_state[OPT__HAIR] = True
	for bone in bones:
		## Ignore the groups not anchored to the head
		if pmx.bones[bone].pos[1] < limit: continue
		
		## Get name from containing slot
		b = bone
		while (b and not pmx.bones[b].name_jp.startswith("ca_slot")): b = pmx.bones[b].parent_idx
		name = pmx.bones[b].name_jp
		## Collect bone chain
		arr = get_children_map(pmx, bone, returnIdx=False, add_first=False)
		#--- Rewrote to work with arbitary root bone
		root_arr = [x for x in arr.keys() if x.startswith(__root_Name)]
		if not any(root_arr): print(f"{bone} has weird bones({list(arr.keys())}), skipping"); continue
		
		root_arr0 = arr[root_arr[0]] ## root_arr[list(root_arr.keys())[0]]
		
		##################
		#-- Regular Joint Handling
		## Check if any bone name of the [slot tree] starts with "joint"
		root_arr1 = [x for x in root_arr0 if pmx.bones[x].name_jp.startswith("joint")]
		#print(root_arr1)
		if any(root_arr1):
			## Get parent of first bone
			first_parent = pmx.bones[root_arr1[0]].parent_idx
			## Descend "joints" for "yure_hair_h_Ro..."
			if (pmx.bones[root_arr1[0]].name_jp == "joints"):
				#first_parent = root_arr1[0]
				continue # nvm, all trash
			## Get a full Tree map of these bones
			all_child = get_children_map(pmx, root_arr0, returnIdx=False, add_first=True)
			## Reduce to the chains whose first bone has the above as parent
			child_arr = [all_child[pmx.bones[x].name_jp] for x in root_arr0 if pmx.bones[x].parent_idx == first_parent]
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		##################
		#-- AS01 Handling
		## Check if any bone name of the [slot tree] starts with "AS01_N_kami"
		root_arr2 = [x for x in root_arr0 if pmx.bones[x].name_jp.startswith("AS01_N_kami")]
		if any(root_arr2):
			## Reduce to its children
			root_arr = get_children_map(pmx, root_arr2[0], returnIdx=False, add_first=False)
			## Descend once more (from "AS01_N_kami" onto first "AS01_J_kami")
			arr = root_arr[list(root_arr.keys())[0]]
			## Get a full Tree map of these bones
			all_child = get_children_map(pmx, arr, returnIdx=False, add_first=True)
			## Reduce to the chains whose first bone has "AS01_J_kami" as parent
			child_arr = [all_child[pmx.bones[x].name_jp] for x in arr if pmx.bones[x].parent_idx == arr[0]]
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		##################
		#-- p_cf_hair && cf_N_J_ Handling
		## Check if any bone name of the [slot tree] starts with "AS01_N_kami"
		root_arr3 = [x for x in root_arr0 if pmx.bones[x].name_jp.startswith("cf_N_J_")]
		if any(root_arr3):
			continue ## Already pre-rigged ? --> Or simply add [Group 16] to pre-rigged ones
			## Reduce to its children
			root_arr = get_children_map(pmx, root_arr3[0], returnIdx=False, add_first=False)
			## Descend once more (from "cf_N_J_" onto first "cf_J_..._top")
			arr = root_arr[list(root_arr.keys())[0]]
			## Get a full Tree map of these bones
			all_child = get_children_map(pmx, arr, returnIdx=False, add_first=True)
			## Reduce to the chains whose first bone has "AS01_J_kami" as parent
			child_arr = [all_child[pmx.bones[x].name_jp] for x in arr if pmx.bones[x].parent_idx == arr[0]]
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		#######################
		arr = root_arr0
		
		#if pmx.bones[arr[0]].name_jp.startswith("root"): del arr[0]
		if pmx.bones[arr[0]].name_jp.startswith("All_Root"): continue
		if len(arr) < 2: continue
		if pmx.bones[arr[-1]].name_jp.startswith("o_"): del arr[-1]
		
		#first = arr[__root_Name][0];arr = [first] + arr[pmx.bones[first].name_jp]
		
		##
		_patch_bone_array(arr, name)

def rig_other_stuff(pmx):
	## Get reference point for discard
	try: limit = pmx.bones[find_bone(pmx, "胸親", False)].pos[1]
	except: limit = 0.0

	### The major hair addons use "root" as first anchor for vertices
	__root_Name = "N_move" ## "root" is gone ....
	bones = [i for (i,b) in enumerate(pmx.bones) if b.name_jp.startswith(__root_Name)]
	#### Other things
	_patch_bone_array = lambda x,n: patch_bone_array(pmx, None, x, n, 16)
	
	for bone in bones:
		## Ignore the hair groups
		if pmx.bones[bone].pos[1] > limit: continue
		
		## Get name from containing slot
		b = bone
		while (b and not pmx.bones[b].name_jp.startswith("ca_slot")): b = pmx.bones[b].parent_idx
		name = pmx.bones[b].name_jp
		## Collect bone chain
		arr = get_children_map(pmx, bone, returnIdx=False, add_first=False)
		#--- Rewrote to work with arbitary root bone
		root_arr = [x for x in arr.keys() if x.startswith(__root_Name)]
		if not any(root_arr): print(f"{bone} has weird bones({list(arr.keys())}), skipping"); continue
		
		root_arr0 = arr[root_arr[0]] ## root_arr[list(root_arr.keys())[0]]
		
		##################
		#-- Regular Joint Handling
		## Check if any bone name of the [slot tree] starts with "joint"
		root_arr1 = [x for x in root_arr0 if pmx.bones[x].name_jp.startswith("joint")]
		#print(root_arr1)
		if any(root_arr1):
			## Get parent of first bone
			first_parent = pmx.bones[root_arr1[0]].parent_idx
			## Descend "joints" for "yure_hair_h_Ro..."
			if (pmx.bones[root_arr1[0]].name_jp == "joints"):
				#first_parent = root_arr1[0]
				continue # nvm, all trash
			## Get a full Tree map of these bones
			all_child = get_children_map(pmx, root_arr0, returnIdx=False, add_first=True)
			## Reduce to the chains whose first bone has the above as parent
			child_arr = [all_child[pmx.bones[x].name_jp] for x in root_arr0 if pmx.bones[x].parent_idx == first_parent]
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		#######################
		arr = root_arr0
		
		#if pmx.bones[arr[0]].name_jp.startswith("root"): del arr[0]
		if pmx.bones[arr[0]].name_jp.startswith("All_Root"): continue
		if len(arr) < 2: continue
		if pmx.bones[arr[-1]].name_jp.startswith("o_"): del arr[-1]
		
		#first = arr[__root_Name][0];arr = [first] + arr[pmx.bones[first].name_jp]
		
		##
		_patch_bone_array(arr, name)


########
## ca_slot (a_n_headside)
## -- N_move >> root
## -- -- joint1-1...1-6
## -- -- joint2-1...2-6
## -- N_hairback126 >> cf_...., ....
######
## ca_slot >> nc
## -- N_move
## -- -- joint1...6
## -- -- o_...
######
## :: YY = Ftop, F_01..02, 02_en \\ 
## ca_slot
## -- N_move >> All_Root.001 >> SCENE_ROOT.001 >> AS01_null_kamiB.001
## -- -- AS01_N_kami(X1).001 >> AS01_J_kami(X1) >> AS01_J_kami(YY)
## -- -- AS01_null_kami(X1).001 >> AS01_null_kamiK >> (renders)
## -- N_hairback06 >> cf_hair_b_02_(01..13)
######
## ca_slot >> N_move >> Armature.003 >> f_08R
## -- N_hairfront08 >> (renders:AS01_O_kami_...)
## -- All_Root >> SCENE_ROOT >> AS01_null_kamiF >> AS01_N_kamiFtop >> AS01_J_kami(YY)
######

##--- Hook a chain of RigidBodies to a static Body and anchor it to [head_body]
def patch_bone_array(pmx, head_body, arr, name, grp):
	if True: ## To keep the History aligned
		bind_bones(pmx, arr, True)
		#grp = 16 # the nocollide_mask given as argument to [add_rigid] has to be changed when using lower numbers
		
		mask = 65535 - (1 << grp - 1)
		
		## Create a root
		root = add_rigid(pmx, name_jp=name+"_r", bone_idx=arr[0], shape=0, size=[0.2, 0, 0], pos = pmx.bones[arr[0]].pos,
			group=grp-1, nocollide_mask=mask, phys_move_damp=1, phys_rot_damp=1)
		
		## Create Physics chain
		num_bodies = len(pmx.rigidbodies)
		num_joints = len(pmx.joints)
		AddBodyChainWithJoints(pmx, arr, 1, 0.0, True, name=name, group=grp)
		new_bodies = len(pmx.rigidbodies) - num_bodies
		new_joints = len(pmx.joints) - num_joints
		
		## Connect with head rigid
		if head_body is None or head_body < 0:
			del pmx.joints[num_joints]
		else:
			joint = pmx.joints[num_joints]
			joint.rb1_idx = head_body #root
			joint.rb2_idx = num_bodies
			joint.movemin = [ 0.0, 0.0, 0.0]
			joint.movemax = [ 0.0, 0.0, 0.0]
			joint.rotmin  = [ 0.0, 0.0, 0.0]
			joint.rotmax  = [ 0.0, 0.0, 0.0]
		
		
		########### If using shorter chains
		## Make first body static
		body = pmx.rigidbodies[num_bodies]
		body.phys_move_damp = 0.999
		body.phys_rot_damp  = 0.99
		## 
		if new_bodies > 1:
			### MMD needs two fixated rigids or one central anchored by multiple
			pmx.rigidbodies[num_bodies+1].phys_mode = 0
			pmx.rigidbodies[-1].size[0] = 0.1
			## Reduce height by the size of a Joint, relative to the radiius
			# --- Otherwise the ends overlap too much
			for bodyX in pmx.rigidbodies[num_bodies:]:
				#msg = f"Size: {bodyX.size[1]}"
				bodyX.size[1] -= (bodyX.size[0]*10) * 0.2 ## 0.1 are exactly 0.2
				#print(msg + f" -> {bodyX.size[1]}")
##########
	pass# To keep trailing comments inside

def split_merged_materials(pmx, input_filename_pmx): #-- Find and split merged Material chains (full chain match)
	"""
	
	-- Fixes issue --
	Vertices of multiple materials weighted to the same bone because using the same name
	
	-- Customization option --
	This process can be controlled by the existence (or lack) of the term "[:AccId:] XX" with XX matching the "ca_slotXX" bone (== KK slot).
	After running [<insert mode>], all Acc materials will contain such a tag in their comments.
	By removing the tag from certain materials, they stay glued to the original (e.g. move together)
	Important: This must be run before [nuthouse01 cleanup], as that removes all unused bones (== all whose children have no vertices connected)
	"""
	verbose = global_state.get("moreinfo", False)
	#### Get parental map of all bones
	par_map = get_parent_map(pmx, range(len(pmx.bones)))
	slots = [i for (i,b) in enumerate(pmx.bones) if b.name_jp.startswith("ca_slot")]
	slot_map = {}    ## dict of { "ca_slot": [slot, list of children] }
	slot_names = {}  ## dict of { "ca_slot": "combined,name,of,children" }
	## Build decendant map
	for slot in slots:
		children = [k for k in par_map.keys() if slot in par_map[k]]
		slot_name = pmx.bones[slot].name_jp
		if DEBUG: print(f"{slot_name}:[{slot}]: {children}")
		slot_map[slot_name] = [slot] + children
		slot_names[slot_name] = ",".join([pmx.bones[x].name_jp for x in children])
	
	## Find all where all names are equal
	name_map   = {}
	for slot in slot_map:
		name = slot_names[slot]
		if name in name_map: name_map[name].append(slot)
		else: name_map[name] = [slot]
	
	if verbose: print("----")
	
	###-- Test with more than two cases of one such thing
	if verbose:
		print("-- Found these Material clusters -- () = total length of name chain")
		[print(f"{name[:50]:50}({len(name):3}): {name_map[name]}") for name in name_map]

	######
	#### Clean up those materials that bind to EOL bones.
	fixed = []
	tabu = {}
	names = [b.name_jp for b in pmx.bones]
	#Find [end of cloth bones]
	#>[A]	try out "KK_Colliders_cf_j_root" // 100%, but only before cleanup
	#>[B]	try out "cf_s_waist01" (stays after cleanup) -- look for any subsequent "an_*" bones
	#>	Either the "max+1" bone directly references max, and is also the last bone.
	#>	Or it references something far before
	last = find_bone(pmx, "KK_Colliders_cf_j_root", False)
	if last in [-1,None]:#>> This branch is still untested
		## This means the model is already cleaned up. This one exists in both.
		last = find_bone(pmx, "cf_s_waist01", False)
		if last not in [-1,None]:
			tmp = [x for x in slots if x > last]
			# if there are any slots (an_*), get the last of it
			if len(tmp) > 0:
				tmp = get_children_map(pmx, tmp, True)[-1]
			##>> Avoid taking one of those bones we try to fix
				if tmp[-1]+1 == len(pmx.bones): last = tmp[-2]
				else: last = tmp[-1]
		else: last = len(pmx.bones) - 2
	last += 1
	## If we have that bone, only allow bones whose parent is smaller than that
	#>	Although could be causing issues for duplicate accs on [waist]...
	#foreach bone: ## id, name, parent
	for (i,bone) in enumerate(pmx.bones[last:]):
		idx = last + i
		name = bone.name_jp
		parent = bone.parent_idx
		if parent >= last or parent == 2: continue
	#	## if not in tabu: register + continue
		if name not in tabu:
			tabu[name] = [parent]
			#print(f"Set {name} with pid:{parent}, continue")
			continue
	#	## else get id & name of parent
		root = tabu[name][0]; pid = tabu[name][-1]
		#print(f"Found duplicate {name}, testing {root} != {parent}")
		if root != parent: continue
		pname = pmx.bones[pid].name_jp
	#	## find first bone beyond pid named pname
		try: _next = names.index(pname, pid+1)
		except: continue
	#	## Set correct bone
		bone.parent_idx = _next
		tabu[name].append(_next)
		#fixed.append([key for key in slot_map.keys() if idx in slot_map[key]][0])
	##--
	if verbose: print("----")
	######
	#### Fix all other materials (those which are weighted to the same bones)
	seen = set()
	bone_map = { b.name_jp: i for (i,b) in enumerate(pmx.bones) if not (b.name_jp in seen or seen.add(b.name_jp)) }
	#[3] for each slotted material
	for slot in slot_map:
		if slot in fixed: continue ## Avoids unneccessary warnings
		idx_map = {}
	#-[1] for each bone, get its name
		for bone in slot_map[slot]:
			name = pmx.bones[bone].name_jp
	#> [2] if list[name] != bone_idx: add to bone_map as { list[name] : bone_idx }
			if bone_map[name] != bone: idx_map[bone_map[name]] = bone
	#-[2] if len(bone_map) > 0: call [reweight] with that (instead of src,dst)
		if len(idx_map) > 0:
			reweight_bones(pmx, None, idx_map, int(re.search(r"ca_slot(\d+)", slot)[1]), False)
	
	if input_filename_pmx is not None:
		import kkpmx_core as kkcore
		kkcore.end(pmx, input_filename_pmx, "_unmerged", "Split up merged materials")
##########
	pass

def split_manually(pmx, key, values): #-- Loop within cluster and pull apart
	"""
	Validates if first list in @values is part of the weights of 1st key.
	Then stores that and uses it to split the correct weights.
	
	@param {pmx}     PMX instance
	@param {key}     List[str] of 'ca_slot' names
	@param {values}  List[List[int]] of associated bone lists (incl. 'ca_slot' bone)
	"""
	first_chain = None
	chain_matched = False
	for idx in range(len(key)):
		name = key[idx]  ### Get name of containing slot
		arr = values[idx][1:] ## Collect bone chain
		##
		if first_chain is None: first_chain = copy.deepcopy(arr)
		bind_bones(pmx, arr, True)
		if not reweight_bones(pmx, first_chain, arr, int(re.search(r"ca_slot(\d+)", name)[1]), False):
			if not chain_matched: first_chain = None
		else: chain_matched = True

########
## Riggers Util
########

def reweight_bones(pmx, src, dst, slot, is_hair=True):
	"""
	Attempts to reassign all vertices weighted to @src that belong to @slot to those in @dst.
	The vertices are taken from the material whose comment contains "[:AccId:] XX" with XX = @slot.
	
	@param {pmx}      PMX instance
	@param {src}      List[int] of boneIndices to replace -[or]- None
	@param {dst}      List[int] of boneIndices to insert  -[or]- a boneMap of { @src : @dst }
	@param {slot}     int -- KK Material Slot to take the Vertices from
	@param {is_hair}  bool -- True to require all of @src, False for at least one.
	
	@return :: True if it was successful, False if not
	"""
	import kkpmx_core as kkcore
	if src is not None:
		bone_map = { src[i]: dst[min(i, len(dst)-1)] for i in range(len(src)) }
	else: bone_map = dst
	
	## List because some materials can have multiple parts
	mat_idx_list = []
	
	for (i,m) in enumerate(pmx.materials):
		if re.search("\[:AccId:\] (\d+)", m.comment):
			tmp = int(re.search("\[:AccId:\] (\d+)", m.comment)[1])
			if slot == tmp:
				mat_idx_list.append(i)
	if len(mat_idx_list) == 0:
		print(f"Unable to find matching material for Slot {slot}")
		return False

	for mat_idx in mat_idx_list:
		faces = kkcore.from_material_get_faces(pmx, mat_idx, returnIdx=False)
		vertices = kkcore.from_faces_get_vertices(pmx, faces, returnIdx=True)
		bones = kkcore.from_vertices_get_bones(pmx, vertices, returnIdx=True)
		## Require full match or not ?
		if is_hair:
			for idx in list(bone_map.keys())[:len(dst)]:
				if idx not in bones: return False
		else:
			flag = False
			for idx in list(bone_map.keys())[:len(dst)]:
				if idx in bones: flag = True
			if flag == False: return False
		
		def replaceBone(target): return bone_map.get(target, target)
		for idx in vertices:
			vert = pmx.verts[idx]
			if vert.weighttype == 0:
				vert.weight[0] = replaceBone(vert.weight[0])
			elif vert.weighttype == 1:
				vert.weight[0] = replaceBone(vert.weight[0])
				vert.weight[1] = replaceBone(vert.weight[1])
			elif vert.weighttype == 2:
				vert.weight[0] = replaceBone(vert.weight[0])
				vert.weight[1] = replaceBone(vert.weight[1])
				vert.weight[2] = replaceBone(vert.weight[2])
				vert.weight[3] = replaceBone(vert.weight[3])
			else:
				raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))
	return True

######-- Emulate rigging similar to how it [PMXView] does

##--- Adds a linked Chain of RigidBodies and their Joints
def AddBodyChainWithJoints(pmx, boneIndex: List[int], mode: int, r: float, uvFlag: bool, name, group):
	body_num: int = len(pmx.rigidbodies)
	AddBaseBody(pmx, boneIndex, mode, r, uvFlag, name, group)
	added_bodies: int = len(pmx.rigidbodies) - body_num
	if (added_bodies <= 0): return
	
	dictionary = { body.bone_idx: i for (i, body) in enumerate(pmx.rigidbodies) if body.bone_idx in boneIndex }
	# Set first body to [Static] to avoid fluid
	pmx.rigidbodies[dictionary[boneIndex[0]]].phys_mode = 0
	
	dictionary2 = {}
	for bone_idx in boneIndex:
		# Don't add more Joints than bodies
		if len(dictionary) == len(dictionary2): break
		# Don't add Joint on last bone
		#if boneIndex[-1] == bone_idx: break

		pmxBone = pmx.bones[bone_idx]
		if (pmxBone != None and (not uvFlag or pmxBone.has_visible)):
			pmxJoint = pmx.joints[add_joint(pmx)]
			pmxJoint.name_jp = name + ":" + pmxBone.name_jp
			pmxJoint.pos = pmxBone.pos
			
			num3: Vector3 = Vector3(10, 5, 10)
			##--- Regen from PMXExport does [-10 to 10, -5 to 5, -10 to 10] for Ponytail
			pmxJoint.rotmax = num3.ToList()   #[  0.0,   0.0,   0.0] #Vector3(num3, num3, num3).ToList();
			pmxJoint.rotmin = (-num3).ToList()#[  0.0,   0.0,   0.0] #-pmxJoint.rotmax;
			dictionary2[bone_idx] = len(pmx.joints) - 1

	### @todo: [?] add hidden bone with [0, 0, -1] as pointer
	for key in dictionary.keys():
		pmxBone2 = pmx.bones[key]
		if pmxBone2.parent_idx not in boneIndex: continue
		#if pmxBone2.tail_usebonelink:
		#	if pmxBone2.tail not in boneIndex: continue
		pmxJoint2 = pmx.joints[dictionary2[key]]
		pmxJoint2.rb1_idx = dictionary[pmxBone2.parent_idx]
		pmxJoint2.rb2_idx = dictionary[key]
		pmxJoint2.rot = pmx.rigidbodies[dictionary[key]].rot

##-- Adds the RigidBodies
def AddBaseBody(pmx, boneIndices: List[int], mode: int, r: float, uvFlag: bool, name, group):
	if group in range(1,17):
		if   group == 16: mask = 2**15 - 1
		else:
			#mask = 0 << group - 1 ## All bigger than 'group'
			#mask = 1 << group - 1 ## All except 'group'
			mask = 65535 - (1 << group - 1) ## group
		
		group = group - 1 ## Because actually [0 - 15]
	else:
		group = 0
		mask = 0 ## == All
	
	for idx in boneIndices:
		bone = pmx.bones[idx]
		#print(f"------------ {idx}: {bone.name_jp}")
		if uvFlag and not bone.has_visible: continue
		pos = Vector3.FromList(bone.pos)
		### flag
		# [A]: bone has to_bone && to_bone is part of chain
		# [B]: bone has no to_bone && bone_link is not [0,0,0]
		###
		is_link = bone.tail_usebonelink
		flag = (is_link and bone.tail in boneIndices) or (not is_link and str(bone.tail) != str([0.0, 0.0, 0.0]))

		if flag:
			num3: float = 0.0
			zero = Vector3.Zero()
			if bone.tail_usebonelink:
				vector = Vector3.FromList(pmx.bones[bone.tail].pos) - pos
				num3 = vector.Length()
				zero = pos + 0.5 * vector
			else:
				bone_link = Vector3.FromList(bone.tail)
				num3 = bone_link.Length()
				zero = pos + 0.5 * bone_link
				#print("No BoneLink, using offset instead")
				#continue
			body = pmx.rigidbodies[add_rigid(pmx)]
			body.shape = 2 # Capsule
			x: float = r
			if (r <= 0.0): x = num3 * 0.2
			body.size = Vector3(x, num3, 0.0).ToList()
			body.pos = zero.ToList()
			m: Matrix = GetPoseMatrix_Bone(pmx, idx)
			body.rot = MatrixToEuler_ZXY(m).ToDegree().ToList()
		else:
			body = pmx.rigidbodies[add_rigid(pmx)]
			body.shape = 0 # Sphere
			x2: float = r
			if (r <= 0.0): x2 = 0.2
			body.size = [x2, 0.0, 0.0]
			body.pos = pos.ToList()
		####--
		body.name_jp = name + ":" + bone.name_jp
		body.bone_idx = idx
		body.phys_mode = mode
		body.phys_move_damp = 0.9
		body.phys_rot_damp = 0.99
		body.group = group
		body.nocollide_mask = mask

def GetPoseMatrix_Bone(pmx, boneIndex: int, upY: bool = True):
	pmxBone = pmx.bones[boneIndex]
	
	zero: Vector3 = Vector3.Zero()
	if (not pmxBone.tail_usebonelink):
		zero = Vector3.FromList(pmxBone.tail)
	else:
		zero = Vector3.FromList(pmx.bones[pmxBone.tail].pos) - Vector3.FromList(pmxBone.pos)
	zero.Normalize()
	if (upY and zero.Y < 0.0): zero = -zero

	vector: Vector3 = zero

	left: Vector3 = Vector3.Cross(vector, Vector3.UnitZ())
	left.Normalize()

	vector2: Vector3 = Vector3.Cross(left, vector)
	vector2.Normalize()

	position: Vector3 = Vector3.FromList(pmxBone.pos)

	identity: Matrix = Matrix.Identity()
	identity.M11 = left.X
	identity.M12 = left.Y
	identity.M13 = left.Z
	identity.M21 = vector.X
	identity.M22 = vector.Y
	identity.M23 = vector.Z
	identity.M31 = vector2.X
	identity.M32 = vector2.Y
	identity.M33 = vector2.Z
	identity.M41 = position.X
	identity.M42 = position.Y
	identity.M43 = position.Z
	return identity;

def MatrixToEuler_ZXY(m: Matrix, pmx = None):
	import math
	#print(str(m))
	zero: Vector3 = Vector3.Zero()
	zero.X = 0.0 - float(math.asin(m.M32))
	if (zero.X == (float(math.pi) / 2.0)) or (zero.X == (-float(math.pi) / 2.0)):
		zero.Y = float(math.atan2(0.0 - m.M13, m.M11))
	else:
		zero.Y = float(math.atan2(m.M31, m.M33))
		zero.Z = float(math.asin(m.M12 / float(math.cos(zero.X))))
		if (m.M22 < 0.0): zero.Z = math.pi - zero.Z
	return zero

########
## Util of Util
########

def spread_pos(arr):
	pos = {}
	pos.X = arr.pos[0]
	pos.Y = arr.pos[1]
	pos.Z = arr.pos[2]
	return pos

def bind_bones(pmx, _arr, last_link=False):
	from copy import deepcopy
	arr = deepcopy(_arr)
	while len(arr) > 1:
		parent = arr[0]#find_bone(pmx, arr[0], False)
		child  = arr[1]#find_bone(pmx, arr[1], False)
		if parent is not None and child is not None:
			pmx.bones[parent].tail_usebonelink = True
			pmx.bones[parent].tail = child
		arr.pop(0)
	if last_link:
		pmx.bones[arr[-1]].tail_usebonelink = False
		pmx.bones[arr[-1]].tail = [0, 0, -0.1]

def change_phy_mode(pmx, _arr, mode):
	if (find_rigid(pmx, _arr[0]) is None): return
	for name in _arr:
		body_idx = find_rigid(pmx, name, False)
		if body_idx is not None: pmx.rigidbodies[body_idx].phys_mode = mode

def get_bone_or_default(pmx, name_jp, idx, default):
	tmp = find_bone(pmx, name_jp, False)
	if tmp not in [-1,None]:
		return pmx.bones[tmp].pos[idx]
	return default

#----

def print_map(_mapObj):
	print("--->")
	for x in _mapObj.keys(): print(f"{x}: {_mapObj[x]}")
	print("<---")

def get_parent_map(pmx, bones):
	"""
	Arranges @bones into a dict of the form { @bone: [ancestors in @bones] }
	"""
	boneMap = { -1: [], 0: [] }
	for bone in sorted(bones):
		p = bone
		while p not in boneMap: p = pmx.bones[p].parent_idx
		if p not in [0,-1]: boneMap[bone] = boneMap[p] + [p]
		else:               boneMap[bone] = []
	del boneMap[-1]
	if 0 not in bones: del boneMap[0]
	return boneMap

def get_delta_map(pmx1, pmx2, boneMap, relative=True):
	vecDict = {}
	for bone in boneMap.keys():
		vector2 = Vector3.FromList(pmx2.bones[bone].pos)
		target  = Vector3.FromList(pmx1.bones[bone].pos)
		## Reduce delta in relation to the already added delta from parent bones, accumulative
		delta = (target - vector2)
		if relative:
			for idx in boneMap[bone]: delta -= vecDict.get(idx, Vector3.Zero)
		vecDict[bone] = delta
	return vecDict

def get_children_map(pmx, bones, returnIdx=False, add_first=True):
	"""
	Arranges @bones into a dict of the form { "name": [list of children] }
	
	@bones:     Can be int or List[int]
	@returnIdx: <dict.keys> will consist of the boneIndices instead
	@add_first: Adds @bone.index as first entry in each <dict.value>
	"""
	if type(bones) is not list: bones = [bones]
	par_map = get_parent_map(pmx, range(len(pmx.bones)))
	bone_map = {}    ## dict of { "name": [bone, list of children] }
	for bone in bones:
		bone_key = pmx.bones[bone].name_jp
		children = [k for k in par_map.keys() if bone in par_map[k]]
		if returnIdx: bone_key = bone
		if add_first: children = [bone] + children
		bone_map[bone_key] = children
	return bone_map

#### Calculate nocollide_mask
# Given a group X in [1 to 16]
#>	remove X only           : 2^(X-1)         # == Keep all except X
#>	remove all lower  groups: 2^(X-1) - 1
#>	remove all higher groups: sum([2^(i-1) for i in range(16, X, -1)])
#>	remove all but X        : sum([2^(i-1) for i in range(16, X, -1)], 2^(X-1) - 1) == higher(X) + lower(X)
#>	>	## For 14: Sum 2^14 + 2^15 + 2^13 - 1
#>	int(math.pow(2, 15))


## /(\w+): (List\[\w+\]|\w+), *:: (.+)/  -- /\1: \2 = \3,/

def add_bone(pmx,
			 name_jp: str = "New Bone1",
			 name_en: str = "",
			 pos: List[float] = [0,0,0],
			 parent_idx: int = -1,
			 deform_layer: int = 0,
			 deform_after_phys: bool = False,
			 has_rotate: bool = True,
			 has_translate: bool = False,
			 has_visible: bool = True,
			 has_enabled: bool = True,
			 has_ik: bool = False,
			 tail_usebonelink: bool = False,
			 tail: Union[int, List[float]] = [0,0,0],
			 # NOTE: either int or list of 3 float, but always exists, never None
			 inherit_rot: bool = False,
			 inherit_trans: bool = False,
			 has_fixedaxis: bool = False,
			 has_localaxis: bool = False,
			 has_externalparent: bool = False,
			 # optional/conditional
			 inherit_parent_idx: int=None,
			 inherit_ratio: float=None,
			 fixedaxis: List[float]=None,
			 localaxis_x: List[float]=None,
			 localaxis_z: List[float]=None,
			 externalparent: int=None,
			 ik_target_idx: int=None,
			 ik_numloops: int=None,
			 ik_angle: float=None,
			 ik_links=None
			 ):
	args = locals()
	del args["pmx"]
	if name_en == "": args["name_en"] = name_jp
	pmx.bones.append(pmxstruct.PmxBone(**args))
	return len(pmx.bones) - 1

def add_rigid(pmx,
			 name_jp: str = "New RigidBody1",
			 name_en: str = "",
			 bone_idx: int = 0,
			 pos: List[float] = [0,0,0],
			 rot: List[float] = [0,0,0],
			 size: List[float] = [2,2,2],
			 shape: int = 0,
			 # Group 1-16 == 0-15
			 group: int = 0,
			 # 16: all but 5 \\ 1: all but 1 \\ 65534(max-1): 1
			 nocollide_mask: int = 65535, ## inverted bit_mask
			 phys_mode: int = 0,
			 phys_mass: float=1.0,
			 phys_move_damp: float=0.5,
			 phys_rot_damp: float=0.5,
			 phys_repel: float=0.0,
			 phys_friction: float=0.5,
			 ):
	""" Create a new RigidBody with default values """
	args = locals()
	del args["pmx"]
	if name_en == "": args["name_en"] = name_jp
	#if bone_idx == 0: print(f"{name_jp} is missing Bone!")
	pmx.rigidbodies.append(pmxstruct.PmxRigidBody(**args))
	return len(pmx.rigidbodies) - 1

def add_joint(pmx,
			 name_jp: str = "New Joint1",
			 name_en: str = "",
			 jointtype: int = 0,
			 rb1_idx: int = 0,
			 rb2_idx: int = 0, 
			 pos: List[float] = [0,0,0],
			 rot: List[float] = [0,0,0],
			 movemin: List[float] = [0,0,0],
			 movemax: List[float] = [0,0,0],
			 movespring: List[float] = [0,0,0],
			 rotmin: List[float] = [0,0,0],
			 rotmax: List[float] = [0,0,0],
			 rotspring: List[float] = [0,0,0],
			 ):
	""" Create a new Joint with default values """
	args = locals()
	del args["pmx"]
	if name_en == "": args["name_en"] = name_jp
	#if (rb1_idx == 0): print(f"{name_jp} is missing Rigid 1!")
	#if (rb2_idx == 0): print(f"{name_jp} is missing Rigid 2!")
	pmx.joints.append(pmxstruct.PmxJoint(**args))
	return len(pmx.joints) - 1

###########
if __name__ == '__main__': util.main_starter(run)