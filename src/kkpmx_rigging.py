# Cazoo - 2023-04-06
# This code is free to use, but I cannot be held responsible for damages that it may or may not cause.
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
local_state = { }                   # Store argument info
OPT__HAIR = "hair"
OPT__NODUPES = "no_dupes"
RBD__CLEANUP = "RBD__CLEANUP"
OPT__TAIL    = "tails"
OPT__LOGS    = "extraLogs" ## Allows methods to add extra log_line
def _verbose(): return local_state.get("moreinfo", False)

##--- Collision Masks :: =/	(GRP_)|(merge_collision_groups)|(nocollide_mask)	/
GRP_BODY    = 1   ## [E] Default Body >> Adding more here
GRP_ARMS    = 2   ## [S] Arms -- Same as Body but ignore Skirt
GRP_DEFHAIR = 3   ## [E] Default Hair
GRP_HAIRACC = 3   ## [S] Adding Accessories attached to a_n_headfront
GRP_SKIRT   = 4   ## [E] Skirt >> Extending here
GRP_CHESACC = 5 
GRP_CHEST_A = 8   ## [E] Chest Mass
GRP_WING    = 12  ## Own
GRP_TAIL    = 13  ## Own
GRP_CHEST_B = 14  ## [E] Chest Rigids
GRP_WAIST   = 15  ## [S] Other Waist Accessories: Conflict free with Skirt & Tail
GRP_BODYACC = 16  ## [S] Adding all other Accessories


def run(pmx, input_filename_pmx, moreinfo=False, write_model=True, _opt={}):
	"""
Rigging Helpers for KK.
- Adjust Body Physics (best guess attempt for butt, adds Torso, Shoulders, and Neck to aid hair collision)
- Transform Skirt Grid from Cubicle to Rectangles (and other things to attempt more fluid movements)
- Untangle merged Materials
-  - Since KKExport loves to merge vertex meshes if they are bound to bones sharing the same name, this also corrects the bone weights
-  - Works by mapping materials with '[:AccId:] XX' in their comment to a bone chain starting with 'ca_slotXX', with XX being a number (and equal in both).
- Add Physics to Accessories
-  - Sometimes needs minor optimizations, but also allows a bit of customization (by changing the Rigid Type of the chain segments)
-  - The "normal" rigging can also be reproduced by selecting a linked bone range, and opening [Edit]>[Bone]>[Create Rigid/Linked Joint]
-  - Disclaimer: Might not work in 100% of cases since there is no enforced bone naming convention for plugins (e.g. using 'root' as start)
-  - Will cleanup certain Physics again if their corresponding bones aren't weighted to anything anymore because of 'Prune invisible faces'.

[Issues]:
- In some cases, the Skirt Rigids named 'cf_j_sk12' point into the wrong direction. Simply negate the [RotX] value on the 5 segments.
- If the skirt was exported without [Side] Joints, it will be modified to avoid messy collisions with lower body rigids
- Rigid-Chains will only be added once -- To redo them, please delete the respective Bodies + Joints manually.

[Add note about that there will be missing entries for Slots if things have been merged at the start]

[Options] '_opt':
- "mode":
-  - 0 -- Main mode
-  - 1 -- Reduce chest bounce
-  - 2 -- Rig a list of bones together (== fix unrecognized chain starts)
-  - 3 -- Cut morph chains (== fix unrecognized chain ends)
-  - 4 -- Repair skin issues (Rebind some bones after Semi-Standard-Bones are added)
-  - 5 -- Cleanup ALL free Physics (unused Bones, RigidBodies, and Joints)

[Input]
- Mode 2: Two bone indices to chain together all inbetween and add RigidBodies + Joints to. Loops until stopped.
- Mode 3: A comma-separated list of RigidBodies Indices
-  - For each Index n, separate it from n+1 and turn them into an End / Start Segment, respectively.

[Logging]: Logs which mode has been executed -- when using '2' or '3', it also stores the respective input indices.

[Output]: PMX file '[modelname]_rigged.pmx'
"""
	### Add some kind of list chooser & ask for int[steps] to execute
	import kkpmx_core as kkcore
	local_state["moreinfo"] = moreinfo or DEBUG
	modes = _opt.get("mode", -1)
	all_yes = _opt.get("all_yes", False)
	local_state[OPT__NODUPES] = False
	
	CH_REGULAR = 0; CH_BOUNCE = 1; CH_RIG_ARRAY = 2; CH_SPLIT_ARRAY = 3; CH_RUN_MODE = 4; CH_REPAIR = 5; CH_CLEANUP = 6;
	
	choices = [
		("Regular Fixes", CH_REGULAR), ("Reduce Chest bounce",CH_BOUNCE), ("Rig Bone Array", CH_RIG_ARRAY), ("Split Chains", CH_SPLIT_ARRAY),
		("Repair some bones", CH_REPAIR), ("Cleanup free rigids", CH_CLEANUP)
	]#, ("Choose mode", CH_RUN_MODE)]
	modes = util.ask_choices("Choose Mode", choices, modes)
	if modes == CH_SPLIT_ARRAY:
		arr_log = ["Modified Rigging (Split Chains)"]
		arr_log += [split_rigid_chain(pmx)]
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", arr_log)
	if modes == CH_BOUNCE:
		#rig_hair_joints(pmx)
		#return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", "Modified Rigging (Hair only)")
		#transform_skirt(pmx)
		#fix_skirt_rigs(pmx)
		#rig_rough_detangle(pmx)
		msg = "\n> ".join([""] + adjust_chest_physics(pmx))
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", "Modified Rigging (Chest only)" + msg)
	if modes == CH_REGULAR:
		arr_log = ["Modified Rigging"]
		local_state[RBD__CLEANUP] = {}
		adjust_body_physics(pmx) ## ++ repair_some_bones, add_body_colliders
		transform_skirt(pmx)
		split_merged_materials(pmx, None)
		rig_hair_joints(pmx)
		rig_other_stuff(pmx)
		rig_rough_detangle(pmx)
		#merge_bone_weights(pmx)
		handle_special_materials(pmx)
		
		flag = len(local_state[RBD__CLEANUP].keys()) != 0 ## Only ask if there is anything to do (full scan only in solo mode)
		if flag and (util.is_auto() or all_yes or util.ask_yes_no("Delete unbound physics", 'y')):
			_out = {}
			cleanup_free_bodies(pmx, _out)
			if "log_line" in _out: arr_log += _out["log_line"]
		util.unify_names(pmx.rigidbodies)
		util.unify_names(pmx.joints)
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", arr_log)
	if modes == CH_REPAIR:
		arr_log = ["Repaired some bones (after Semi-Standard)"]
		repair_some_bones(pmx)
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", arr_log)
	if modes == CH_RUN_MODE:
		pass
	if modes == CH_CLEANUP:
		cleanup_free_things(pmx)
		arr_log = ["Cleaned up unused Physics"]
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", arr_log)
	#######
	print("This will connect a consecutive list of bones and rig them together.")
	print("To skip an accidental input, just type the same number for both steps.")
	print("Start also accepts:")
	print("-- A pair of numbers: 123, 123")
	print("-- Any JSON-Array:    [123, 123] or [[123, 123], [123, 123]]")
	print("- If an entry contains exactly two numbers, they define a range to generate a chain with.")
	print("- Otherwise the provided indices will be chained together in the order they are given.")
	print("-  (in that case there is no bone index validation and it will fail when not found)")
	print("- If the array has a sufficient length, it will be parsed to detect individual chains.")
	print("- If this fails, you will be asked if the [Detangle] detection should be called at the end.")
	def is_valid_bulk(value):
		if is_valid(value): return True
		if util.is_csv_number(value): return len(value.split(',')) == 2
		return util.is_csv_array(value)
	def is_valid(value): return util.is_number(value) and int(value) > -1 and int(value) < len(pmx.bones)
	
	all_arr = []
	# TODO: Ask for a prefix somewhere here -- else it might get ugly (also check that this prefix isn't already used somewhere)
	#--- TODO: Print a warning if the prefix already exists (just adds them unconditionally again)
	# TODO(Think): Think about keeping a Chain start as [orange] if the parent is not green either
	# TODO(Fix): Seems to loose Chain(both idk are 0) on a Joint if previous segment is a non-consecutive bone
	# TODO: Figure out how what to do with the final bone-Link -- Unconditional Z=-0.1 seems wrong
	#	either continue parent or keep at 0 0 0
	# TODO: Add option that aligns the X-Axis with the body center (see ex__Finana_Honkai)
	# TODO: -- Make a "paired" flag that mirrors POS ROT etc accordingly (usually already the case except for minor offsets)
	# TODO: For non-head chains, use the appropriate "a_n_*" bone as Anchor
	#	--  >> Skip the [N_move] bone, and remove the bone link from [a_n_*] again at the end
	#	--	>> Provides the required dual root as [a_n_* ++ ca_slot], allowing the whole chain to move freely
	def looper(start, end, log=True, all_arr=[]):
		if start < end:
			arr = list(range(int(start), int(end)+1))
			all_arr += arr
			if log: arr_log.append("> " + json.dumps(arr))
			patch_bone_array(pmx, None, arr, pmx.bones[arr[0]].name_jp, 16, False)
		else: print("> End must be bigger than start")
	arr_log = ["Modified Rigging (Bone chains)"]
	while(True):
		#try:
		start = core.MY_GENERAL_INPUT_FUNC(is_valid_bulk, "First Bone (or Pair or JSON-Array)" + f"?: ")
		if util.is_number(start): looper(start, core.MY_GENERAL_INPUT_FUNC(is_valid, "Last Bone"  + f"?: "), True, all_arr)
		else:
			if not start.startswith('[['):
				if "-" in start: start = re.sub("-", ",", start)
				if not start.startswith('['): start = f"[[{start}]]" ## Wrap flat pairs
				else: start = f"[{start}]" ## Wrap lists without enclosing bracket
			arr_log.append(">>> " + json.dumps(json.loads(start)))
			for x in json.loads(start):
				if len(x) < 2: continue
				if len(x) == 2: looper(x[0], x[1], False, all_arr)
				else:
					all_arr += x
					patch_bone_array(pmx, None, x, pmx.bones[x[0]].name_jp, 16, False)
			print("> Done")
			#[looper(x[0], x[-1]) for x in json.loads(start)]
			#arr = start.split(','); looper(arr[0], arr[1])
		#except Exception as ex: print(ex)
		if util.ask_yes_no("-- Add another one","y") == False: break
	if len(arr_log) > 1:
		if util.ask_yes_no("-- Call detangle() to try cutting clusters","y"):
			print(all_arr)
			rig_rough_detangle(pmx, all_arr)
	return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", arr_log)

###############
### Riggers ###
###############

## [Step 01]
def adjust_body_physics(pmx):
	printStage("Adjust Body Physics")
	mask = 65535 # == [1] is 2^16-1
	
	if find_bone(pmx, "左胸操作", False) != -1:
		## -- Make Chest ignore Chest Acc & Hairs
		bodies = { "x": [] }
		def tmp(name):
			idx = find_rigid(pmx, name, False)
			if idx != -1: bodies["x"].append(pmx.rigidbodies[idx])
		tmp("左胸操作");     tmp("右胸操作")
		tmp("左AH1");       tmp("右AH1")
		tmp("左AH2");       tmp("右AH2")
		tmp("左胸操作接続");  tmp("右胸操作接続")
		tmp("左胸操作衝突");  tmp("右胸操作衝突")
		adjust_collision_groups(GRP_CHEST_B, bodies["x"])
		
		## Fix Joints (WAY LESS BOUNCY)
		# 左胸操作調整用, 右胸操作調整用 --> 200 200 200 100 100 100 -- Maybe fine adjust the movements to side and slight bounce
		def fixSpring(name):
			idx = util.find_joint(pmx, name, False)
			if idx != -1:
				j = pmx.joints[idx]
				# Move: Left/Right, Up/Down, Back/Forward
				j.movmin = [-0.001, -0.001, 0]
				j.movmax = [ 0.001,  0.003, 0]
				# Rotation: Up/Down, Left/Right, Rotate
				j.rotmin = [-20, -10, 0]
				j.rotmax = [ 20,  10, 0]
				j.movespring = [5000, 800, 200] # 0 20 0
				j.rotspring  = [2500, 500, 100] # 100 100 100
		fixSpring("左胸操作調整用")
		fixSpring("右胸操作調整用")

	## Butt collision
	decider = find_bone(pmx, "cf_j_waist02", False) != -1
	#-- Sanity check to not do it again because code block is not idempotent.
	try: decider = decider and pmx.rigidbodies[find_rigid(pmx, "下半身")].size[0] == 1
	except: decider = False
	if decider:
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
	
	## Fix existing Sphere / Capsule Colliders
	if find_rigid(pmx, "cf_hit_spine01", False) != -1:
		# cf_hit_spine01 -- Center of Torso
		#[Arms] cf_hit_arm_L, cf_hit_wrist_L, cf_hit_arm_R, cf_hit_wrist_R
		pmx.rigidbodies[find_rigid(pmx, "cf_hit_arm_L")].rot[2]   = 90
		pmx.rigidbodies[find_rigid(pmx, "cf_hit_wrist_L")].rot[2] = 90
		pmx.rigidbodies[find_rigid(pmx, "cf_hit_arm_R")].rot[2]   = 90
		pmx.rigidbodies[find_rigid(pmx, "cf_hit_wrist_R")].rot[2] = 90
		# cf_hit_spine03 -- Between Shoulders
		# cf_hit_berry -- ??
		# cf_hit_waist_L -- Below Center of Torso [to] Pelvis
		#[Legs] cf_hit_thigh02_L, cf_hit_leg01_L, cf_hit_thigh02_R, cf_hit_leg01_R
		# cf_hit_waist02
		#[Bust] cf_hit_bust02_L, cf_hit_bust02_R    --- Shake colliders
		#[Butt] cf_hit_siri_L, cf_hit_siri_R        --- Shake colliders
		#[Thigh] cf_hit_thigh01_L, cf_hit_thigh01_R --- Shake colliders
	
	repair_some_bones(pmx)
	add_body_colliders(pmx, mask)

def add_body_colliders(pmx, mask): ## -- Try to find some use for the other cf_hit_arm_L.. bones
	## Hair collision
	if find_rigid(pmx, "RB_upperbody", False) == -1:
		
		def absarr(arr): return [abs(a) for a in arr]
		
		common = {
			"nocollide_mask": mask, "shape": 1, #"group": 1,
			"phys_move_damp": 0.9999, "phys_rot_damp": 0.9999
			}
		commonPill = {
			"nocollide_mask": mask, "shape": 2, #"group": 1,
			"phys_move_damp": 0.9999, "phys_rot_damp": 0.9999
			}
		commonSph = {
			"nocollide_mask": mask, "shape": 0, #"group": 1,
			"phys_move_damp": 0.9999, "phys_rot_damp": 0.9999
			}
		
		bn_shou_L = pmx.bones[find_bone(pmx, "cf_d_shoulder_L")]
		bn_shou_R = pmx.bones[find_bone(pmx, "cf_d_shoulder_R")]
		
		## Torso -- Find out why it didn't work with [finished one]
		maxX = pmx.bones[find_bone(pmx, "左肩Solo")].pos[0]
		
		tie = find_bone(pmx, "cf_j_spinesk_01", False)
		if tie != -1: maxY = pmx.bones[tie].pos[1]
		else:
			up   = bn_shou_R.pos[1]
			down = pmx.bones[find_bone(pmx, "cf_s_bnip01_R")].pos[1]
			maxY = (up + down)/2
		
		maxZ = pmx.bones[find_bone(pmx, "cf_d_sk_03_00")].pos[2]
		
		minX = pmx.bones[find_bone(pmx, "右肩Solo")].pos[0]
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
		rot  = [0, 0, 90]
		
		add_rigid(pmx, name_jp="RB_shoulder_L", pos=pos, size=size, bone_idx=find_bone(pmx, "左肩"), rot=rot, **commonPill)
		neck_minX = minX
		
		####
		## Left arm
		#-- between cf_d_arm01_L & 左ひじ \\ [rad]: cf_s_elboback_L - cf_s_elbo_L (out)
		rIn  = pmx.bones[find_bone(pmx, "cf_s_elboback_L")].pos[2]
		rOut = pmx.bones[find_bone(pmx, "cf_s_elbo_L")].pos[2]
		lenIn = pmx.bones[find_bone(pmx, "左肩Solo")].pos[0]
		lenOut = pmx.bones[find_bone(pmx, "cf_s_forearm01_L")].pos[0]
		
		pos = pmx.bones[find_bone(pmx, "cf_hit_arm_L")].pos
		rot  = [0, 0, 90]
		
		rad = ((pos[2] - rIn) + (rOut - pos[2])) / 2
		height = (lenOut - lenIn)
		size = absarr([rad, height, 0])
		
		add_rigid(pmx, name_jp="RB_arm_L", pos=pos, size=size, rot=rot, bone_idx=find_bone(pmx, "cf_hit_arm_L"), **commonPill)
		
		####
		## Right arm
		rIn  = pmx.bones[find_bone(pmx, "cf_s_elboback_R")].pos[2]
		rOut = pmx.bones[find_bone(pmx, "cf_s_elbo_R")].pos[2]
		lenIn = pmx.bones[find_bone(pmx, "右肩Solo")].pos[0]
		lenOut  = pmx.bones[find_bone(pmx, "cf_s_forearm01_R")].pos[0]
		
		pos = pmx.bones[find_bone(pmx, "cf_hit_arm_R")].pos
		rot  = [0, 0, -90]
		
		rad = ((pos[2] - rIn) + (rOut - pos[2])) / 2
		height = (lenIn - lenOut)
		size = absarr([rad, height, 0])
		
		add_rigid(pmx, name_jp="RB_arm_R", pos=pos, size=size, rot=rot, bone_idx=find_bone(pmx, "cf_hit_arm_R"), **commonPill)
		
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
		rot = [0, 0, 90]
		
		sizeSh = size
		posSh = pos
		
		add_rigid(pmx, name_jp="RB_shoulder_R", pos=pos, size=size, bone_idx=find_bone(pmx, "右肩"), rot=rot, **commonPill)
		neck_maxX = minX
		
		####
		## Neck -- reuses values from [Right shoulder]
		maxX = get_bone_or_default(pmx, "cf_J_CheekLow_s_R", 0, neck_maxX)
		maxY = pmx.bones[find_bone(pmx, "頭")].pos[1]
		maxZ = maxZ
		
		minX = get_bone_or_default(pmx, "cf_J_CheekLow_s_L", 0, neck_minX)
		minY = minY
		minZ = minZ
		
		pos = [((maxX+minX)/2), (maxY+minY)/2, (maxZ+minZ)/2]
		#print(f"[NK]size = [({maxX}-{minX}), ({maxY}-{minY}), ({maxZ}-{minZ})]")
		size = absarr([(maxX-minX)/2, (maxY-minY)/2, (maxZ-minZ)/1.5])
		sizeNeck = size
		
		add_rigid(pmx, name_jp="RB_neck", pos=pos, size=size, bone_idx=find_bone(pmx, "首"), **commonPill)

		####
		## Full shoulder
		
		pos = [0, posSh[1], 0]
		size = [sizeSh[0], sizeSh[1]*2 + sizeNeck[0]*3, sizeSh[2]]
		rot = [0, 0, 90]
		add_rigid(pmx, name_jp="RB_shoulders", pos=pos, size=size, rot=rot, bone_idx=find_bone(pmx, "首"), **commonPill)
		
		####
		## Waist
		# X == 0  \\  Y == Lowerbody w/e  \\  # Z == Legs
		# X == 0  \\  Y == 0  \\  Z == 90
		# Pill \\ Root = (Y-Bone)
		# height(== rotated width) == left of left leg --> right of right leg
		# radius(== rotated height) == Touch RB_upperbody (if in cube form)
		
		#pos = [0, posSh[1], 0]
		#size = [sizeSh[0], sizeSh[1]*2 + sizeNeck[0]*3, sizeSh[2]]
		#rot = [0, 0, 90]
		#add_rigid(pmx, name_jp="RB_shoulders", pos=pos, size=size, rot=rot, bone_idx=find_bone(pmx, "首"), **commonPill)
		
		############
		pass

def repair_some_bones(pmx):
	## in kkpmx_core
	#-- Bind Fingertips to fingers
	#-- Patch weird eyesight: cf_J_Eye_rz_L
	#-- Provide convenient grab
	#-- Patch Knees: cf_d_kneeF_L, cf_d_kneeF_R, cf_s_kneeB_L, cf_s_kneeB_R
	#-- Move Ankle IK upwards to match standard
	
	from _prune_unused_bones import insert_single_bone
	from kkpmx_utils import Vector3
	
	def fb(s): return find_bone(pmx, s, False)
	def adjust_bone(s, fnc):
		_idx = fb(s)
		if _idx != -1: fnc(pmx.bones[_idx])
	
	###--- Add [Semi-Standard-Bones] "Arm Twist" and "Wrist Twist" to avoid having to fix it afterwards
	def insert_twist_bone(_idx, nameJP, nameEN, parent, child):
		if _idx == -1: return
		bone = pmx.bones[_idx]
		elbowRot = add_bone(pmx, _solo=True)
		elbowRot.name_jp = nameJP
		_idx2 = find_bone(pmx, elbowRot.name_jp, False)
		if _idx2 != -1:
			#elbowRot = pmx.bones[_idx2]
			#elbowRot.parent_idx = _idx
			return _idx2
		# Adjust Child.Position.Z based on [checkElbowPosOffset] on ArmTwist (== new Bone has different Z)
		# -- Remove again before leaving Scope
		boneChi = pmx.bones[child]
		posPar = Vector3.FromList(pmx.bones[parent].pos)
		posChi = Vector3.FromList(pmx.bones[child].pos)
		pos3 = Vector3.LerpS(posPar, posChi, 0.6)
		pos4 = Vector3.Normalize(posChi - posPar)
		
		elbowRot.parent_idx = parent
		elbowRot.name_en = nameEN
		elbowRot.pos  = Vector3.ToList(pos3)
		elbowRot.fixedaxis = Vector3.ToList(pos4)
		elbowRot.has_rotate = True
		elbowRot.has_fixedaxis = True
		insert_single_bone(pmx, elbowRot, _idx + 1);
		boneChi.parent_idx = fb(elbowRot.name_jp)
		
		return _idx + 1
	
	insert_twist_bone(fb("右腕"), "右腕捩", "arm twist_R", fb("右腕"), fb("右ひじ"))
	insert_twist_bone(fb("左腕"), "左腕捩", "arm twist_L", fb("左腕"), fb("左ひじ"))
	insert_twist_bone(fb("右ひじ"), "右手捩", "wrist twist_R", fb("右ひじ"), fb("右手首"))
	insert_twist_bone(fb("左ひじ"), "左手捩", "wrist twist_L", fb("左ひじ"), fb("左手首"))
	
	##-- Fix incomplete coverage of wrist_twist
	#> Plugin fails because vertices are in these bones, instead of elbow
	if find_bone(pmx, "左手捩", False) != -1:
		def set_attr(parent, ratio, name):
			twist = pmx.bones[find_bone(pmx, name)]
			twist.inherit_rot = True
			twist.inherit_parent_idx = parent
			twist.inherit_ratio = ratio
			
		twistL = find_bone(pmx, "左手捩") ## Semi-Standard "wrist_twist L"
		set_attr(twistL, 0.25, "cf_s_forearm01_L")## Technically this should be moved a bit outwards to be the same as in the arm
		set_attr(twistL, 0.50, "cf_s_forearm02_L")
		set_attr(twistL, 0.75, "cf_s_wrist_L")
		
		twistR = find_bone(pmx, "右手捩") ## Semi-Standard "wrist_twist R"
		set_attr(twistR, 0.25, "cf_s_forearm01_R")
		set_attr(twistR, 0.50, "cf_s_forearm02_R")
		set_attr(twistR, 0.75, "cf_s_wrist_R")
		
		##-- Don't see any effect on these.... but technically has same the problem.
		twistL = find_bone(pmx, "左腕捩") ## Semi-Standard "arm_twist L"
		set_attr(twistL, 0.25, "cf_s_arm01_L")
		set_attr(twistL, 0.50, "cf_s_arm02_L")
		set_attr(twistL, 0.75, "cf_s_arm03_L")
		
		twistR = find_bone(pmx, "右腕捩") ## Semi-Standard "arm_twist R"
		set_attr(twistR, 0.25, "cf_s_arm01_R")
		set_attr(twistR, 0.50, "cf_s_arm02_R")
		set_attr(twistR, 0.75, "cf_s_arm03_R")
	
	###--- Add [Semi-Standard-Bones] "D-Bone Operational"
	#: Run it normally first, then replace "D Toes" with "D Foot" and instead assign the regular Toes to "D Toes"
	##-----------------------------------
	#ä--- Move Rotation Axis of shoulders a bit more outwards to make it look less weird
	def move_shoulders(_bone, _src):
		if -1 in [_bone, _src]: return
		pmx.bones[_bone].pos[0] = pmx.bones[_src].pos[0]
	move_shoulders(fb("左肩"), fb("cf_hit_shoulder_L"))
	move_shoulders(fb("右肩"), fb("cf_hit_shoulder_R"))
	
	##--- Make elbow fold move with elbow instead of [cf_s_forearm01_L,R]
	if find_bone(pmx, "cf_s_elboback_L", False) != -1:
		## Clone elbow, attach these two and the other two to that instead -- Avoids 
		def insert_extra_elbow(_idx, nameEN):
			if _idx == -1: return
			bone = pmx.bones[_idx]
			elbowRot = copy.deepcopy(bone)
			elbowRot.name_jp = bone.name_jp + "_Rot"
			_idx2 = find_bone(pmx, elbowRot.name_jp, False)
			if _idx2 != -1:
				elbowRot = pmx.bones[_idx2]
				elbowRot.parent_idx = _idx
				return _idx2
			elbowRot.name_en = nameEN
			elbowRot.has_visible = False
			elbowRot.inherit_rot = True
			elbowRot.inherit_trans = True
			elbowRot.inherit_parent_idx = _idx
			elbowRot.inherit_ratio = 0.5
			insert_single_bone(pmx, elbowRot, _idx + 1);
			return _idx + 1
		## Replacing existing one does not seem to work...
		elbow = find_bone(pmx, "左ひじ")
		_elbow = insert_extra_elbow(elbow, "elbow_L_Rot")
		
		bone = pmx.bones[find_bone(pmx, "cf_s_elbo_L")]
		bone.parent_idx = bone.parent_idx if elbow == -1 else _elbow
		bone = pmx.bones[find_bone(pmx, "cf_s_elboback_L")]
		bone.parent_idx = bone.parent_idx if elbow == -1 else _elbow
		
		elbow = find_bone(pmx, "右ひじ")
		_elbow = insert_extra_elbow(elbow, "elbow_R_Rot")
		
		bone = pmx.bones[find_bone(pmx, "cf_s_elbo_R")]
		bone.parent_idx = bone.parent_idx if elbow == -1 else _elbow
		bone = pmx.bones[find_bone(pmx, "cf_s_elboback_R")]
		bone.parent_idx = bone.parent_idx if elbow == -1 else _elbow
	
	#adjust_bone("左肩C", lambda b: b.name_en = "shoulderC_L")
	#adjust_bone("右肩C", lambda b: b.name_en = "shoulderC_R")
	idx = find_bone(pmx, "左肩C", False)
	if idx != -1: pmx.bones[idx].name_en = "shoulderC_L"
	idx = find_bone(pmx, "右肩C", False)
	if idx != -1: pmx.bones[idx].name_en = "shoulderC_R"
	
	## --- Restore IK in case it is gone
	## --- Allow Rotation since it seems to have been needed
	bones = util.find_bones(pmx, ["左足ＩＫ", "左つま先ＩＫ", "右足ＩＫ", "右つま先ＩＫ"], returnIdx=False)
	for bone in [x for x in bones if x != None]: bone.has_rotate = True
	
	## --- Find these based on non-T-Pose alignment
	def add_axis(name, fixedaxis, localaxis):
		idx = find_bone(pmx, name)
		if idx == -1: return
		bone = pmx.bones[idx]
		if fixedaxis and fixedaxis != [0, 0, 0]:
			bone.has_fixedaxis = True
			bone.fixedaxis = fixedaxis
		if localaxis and localaxis != [1, 0, 0, 0, 0, 1]:
			bone.has_localaxis = True
			bone.localaxis_x = [localaxis[0], localaxis[1], localaxis[2]]
			bone.localaxis_z = [localaxis[3], localaxis[4], localaxis[5]]
	
	return
	
	########
	pass####

## [Mode 01]
def adjust_chest_physics(pmx):
	## Chest collision
	if find_rigid(pmx, "左胸操作", False) == -1: return ["No chest anchor found"]
	## The two long bones: 左AH1, 右AH1: Auto adjusts bc link
	## The two hidden bones: 左AH2, 右AH2:  PosZ +0.4
	bone = find_bone(pmx, "左AH2")
	pmx.bones[bone].pos[2] += 0.4
	bone = find_bone(pmx, "右AH2")
	pmx.bones[bone].pos[2] += 0.4
	## Long Rigid: 左胸操作接続, 右胸操作接続: Height -0.4, PosZ +0.2
	rigid = find_rigid(pmx, "左胸操作接続")
	pmx.rigidbodies[rigid].size[1] -= 0.4
	pmx.rigidbodies[rigid].pos[2] += 0.2
	rigid = find_rigid(pmx, "右胸操作接続")
	pmx.rigidbodies[rigid].size[1] -= 0.4
	pmx.rigidbodies[rigid].pos[2] += 0.2
	## End Rigid: 左AH2, 右AH2: PosZ +0.4
	rigid = find_rigid(pmx, "左AH2")
	pmx.rigidbodies[rigid].pos[2] += 0.4
	rigid = find_rigid(pmx, "右AH2")
	pmx.rigidbodies[rigid].pos[2] += 0.4
	return ["Bone+Rigid(左AH2, 右AH2): PosZ +0.4","Rigid(左胸操作接続,右胸操作接続): Height -0.4, PosZ +0.2"]

def fix_skirt_rigs(pmx): ReplaceAllWeights(pmx, 202, 192)
def ReplaceAllWeights(pmx, searchFor, replaceWith):
	def replaceBone(target):
		if target == searchFor: return replaceWith
		return target
	for vert in pmx.verts:
		#vert = pmx.verts[idx]
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

## [Step 02]
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
	
	printStage("Transform Skirt")
	moreinfo = local_state["moreinfo"]
	
	col__skirt_tail = merge_collision_groups([GRP_SKIRT, GRP_TAIL])
	
	rotY = 0
	rigids = []
	bones = []
	cleanup = {}
	for rigid in pmx.rigidbodies:
		## Change width of all but [05] to XX (start at 0.6)
		if not re.match(r"cf_j_sk", rigid.name_jp): continue
		rigids.append(rigid)
		m = re.match(r"cf_j_sk_(\d+)_(\d+)", rigid.name_jp)
		bones.append(rigid.bone_idx)
		cleanup.setdefault(m[1], [])
		cleanup[m[1]] += [rigid.bone_idx]
		rigid.nocollide_mask = col__skirt_tail
		
		## Normalize Rotation for extended lines below
		rigid.rot = util.normalize(rigid.rot, 360)
		
		## Unify the outward Rotation for all lines (some assets mess them up)
		if int(m[2]) == 0: rotY = rigid.rot[1]
		else: rigid.rot[1] = rotY
		
		rigid.phys_mass = 1
		rigid.phys_move_damp = 0.5
		rigid.phys_rot_damp = 0.5
		rigid.phys_repel = 0
		rigid.phys_friction = 0.5
		if int(m[2]) == 5: ## Keep the ends as capsules
			#rigid.phys_mass = 2
			continue
		
		## Change mode to 1 & set depth to 0.02
		rigid.shape = 1
		rigid.size[0] = 0.6
		rigid.size[2] = 0.02
		
		#-- Make front / back pieces a bit wider
		if int(m[1]) in [0,4]: rigid.size[0] = 0.7
	
	## Add them as a whole to the cleanup dict for later
	local_state[RBD__CLEANUP]["__skirt__"] = list(cleanup.values())
	
	if len(rigids) == 0:
		print("> No Skirt rigids found, skipping")
		return
	elif len(rigids) > 48:
		print("> Skirt already rigged, skipping")
		return
	
	## Create more rigids inbetween (?)
	
	## Move Side Joints to sides (X + width / 2, Y + height / 2)
	joints = []
	for joint in pmx.joints:
		if not re.match(r"cf_j_sk", joint.name_jp): continue
		joints.append(joint)
		if re.match(r"cf_j_sk_\d\d_05", joint.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_\d\d\[side\]", joint.name_jp):
			rigid = pmx.rigidbodies[joint.rb1_idx]
			## X pos requires using triangulation, maybe later
			#joint.pos[0] = rigid.pos[0] + rigid.size[0] / 2
			joint.pos[1] = rigid.pos[1] + rigid.size[1]# / 2
			joint.pos[2] = rigid.pos[2] + rigid.size[2]# / 2

	#### Make skirt move more like a fluid
	for joint in joints:
		m = re.match(r"cf_j_sk_(\d+)_(\d+)(\[side\])?", joint.name_jp)
		main = int(m[1])
		sub  = int(m[2])
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
		#-- Remark: Seems like the Joints of cf_j_sk_03_04/5 (and diagonal front counterpart) are dropping a bit more than the others (==CW the first of front / back)
	##################################
	####### Extend skirt with more "lines"
	#### First the rigidbodies
	commonRbd = {
		#name_jp: str, name_en: str, "bone_idx": int,
		#pos: List[float], rot: List[float], size: List[float],
		#"shape": rigids[0].shape,
		"group": rigids[0].group,
		"nocollide_mask": rigids[0].nocollide_mask,
		#"phys_mode": int,
		"phys_mass": rigids[0].phys_mass,
		"phys_move_damp": rigids[0].phys_move_damp,
		"phys_rot_damp": rigids[0].phys_rot_damp,
		"phys_repel": rigids[0].phys_repel,
		"phys_friction": rigids[0].phys_friction,
	}
	
	## Get pair of 0-1, 1-2, ... 7-0 for each rigid
	def chunk(lst, n): return [lst[i:i + n] for i in range(0, len(lst), n)]
	def pairwise(lst): return zip(*[iter(lst)]*2)
	def average(arr1, arr2):
		arr = []
		arr.append((arr1[0] + arr2[0]) / 2)
		arr.append((arr1[1] + arr2[1]) / 2)
		arr.append((arr1[2] + arr2[2]) / 2)
		return arr
	
	rlst = chunk(rigids, 6)
	rigid_dict = {
		"10": zip(rlst[0], rlst[1]), "12": zip(rlst[1], rlst[2]),
		"23": zip(rlst[2], rlst[3]), "34": zip(rlst[3], rlst[4]),
		"45": zip(rlst[4], rlst[5]), "56": zip(rlst[5], rlst[6]),
		"67": zip(rlst[6], rlst[7]), "70": zip(rlst[7], rlst[0]),
	}
	
	if moreinfo: printSubStage("Physics")
	## Get pos,rot,size of both, and set the average as new
	for grp in rigid_dict.items():
		#print("----- P Grp " + grp[0])
		## Grp = {
		#	[0]: class='str': len=2,
		#	[1]: class 'zip'
		#	>0 it> class 'tuple': 0 = Rigid, 1 = Rigid
		#	>1 it> class 'tuple': 0 = Rigid, 1 = Rigid
		#	>2 it> class 'tuple': 0 = Rigid, 1 = Rigid
		#	>3 it> class 'tuple': 0 = Rigid, 1 = Rigid
		#	>4 it> class 'tuple': 0 = Rigid, 1 = Rigid
		#	>5 it> class 'tuple': 0 = Rigid, 1 = Rigid
		#}
		for l,r in list(grp[1]):
			m = re.match(r"cf_j_sk_(\d+)_(\d+)", l.name_jp)
			name = f"cf_j_sk_{grp[0]}_{m[2]}"
			pos = average(l.pos, r.pos)
			rot = average(l.rot, r.rot)
			## 1 -> 2 can be weird, so flip the X
			##>> 1=Pos/Rot(-+- +++) vs 2=Pos/Rot(-++ +-+) -> 12=Pos/Rot(-+- +-+)
			#if grp[0] == '12': rot[0] = -rot[0] #        -> 12=Pos/Rot(-+- --+)
			size = average(l.size, r.size)
			bone_idx = l.bone_idx
			shape = l.shape # 2 if int(m[1]) == 5 else 1
			mode = l.phys_mode # 0 if int(m[1]) == 0 else 1
			add_rigid(pmx, name_jp=name, pos=pos, rot=rot, size=size, shape=shape,
				phys_mode=mode, bone_idx=bone_idx, **commonRbd)

	##-- Bind them together because screw you
	#util.bind_bone(pmx, )
	
	################
	## Same for joints
	if moreinfo: printSubStage("Joints")
	
	jlst = chunk(joints[0:8*5], 5)
	joint_dict = { # 10,70 to avoid confusion with 01 & 07
		"10": zip(jlst[0], jlst[1]), "12": zip(jlst[1], jlst[2]),
		"23": zip(jlst[2], jlst[3]), "34": zip(jlst[3], jlst[4]),
		"45": zip(jlst[4], jlst[5]), "56": zip(jlst[5], jlst[6]),
		"67": zip(jlst[6], jlst[7]), "70": zip(jlst[7], jlst[0]),
	}
	## Get pos,rot,size of both, and set the average as new
	for grp in joint_dict.items():
		for l,r in list(grp[1]):
			m = re.match(r"cf_j_sk_(\d+)_(\d+)", l.name_jp)
			name = f"cf_j_sk_{grp[0]}_{m[2]}"
			## Starts with 10_01 -- connects 10_00 to 10_01
			rb1_idx    = find_rigid(pmx, f"cf_j_sk_{grp[0]}_0{int(m[2])-1}")
			rb2_idx    = find_rigid(pmx, f"cf_j_sk_{grp[0]}_0{int(m[2])}")
			pos        = average(l.pos, r.pos)
			rot        = average(l.rot, r.rot)
			
			add_joint(pmx, name_jp=name, 
				jointtype  = l.jointtype ,
				rb1_idx    = rb1_idx   , rb2_idx    = rb2_idx   ,
				pos        = pos       , rot        = rot       ,
				movemin = l.movemin, movemax = l.movemax, movespring = l.movespring,
				rotmin  = l.rotmin , rotmax  = l.rotmax , rotspring  = l.rotspring
			)
	####### And again for the side ones
	jslst = chunk(joints[8*5:-1], 6)
	
	if len(jslst) == 0:
		print("[!] The model did not contain any [side] joints -- skipping them")
		##-- Set the 2nd row to silent because they will vibrate because of the butt
		for rigid in pmx.rigidbodies:
			if re.match(r"cf_j_sk_\d+_01", rigid.name_jp): rigid.phys_mode = 0
		return
	
	side_dict = {
		"10": zip(jslst[0], jslst[1]), "12": zip(jslst[1], jslst[2]),
		"23": zip(jslst[2], jslst[3]), "34": zip(jslst[3], jslst[4]),
		"45": zip(jslst[4], jslst[5]), "56": zip(jslst[5], jslst[6]),
		"67": zip(jslst[6], jslst[7]), "70": zip(jslst[7], jslst[0]),
	}
	
	## Have to rebind the original side joints as well
	grp_dict = {
		"10": "01",  "01": "12",
		"12": "02",  "02": "23",
		"23": "03",  "03": "34",
		"34": "04",  "04": "45",
		"45": "05",  "05": "56",
		"56": "06",  "06": "67",
		"67": "07",  "07": "70",
		"70": "00",  "00": "10",
	}
	
	## Get pos,rot,size of both, and set the average as new
	if moreinfo: printSubStage("Side Joints")
	for grp in side_dict.items():
		for l,r in list(grp[1]):
			m = re.match(r"cf_j_sk_(\d+)_(\d+)(\[side\])", l.name_jp)
			name = f"cf_j_sk_{grp[0]}_{m[2]}{m[3]}"
			## Starts with 10_00 -- connects 10_00 with 01_00
			rb1_idx    = find_rigid(pmx, f"cf_j_sk_{grp[0]}_{m[2]}")
			rb2_idx    = find_rigid(pmx, f"cf_j_sk_{grp_dict[grp[0]]}_{m[2]}")
			pos        = average(l.pos, r.pos)
			rot        = average(l.rot, r.rot)
			
			add_joint(pmx, name_jp=name, 
				jointtype  = l.jointtype,
				rb1_idx    = rb1_idx   , rb2_idx    = rb2_idx   ,
				pos        = pos       , rot        = rot       ,
				movemin = l.movemin, movemax = l.movemax, movespring = l.movespring,
				rotmin  = l.rotmin , rotmax  = l.rotmax , rotspring  = l.rotspring
			)
	### Rebind original joints
	for joint in joints[8*5:-1]:
		## Starts with 00_00 -- connects 00_00 with old:01_00 / new:10_00
		m = re.match(r"cf_j_sk_(\d+)_(\d+)(\[side\])", joint.name_jp)
		joint.rb2_idx = find_rigid(pmx, f"cf_j_sk_{grp_dict[m[1]]}_{m[2]}")
	
	
##########
	pass# To keep trailing comments inside

# --[Fix materials that exist multiple times]-- #

text_about_rigid_names = """
Names for RigidBodies are build like this:

Prefix is the root slot the Rigid belongs to (e.g. ca_slot06)
If the asset used separate roots for Left/Right, "-0" / "-1" is added
Next, a running number ("_0", "_1", ...) is added for each separate chain detected within the asset
Last, we append ":" and the name of the attached bone to it

Joints are build similarly, but simply copy the name of the secondary rigid of the junction

"""

## [Step 04]
def rig_hair_joints(pmx): #--- Find merged / split hair chains --> apply Rigging to them
	printStage("Rig Hair")
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
	_limit = lambda i: i < limit
	
	local_state[OPT__HAIR] = True
	################################
	_patch_bone_array = lambda x,n: patch_bone_array(pmx, head_body, x, n, grp=3)
	__rig_acc_joints(pmx, _patch_bone_array, _limit)
RBD__MULTIROOT = "multi_root"
## [Common of 04+05]
def __rig_acc_joints(pmx, _patch_bone_array, limit): ## TODO: Make the tail end have a tail in the same diretion as the previous bone-Link
	"""
	:: private method as common node for both normal and hair chains
	"""
	verbose = True#_verbose()
	dRigAcc = False
	### At least this exists for every accessory
	__root_Name = "N_move"
	bones = [i for (i,b) in enumerate(pmx.bones) if b.name_jp.startswith(__root_Name)]
	if dRigAcc: print(bones)
	### Some assets allow separate movement for each side
	__root_Name2 = "N_move2"
	bones2 = [i for (i,b) in enumerate(pmx.bones) if b.name_jp.startswith(__root_Name2)]
	
	if len(bones) == 0:
		print("> No acc chains found to rig.")
		return
	
	#--- Merge the secondary roots into the primary to keep things simple (hopefully)
	mergeDict = {}
	if len(bones2) > 0:
		for bone in bones2:
			b = bone
			while (b and not pmx.bones[b].name_jp.startswith("ca_slot")): b = pmx.bones[b].parent_idx
			name = pmx.bones[b].name_jp
			mergeDict[name] = mergeDict.get(name, []) + [bone]
	
	local_state[OPT__NODUPES] = True
	local_state.setdefault(RBD__CLEANUP, {})
	local_state.setdefault(RBD__MULTIROOT, False)
	
	roots_to_evaluate = []
	################################
	for bone in bones:
		##[Hair] Ignore the groups not anchored to the head
		##[Rest] Ignore the hair groups
		if limit(pmx.bones[bone].pos[1]): continue
		##[Ignore the ones from bones2 bc already added I guess]
		if bone in bones2: continue
		local_state[RBD__MULTIROOT] = False
		
		## Get name from containing slot
		b = bone
		while (b and not pmx.bones[b].name_jp.startswith("ca_slot")): b = pmx.bones[b].parent_idx
		name = pmx.bones[b].name_jp
		#dRigAcc = name in ["ca_slot16", "ca_slot20", "ca_slot07", "ca_slot06"]
		if dRigAcc: print(f"---- Parse [{bone}] > [{b}]: {name}")
		#Example: [487] > [486]: ca_slot16 with N_move: 488 till 497
		#Example: [498] > [486]: ca_slot16 with N_move2: 499 till 504
		
		## Collect bone chain
		if name in mergeDict:
			print(f" Found {name} in Merge Dict")
			local_state[RBD__MULTIROOT] = True
			##--- Search for all root bones we found for this slot instead of a single one
			arr = get_children_map(pmx, [ bone ] + mergeDict[name], returnIdx=False, add_first=False)
		else:
			arr = get_children_map(pmx, bone, returnIdx=False, add_first=False)
		if dRigAcc: print(f" Arr: {arr}")
		#--- Rewrote to work with arbitary root bone
		root_arr = [x for x in arr.keys() if x.startswith(__root_Name)]
		if not any(root_arr): print(f"{bone} has weird bones({list(arr.keys())}), skipping"); continue
		
		#-- This prints either N_move or N_move2
		
		if local_state[RBD__MULTIROOT]:
			if dRigAcc: print(f" RootArr has these chains: {root_arr}")
			for i,rArr in enumerate(root_arr):
				root_arr0 = arr[root_arr[i]]
				if dRigAcc: print(f"> root_arr0: {root_arr0}")
				roots_to_evaluate.append((f"{name}-{i}", root_arr0))
		else:
			root_arr0 = arr[root_arr[0]] ## root_arr[list(root_arr.keys())[0]]
			#if dRigAcc: print(f" root_arr0: {root_arr0}") ## Equal to what [Arr] prints above
			roots_to_evaluate.append((name, root_arr0))
	#print(roots_to_evaluate)
	for __item in roots_to_evaluate: ### Turned into loop to keep history
		prefix    = __item[0]
		root_arr0 = __item[1]
		root_arr1 = []
		## These exist just to make it... less complicated
		mostRec = "mostRec"
		finder_dict = { mostRec: "" }
		def finder(name): 
			finder_dict[mostRec] = name
			return [x for x in root_arr0 if pmx.bones[x].name_jp.startswith(name)]
		def finder2(name, _arr): return [x for x in _arr if pmx.bones[x].name_jp.startswith(name)]
		def descend_first(root_arrX):
			## Reduce to its children
			_arr = get_children_map(pmx, root_arrX[0], returnIdx=False, add_first=False)
			## Descend to first of those
			return _arr[list(_arr.keys())[0]]
		def get_direct_chains(_arr, parent_idx):
			## Get a full Tree map of these bones
			all_child = get_children_map(pmx, _arr, returnIdx=False, add_first=True)
			## Reduce to the chains whose first bone has the above as parent
			return [all_child[pmx.bones[x].name_jp] for x in _arr if pmx.bones[x].parent_idx == parent_idx]
		##-- Finalizer of most finders
		def evaluate_chains(_arr, first_parent):
			if verbose:
				print(f":: {prefix} starting with {first_parent} -- {finder_dict[mostRec]}")
				print(_arr);print("----")
			local_state[RBD__CLEANUP][prefix] = _arr
			for i,arr in enumerate(_arr): _patch_bone_array(arr, prefix+'_'+str(i))
		##-- Pull down the "_end" Tails because they are annoying
		def shift_weird_end_bone(_arr):
			rgx = re.compile("_end(\*\d+)?$")
			for hair_arr in _arr:
				lastBone = pmx.bones[hair_arr[-1]]
				if rgx.search(lastBone.name_jp):
					_parent = pmx.bones[lastBone.parent_idx]
					lastBone.pos[1] = _parent.pos[1] ## Copy Height from Parent to avoid weird rigids
					#lastBone.has_visible = False ## Mark it as proper Tail too.
		
		##################
		#-- CM3D2 Handling -- because it contains [joints.xxx]
		root_arr1 = finder("Bone_Face")
		printIt = False#prefix == "ca_slot00"
		if util.PRODUCTIONFLAG: printIt = False
		if printIt: print("--------------- " + prefix)
		def doPrint(x, name=""): 
			if printIt: print(name); print(x)
		if any(root_arr1):
			#printIt = True
			##[C] Descend onto Hair_R etc.
			if (printIt):
				for _bb in root_arr0:
					print(f"{_bb}: {pmx.bones[_bb].name_jp}")
			# Hair_F = 300,301
			# Hair_R = 302
			# _yure_hair = 303 to 342, joints.002 on 343, rigidbodies.003 on 374
			#print("-- root_arr0")
			doPrint(root_arr0) #### starts on first after [N_move]: 297 -- 419 = last before next slot
			#print("-- root_arr1")
			doPrint(root_arr1)		### 299, 376 -- Both Bone_Face -- only first has the vertex bones
			root_arr2 = get_direct_chains(root_arr0, root_arr1[0])
			child_arr = []
			for elem in root_arr1:
				arr = descend_first([elem]) ## [Bone_Face -> all children]
				##[C] Reduce to children but keep first -- it contains some root weights
				##[A] Reduce to the chains whose first bone has "AS01_J_kami" as parent
				hair = finder2("Hair_F", arr)		### 300, 301 == Hair_F, ok
				doPrint(hair, "Hair_F")
				if len(hair) > 2: child_arr += get_direct_chains(arr, hair[0])
				hair = finder2("Hair_R", arr)		### 302 == Hair_R, ok
				doPrint(hair, "Hair_R")
				if len(hair) > 2: child_arr += get_direct_chains(arr, hair[0])
				hair = finder2("_yure_hair_", arr)	### 303 -- 342 -- Ok, but parented to hair_R
				if len(hair) > 2: child_arr += get_direct_chains(arr, pmx.bones[hair[0]].parent_idx)
				doPrint(hair, "_yure_hair_")
				doPrint(child_arr, "---- child_arr")
			#child_arr = get_direct_chains(arr, arr[0])
			shift_weird_end_bone(child_arr)
			evaluate_chains(child_arr, root_arr1[0]);continue
		##################
		#-- AS01 Handling  -- contains "SCENE_ROOT"
		root_arr1 = finder("AS01_N_kami")
		if any(root_arr1):
			##[C] Descend onto Hair_R etc.
			arr = descend_first(root_arr1)
			##[C] Reduce to children but keep first -- it contains some root weights
			##[A] Reduce to the chains whose first bone has "AS01_J_kami" as parent
			child_arr = get_direct_chains(arr, arr[0])
			shift_weird_end_bone(child_arr)
			evaluate_chains(child_arr, root_arr1[0]);continue
		
		# AS00_N_kami
		# > A00_N_kamiB --> "O"
		# > A00_N_kamiBtop --> "J"
		# > > A00_J_kamiBtop >> RB00... LB00 .. B00
		
		root_arr1 = finder("AS00_N_kami")
		if any(root_arr1):
			##[C] Descend onto Hair_R etc.
			arr = descend_first(root_arr1)
			##[A] Reduce to the chains whose first bone has "AS01_J_kami" as parent
			child_arr = get_direct_chains(arr, arr[0])
			
			#-- Skip the "O" branch
			topBone = pmx.bones[child_arr[0][0]]
			if topBone.name_jp.startswith("A00_O"):
				child_arr = get_direct_chains(arr, child_arr[-1][-1]+1)
			
			#-- Descend the first "J" parent if special
			topBone = pmx.bones[child_arr[0][0]]
			doFlag  = topBone.name_jp.endswith("kami00")
			doFlag |= re.search("kami[SB]top$", topBone.name_jp) is not None
			if doFlag:
				arr = descend_first(child_arr)
				child_arr = get_direct_chains(arr, child_arr[0][0])
			evaluate_chains(child_arr, root_arr1[0]);continue
		##################
		#-- Regular Joint Handling
		root_arr1 = finder("root") + finder("joint")
		if any(root_arr1):
			## Get parent of first bone
			first_parent = pmx.bones[root_arr1[0]].parent_idx
			child_arr = get_direct_chains(root_arr0, first_parent)
			evaluate_chains(child_arr, root_arr1[0]);continue
		##################
		#-- p_cf_hair && cf_N_J_ Handling
		root_arr3 = finder("cf_N_J_")
		if False and any(root_arr3):
			continue ## Already pre-rigged ? --> Or simply add [Group 16] to pre-rigged ones
			arr = descend_first(root_arr3)
			child_arr = get_direct_chains(arr, arr[0])
			evaluate_chains(child_arr, root_arr3[0]);continue
		#######################
		# Common Accs: Use all that have "prefix" as parent
		##################
		#-- Common hair
		root_arr2 = finder("cf_J_hairF_top")
		root_arr2 += finder("cf_J_hairB_top")
		#-- [acs_j_top]: Cardigan -- needs more arm rigids
		#-- [j_acs_1]: acs_m_idolwaistribbon -- 
		root_arr2 += finder("acs_j_top") + finder("j_acs_1") + finder("acs_j_usamimi_00")
		if any(root_arr2):
			arr = descend_first(root_arr2)
			child_arr = get_direct_chains(arr, root_arr2[0])
			evaluate_chains(child_arr, root_arr2[0]);continue
		#######################
		## If nothing else, just filter out all Renderer bones (= starting with "o_") and go all-in.
		arr = root_arr0
		if len(arr) == 0: continue
		if pmx.bones[arr[0]].name_jp.startswith("All_Root"): continue
		arr = [x for x in arr if not pmx.bones[x].name_jp.startswith("o_")]
		if len(arr) < 2: continue
		
		local_state[RBD__CLEANUP][prefix] = [arr]
		_patch_bone_array(arr, prefix)
	local_state[OPT__NODUPES] = False
####################
	pass

## [Step 05]
def rig_other_stuff(pmx):
	printStage("Rig non hair stuff")
	## Get reference point for discard
	try: limit = pmx.bones[find_bone(pmx, "胸親", False)].pos[1]
	except: limit = 0.0
	_limit = lambda i: i > limit
	_patch_bone_array = lambda x,n: patch_bone_array(pmx, None, x, n, grp=16)
	__rig_acc_joints(pmx, _patch_bone_array, _limit)

### Annotation
# Maybe rig Tongue: weighted to [cf_J_MouthCavity] << cf_J_MouthBase_rx < ty < cf_J_FaceLow_tz < Base < J FaceRoot < J_N < p_cf_head_bone < cf_s_head
#>> But these exist: cf_s_head < cf_j_tang_01 < 02 < 03 < 04(< 05(< L+R), L+R), L+R -- Quite some below the mesh though

## [Step 06] -- Cut chains into smaller segments that correspond more with how the bones are connected
def rig_rough_detangle(pmx, custArr=None): ## << HAS TODO
	printStage("Detangle some chains")
	if _verbose(): print("> aka perform [Mode: 3] for some obvious cases")
	isCustom = custArr is not None
	# Remark: The first three of any given ca_slot are already [green] through generation
	## Get all rigging starting with ca_slot
	def collect(item):
		idx = item[0]
		rig = item[1]
		if isCustom:
			if rig.bone_idx not in custArr: return False
		elif not rig.name_jp.startswith("ca_slot"): return False
		if idx == len(pmx.rigidbodies) - 1: return False
		
		def matcher(_m, _n = None, isLess = False):
			if _n is None: _n = _m
			m = re.search(_m, rig.name_jp)
			if m:
				n = re.search(_n, pmx.rigidbodies[idx+1].name_jp)
				if not n: return False
				if isLess: return int(m[1]) < int(n[1])
				return int(m[1]) > int(n[1])
			return None
		
		## TODO: Verify Chains where a Hair strand is not anchored to the root but halfway on another
		#-- e.g. parent of green is not green but orange --> turn orange as well
		
		###-- This should cover everything if the bone structure is correct already
		if True:
			cur = rig.bone_idx
			nxt = pmx.bones[pmx.rigidbodies[idx+1].bone_idx]
			#- Consider any two subsequent rigids whose bones are not parent x child
			if nxt.parent_idx != cur:
				#- ... but ignore those where the first is already a tail to begin with
				return pmx.bones[cur].tail_usebonelink
		
		###-- Otherwise (if it somehow is still weird) go off manually.
		## Basic joints -- Just to capture that ahead of time
		ret = matcher(r"joint(\d+)");
		if ret is not None: return ret
		
		## "ca_slot05_0:joint1-3" > "ca_slot05_0:joint2-1"
		ret = matcher(r"joint(\d+)-\d+", None, True);
		if ret is not None: return ret
		
		## Always if with "_end$"
		mm = re.search(r"\d+_end$", rig.name_jp) is not None
		mm |= re.search(r"_base_[FSB]$", rig.name_jp) is not None ## ["May_Strongs"]
		if mm: return True
		
		## "left+1,2,3..." > "right+1,2,3"
		lst = "left|right|front|back|head|body"
		ret = matcher(r"(?:"+lst+r")[LR]?(\d)$");
		if ret is not None: return ret
		
		## "R1,R2,R3" > "L1,L2,L3", with optional "Top / Side / Bottom"
		ret = matcher(r"[LR][TSB]?(\d+)$");
		if ret is not None: return ret
		
		## A00 and AS01
		ret = matcher(r"kami[LRB]?[TSB](\d+)$");
		if ret is not None: return ret
		
		## "2_L" > "1_R"
		ret = matcher(r"(\d+)_[LR]$");
		if ret is not None: return ret
		
		## Check if next is "_core$" << from "mat_sshair2"
		xx = "|".join(["_core"])
		#-- Stuff from SCENE_ROOT
		yy = "|".join(["[BS]top"])
		zz = (xx + "|" + yy).strip("|")
		mm = re.search(r"(" + zz + r")$", pmx.rigidbodies[idx+1].name_jp)
		if mm: return True
		
		## Nothing matched
		return False
	######
	arr = [item[0] for item in enumerate(pmx.rigidbodies) if collect(item)]
	print(f"> Found {len(arr)} entries to verify")
	return split_rigid_chain(pmx, arr)

## [Step XX] -- Merge some bones
def merge_bone_weights(pmx, input_filename_pmx=None):
	import kkpmx_core as kkcore
	printStage("Merge some bones")
	log_line = ["Moved bone weights of:"]
	### Read in Bones to replace
	
	def replace_bone(oldIdx, newIdx):
		if type(oldIdx) != type([]): oldIdx = [oldIdx]
		if len(oldIdx) == 0 or newIdx == -1: return
		for vert in pmx.verts:
			if vert.weighttype == 0:
				if(vert.weight[0] in oldIdx): vert.weight[0] = newIdx
			elif vert.weighttype == 1:
				if(vert.weight[0] in oldIdx): vert.weight[0] = newIdx
				if(vert.weight[1] in oldIdx): vert.weight[1] = newIdx
			elif vert.weighttype == 2:
				if(vert.weight[0] in oldIdx): vert.weight[0] = newIdx
				if(vert.weight[1] in oldIdx): vert.weight[1] = newIdx
				if(vert.weight[2] in oldIdx): vert.weight[2] = newIdx
				if(vert.weight[3] in oldIdx): vert.weight[3] = newIdx
			else:
				raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))
		log_line.append(f"-- {oldIdx} to {newIdx},{pmx.bones[newIdx].name_jp}")
	def replace_bones(oldIdx, newIdx):
		if type(oldIdx) != type([]): oldIdx = [oldIdx]
		if type(newIdx) == type(""): newIdx = find_bone(pmx, newIdx, True)
		arr = []
		for b in oldIdx:
			if type(b) == type(""): arr.append(find_bone(pmx, b, True))
			arr.append(b)
		try:
			replace_bone(list(filter(lambda x: x != -1, arr)), newIdx)
		except:
			print(f"[!] Error while reweighting {arr}")
	def replace_all_not_shared(srcIdx, cmpIdx, dumpIdx):
		srcIdx  = find_bone(pmx, srcIdx , True)
		cmpIdx  = find_bone(pmx, cmpIdx , True)
		dumpIdx = find_bone(pmx, dumpIdx, True)
		if -1 in [srcIdx, cmpIdx, dumpIdx]: raise Error("Must all exist")
		for vert in pmx.verts:
			all_verts = [x for x in vert.weight]
			if srcIdx not in all_verts: continue
			if cmpIdx in all_verts: continue
			perform_on_weights(vert, lambda x: x == srcIdx, dumpIdx)
		log_line.append(f"-- {srcIdx} (where not also {cmpIdx}) to {dumpIdx}, {pmx.bones[dumpIdx].name_jp}")
	def replace_all_shared(srcIdx, cmpIdx, dumpIdx=None):
		srcIdx  = find_bone(pmx, srcIdx , True)
		cmpIdx  = find_bone(pmx, cmpIdx , True)
		if not dumpIdx: dumpIdx = cmpIdx
		if -1 in [srcIdx, cmpIdx, dumpIdx]: raise Error("Must all exist")
		for vert in pmx.verts:
			all_verts = [x for x in vert.weight]
			if srcIdx not in all_verts: continue
			if cmpIdx not in all_verts: continue
			perform_on_weights(vert, lambda x: x == srcIdx, dumpIdx)
		log_line.append(f"-- {srcIdx} (where also {cmpIdx}) to {dumpIdx}, {pmx.bones[dumpIdx].name_jp}")

	##-- Fix [X-Axis] when rotating [arm_L, arm_R]
	#Swap [arm_L] <-> [左肩Solo]
	#Set [左肩Solo]: ROT+=1 L=57

	##-- Merge elbow bones -- Unknown if it fixes anything
	#replace_bones(["cf_s_elbo_L", "cf_s_forearm01_L", "cf_s_elboback_L"], "左ひじ")
	#replace_bones(["cf_s_elbo_R", "cf_s_forearm01_R", "cf_s_elboback_R"], "右ひじ")
	###-- Merge arm bones -- Fixes [X-Axis] when rotating [arm_L]
	#replace_bones(["cf_d_arm01_L", "cf_s_arm01_L", "cf_d_arm02_L", "cf_s_arm02_L", "cf_d_arm03_L", "cf_s_arm03_L"], "左腕")
	#replace_bones(["cf_d_arm01_R", "cf_s_arm01_R", "cf_d_arm02_R", "cf_s_arm02_R", "cf_d_arm03_R", "cf_s_arm03_R"], "右腕")
	###-- Merge shoulder bones -- Fixes [X-Axis] when rotating [shoulder_L]
	#replace_bones(["左肩Solo"], "左肩")
	#replace_bones(["右肩Solo"], "右肩")
	#
	###-- Merge knee bones (does not fix knee issue ?)
	#replace_bones(["cf_d_kneeF_L", "cf_s_leg01_L", "cf_s_kneeB_L"], "左ひざ")
	#replace_bones(["cf_d_kneeF_R", "cf_s_leg01_R", "cf_s_kneeB_R"], "右ひざ")
	
	
	#replace_all_shared("cf_s_elboback_L", "左肩Solo")
	#replace_all_shared("cf_s_elboback_R", "右肩Solo")

	
	if input_filename_pmx is not None:
		return kkcore.end(pmx, input_filename_pmx, "_boneMerge", log_line)
	return log_line

## [Step 07] -- Apply additional processing to certain materials
def handle_special_materials(pmx):
	import kkpmx_core as kkcore
	from kkpmx_core import from_material_get_faces, from_faces_get_vertices
	printStage("Handle special materials")
	verbose = _verbose()
	
	def collect_by_slot():
		_map = {}
		for mat in pmx.materials:
			m = util.readFromComment(mat.comment, 'Slot')
			s = util.readFromComment(mat.comment, 'AccId')
			if m is None or s is None: continue
			_arr = _map.get(m, [])
			_arr.append(s)
			_map[m] = _arr
		return _map
	slot_map = collect_by_slot()
	### Assign Chest Group to all Chest accs (verified to not work yet, try again)
	col__chestAll = adjust_collision_groups(GRP_CHESACC)
	for slot in [x for x in ["a_n_bust_f", "a_n_bust", "a_n_nip_L", "a_n_nip_R"] if x in slot_map]:
		for slotMat in [f"ca_slot{x}" for x in slot_map[slot]]:
			for rigid in util.find_all_in_sublist(slotMat, pmx.rigidbodies, returnIdx=False):
				rigid.group = GRP_CHESACC
				rigid.nocollide_mask = col__chestAll
	
	############
	## Fox Tail
	############
	# Set some properties
	skirt_col = get_collision_group(GRP_SKIRT)[1]
	acc_col   = get_collision_group(GRP_BODYACC)[1]
	tail_col  = get_collision_group(GRP_TAIL)
	col__skirt_acc_tail = merge_collision_groups([GRP_SKIRT, GRP_BODYACC, GRP_TAIL])
	col__acc_tail = merge_collision_groups([GRP_BODYACC, GRP_TAIL])
	
	#---
	tails = util.find_all_mats_by_name(pmx, "acs_m_tail_fox", withName=True)
	tails += util.find_all_mats_by_name(pmx, "arai_tail", withName=True) # Racoon Tail
	tails += util.find_all_mats_by_name(pmx, "acs_m_aku01_sippo", withName=True) # Demon Tail: j_01, j_02, j_03, ...
	tails += util.find_all_mats_by_name(pmx, "acs_m_cattail", withName=True) # Cat Tail
	tailCnt = 0
	for tail in tails:
		root = tail[0]
		## root >> contains "ca_slotXX"
		rigids = util.find_all_in_sublist(root, pmx.rigidbodies, returnIdx=False)
		if len(rigids) < 5: continue
		joints = util.find_all_in_sublist(root, pmx.joints, returnIdx=False)
		if len(joints) < 3: continue
		
		is_raccoon = tail[1] in ["arai_tail"]
		#print([(x.name_jp, x.bone_idx) for x in rigids])
		#print([(x.rb1_idx, x.rb2_idx) for x in joints])
		
		cnt = 0
		for rig in rigids:
			pmx.bones[rig.bone_idx].name_jp = f"Tail{tailCnt}_{cnt}"
			cnt += 1
		tailCnt += 1
		
		### Base
		body = rigids[0]
		body.group = tail_col[0]
		# Make the base bodies not interact with the Skirt << todo: Still causes Pantsu leaks, so find the skirt ones and make them ignore the tail
		body.nocollide_mask = col__skirt_acc_tail
		### Segment 0
		body = rigids[1]
		body.group = tail_col[0]
		body.nocollide_mask = col__skirt_acc_tail
		### Segment 1
		body = rigids[2];joint = joints[0]
		body.phys_mode = 1
		body.group = tail_col[0]
		body.nocollide_mask = col__acc_tail
		# Make movements more smooth
		joint.rotmax[0] = 40
		joint.rotmax[2] = 15
		joint.rotmin[2] = -15
		### Segment 2+
		#TODO: Determine if tail is inside skirt and don't omit it in that case
		for segment in zip(rigids[3:], joints[1:]):
			body = segment[0];joint = segment[1]
			body.group = tail_col[0]
			body.nocollide_mask = col__acc_tail
			joint.rotmax[0] = 50
			joint.rotmax[2] = 25
			joint.rotmin[2] = -25
		### End
		lastIdx = find_rigid(pmx, body.name_jp)
		
		########## Add extra bone to the end for fancyness
		# Find lowest vertice
		mat_idx = find_mat(pmx, tail[1])
		faces = from_material_get_faces(pmx, mat_idx, False, moreinfo=False)
		verts = from_faces_get_vertices(pmx, faces, False, moreinfo=False)
		def lowestY(e): return e.pos[1]
		verts.sort(key=lowestY)
		endVert = verts[0]
		
		# Create new bone
		lastBone = pmx.bones[body.bone_idx]
		bone_idx = add_bone(pmx, name_jp=f"{lastBone.name_jp}先", name_en=f"{lastBone.name_jp}_End")
		bone = pmx.bones[bone_idx]
		bone.pos         = endVert.pos
		bone.has_visible = False
		bone.parent_idx = body.bone_idx
		
		# Create new physics
		arr = [body.bone_idx, bone_idx]
		newName = body.name_jp.split(':')[0]
		util.bind_bone(pmx, arr, True)
		num_bodies = len(pmx.rigidbodies)
		num_joints = len(pmx.joints)
		AddBodyChainWithJoints(pmx, arr, 1, radius=0.0, uvFlag=False, name=newName, group=GRP_TAIL)
		
		if verbose:
			print(f"-- Adding extra physics for tail [{tail[1]}]")
			for x in pmx.rigidbodies[num_bodies:]: print(x)
			for x in pmx.joints[num_joints:]: print(x)
		
		new_body   = pmx.rigidbodies[num_bodies]
		tail_body  = pmx.rigidbodies[num_bodies+1]
		new_joint  = pmx.joints[num_joints]
		tail_joint = pmx.joints[num_joints+1]
		## Copy values from new_body to rigids[4]
		new_body.phys_mode = 1
		body = pmx.rigidbodies[lastIdx] = copy.deepcopy(new_body)
		### Set all of nocollide_mask again
		for rigid in rigids[2:]: rigid.nocollide_mask = col__acc_tail
		body.nocollide_mask      = col__acc_tail
		tail_body.nocollide_mask = col__acc_tail
		
		## Move start to center of new bone
		if is_raccoon:
			tail_bone = pmx.bones[bone_idx]
			tail_body.pos  = tail_bone.pos
			tail_joint.pos = tail_bone.pos
			tail_body.shape = 0
		## Rotate new tails like rigids[4]
		tail_body.rot  = body.rot
		tail_joint.rot = body.rot
		## Bind tail_joint to rigids[4] & tail_body
		tail_joint.rb1_idx = lastIdx
		tail_joint.rb2_idx = num_bodies+1
		## Clear limit of tail_joint
		tail_joint.rotmin = Vector3(0,0,0).ToList()
		tail_joint.rotmax = Vector3(0,0,0).ToList()
		## Mark new_body as invalid so that it is cleaned up
		new_body.bone_idx = 0
		## Connect new_joint to new_body for the same reason
		new_joint.rb1_idx = num_bodies
		new_joint.rb2_idx = num_bodies
	
	############
	## All in slot a_n_bust ignore chest ?
	############
	miko_flaps = util.find_all_mats_by_name(pmx, "acs_m_miko_sode_00")
	##### Find direction axis
	# Get max X, min X, max Z, min Z
	# -- Get min Y within 5% of that area
	# -- Higher Y on Z is front, other is back
	# -- Lower Y on X is Ribbon
	# -- Determine if Ribbon is towards or away from Body
	# -- Collect Bones, RigidBodies, Joints
	# --- [0] = center, [1,2]=Inner Top/Bottom, [3,4]=Outer T/B
	# -- Collect RigidBodies
	# --- Root, Hor Piece in Arm, 
	# --- Downwards Inner Top, End piece
	# -[Actions]
	# -- Add new Bone at bottom of the Flaps on both X
	# -- -- Add an extra bone onto the Ribbon
	# -- -- Add an extra Rigid between 0 and 3
	# -- Reweight stuff
	# -- Recreate the Rigid-Chains
	
	### Scarf: Make lats Rigid be flat and same alignment as parent << Actually do this in general
	#>> If on back, make bone offset face backwards too, properly extend to the end
	#>> 0.1 0.06 0.01
	
	### Fix these kinda materials which have their mirror halfs anchored on the same root bone, but only one half gets the rigid to it
	
	### Fix cf_m_hair_f_20_00*1 -- All vertices are on the center line, and the sides only have a little bit on the 2nd bone segment
	### Find out why cf_m_hair_f_20_00 is not broken -- everything is fine
	
	#######
	pass ##


## [Step 08] -- Cleanup Physics whose bones aren't weighted to any vertices. (Only works if ran together with 04 and/or 05)
def cleanup_free_bodies(pmx, outParam={}):
	local_state.setdefault(RBD__CLEANUP, {})
	#if local_state[RBD__CLEANUP] is None: return
	verbose = _verbose()
	
	##-- Maybe add an option to ask if they should stay
	
	printStage("Delete Physics used by pruned vertices")
	##-----
	from _prune_unused_vertices import newval_from_range_map, delme_list_to_rangemap
	
	## Collect all bones targeted by weights
	weighted_bones = set()
	for vert in pmx.verts:
		wtype  = vert.weighttype
		weight = vert.weight
		if wtype == 0: weighted_bones.add(weight[0])
		elif wtype == 1 or wtype == 3:
			# b1, b2, b1w
			# if b1w = 0, then skip b1
			if weight[2] != 0: weighted_bones.add(weight[0])
			# if b1w = 1, then skip b2
			if weight[2] != 1: weighted_bones.add(weight[1])
		elif wtype == 2 or wtype == 4:
			for i in range(4):
				if weight[i+4] != 0: weighted_bones.add(weight[i])
	
	## Map all (accessory) rigids as "boneIndex : [list of rigids attached to it]"
	rigid_dict = {}
	for idx,rigid in enumerate(pmx.rigidbodies):
		#if not rigid.name_jp.startswith("ca_slot"):
		if not re.search(r"^(ca_slot|cf_j_sk_)", rigid.name_jp): continue
		b = rigid.bone_idx
		if not b or b < 0: b = -1 ## Just to be safe.
		if b in rigid_dict: rigid_dict[b] += [idx]
		else: rigid_dict[b] = [idx]
	
	if verbose:
		#print("------- [rigid_dict]")
		#for x in rigid_dict: print(f"- {x}: {rigid_dict[x]}")
		print("------- [List of chains to check]")
		zz = local_state[RBD__CLEANUP]
		for x in zz: print(f"- {x}: {zz[x]}")
		print("-------------")
	
	## Collect rigidbodies
	rigid_dellist = []
	for (k,v) in local_state[RBD__CLEANUP].items():
		## Keep solo or short chains
		if v is None or len(v) == 0: continue
		if len(v) < 2:
			if len(v[0]) < 15: continue
			## Try walking the long list to verify the chains
			arr = {}
			tmp = v[0][0]
			for bone in v[0]:
				rr = rigid_dict[bone][0]
				if pmx.rigidbodies[rr].phys_mode == 0: tmp = rr
				arr.setdefault(tmp, [])
				arr[tmp] += [bone]
			v = arr.values()
			if verbose:
				print("-- Re-scanned long list:")
				print(v)
		##--- Scan the rest
		for _arr in v:
			## Ignore if any part of the chain has bone weights
			if any([x for x in _arr if x in weighted_bones]):
				if verbose: print(f"--- Bone-Chain {_arr} contains bone weights")
				continue
			## Otherwise collect all their rigids
			flat = util.flatten([rigid_dict[x] for x in _arr])
			if verbose: print(f"Remove {flat} from {_arr}")
			rigid_dellist += flat
	## Invalid rigids are always unweighted
	if -1 in rigid_dict:
		flat = util.flatten([rigid_dict[-1]])
		if verbose: print(f"Invalid Rigids: {flat}")
		rigid_dellist += flat
	
	if len(rigid_dellist) == 0:
		print(f"> Removed 0 rigidbodies and 0 joints.")
		return
	
	## Collect their joints too
	joint_dellist = []
	for idx,joint in enumerate(pmx.joints):
		if joint.rb1_idx in rigid_dellist: joint_dellist.append(idx)
		elif joint.rb2_idx in rigid_dellist: joint_dellist.append(idx)
		elif joint.rb1_idx == 0 and joint.rb2_idx == 0: joint_dellist.append(idx)
	
	## Delete both
	rigid_dellist = sorted(rigid_dellist)
	joint_dellist = sorted(joint_dellist)
	rigid_shiftmap = delme_list_to_rangemap(rigid_dellist)
	
	for i in reversed(joint_dellist): pmx.joints.pop(i)
	for i in reversed(rigid_dellist): pmx.rigidbodies.pop(i)
	msg = f"> Removed {len(rigid_dellist)} rigidbodies and {len(joint_dellist)} joints."
	print(msg)
	outParam["log_line"] = [msg]
	
	## Remap the rigid indices in the remaining joints
	for idx,joint in enumerate(pmx.joints):
		joint.rb1_idx = newval_from_range_map(joint.rb1_idx, rigid_shiftmap)
		joint.rb2_idx = newval_from_range_map(joint.rb2_idx, rigid_shiftmap)

def fix_slot_collisions(pmx):
	
	## Make certain Slots ignore the rigids of other things to avoid useless vibration
	
	#- Make Wrists (Armbands) ignore Arms
	#- Make chest decor ignore Jiggle physics
	#- Detangle certain Hair rigids from the skirt
	
	#- Make some things just ... idk, be fine?
	
	# Ask to cleanup useless rigids like Rings, ornaments, etc. with only root+one rigid
	
	######
	pass #

## [Mode 05]
def cleanup_free_things(pmx, _opt = { }):
	from _prune_unused_bones import prune_unused_bones, identify_unused_bones_base
	from _prune_unused_vertices import newval_from_range_map, delme_list_to_rangemap
	unusedBones = identify_unused_bones_base(pmx, False, True) + [-1, None]
	
	rgx = re.compile(r'^((cf_J_hair)|(ca_slot))')# or body.name_jp.startswith("cf_j_j_sk"):
	
	flag = _opt.get("flag", False)
	
	dupeBodies = {}
	
	rigid_dellist = []
	for d,body in enumerate(pmx.rigidbodies):
		#if body.name_jp.startswith("cf_hit"): continue		if body.group == 1: continue
		if rgx.match(body.name_jp) or flag:
			if body.bone_idx in unusedBones:
				#print(f"Adding [{d}]{body.name_jp} with Idx {body.bone_idx}")
				rigid_dellist.append(d)
	
	def __internal_cleanup(rigid_dellist):
		rigid_dellist2 = [-1] + rigid_dellist
		joint_dellist = []
		for d,joint in enumerate(pmx.joints):
			if joint.rb1_idx in rigid_dellist2 or joint.rb2_idx in rigid_dellist2:
				#print(f"Adding [{d}]{joint.name_jp} with RBs {joint.rb1_idx},{joint.rb2_idx}")
				joint_dellist.append(d)
		
		do_bodies = len(rigid_dellist) > 0
		do_joints = len(joint_dellist) > 0
		if do_bodies: print(f"Deleted {len(rigid_dellist):3} / {len(pmx.rigidbodies):3} rigidbodies")
		if do_joints: print(f"Deleted {len(joint_dellist):3} / {len(pmx.joints):3} joints")
		
		rigid_dellist = sorted(rigid_dellist)
		joint_dellist = sorted(joint_dellist)
		
		#if do_bodies:
		if do_joints:
			for f in reversed(joint_dellist): pmx.joints.pop(f)
		if do_bodies:
			rigid_shiftmap = delme_list_to_rangemap(rigid_dellist)
			for f in reversed(rigid_dellist): pmx.rigidbodies.pop(f)
			for idx, joint in enumerate(pmx.joints):
				joint.rb1_idx = newval_from_range_map(joint.rb1_idx, rigid_shiftmap)
				joint.rb2_idx = newval_from_range_map(joint.rb2_idx, rigid_shiftmap)
		
		if (do_bodies or do_joints): prune_unused_bones(pmx, False)
	__internal_cleanup(rigid_dellist)
	##---- Unless deleting them, print afterwards
	for d,body in enumerate(pmx.rigidbodies):
		if rgx.match(body.name_jp):
			dupeBodies.setdefault(body.bone_idx, [])
			dupeBodies[body.bone_idx].append(d)
	msgs = []; rigid_dellist = []
	for k,v in dupeBodies.items():
		if len(v) == 2 and (v[1] == (v[0]+1)): continue
		if len(v) > 1:
			rigid_dellist.append(v[0])
			msgs.append(f"[{k}]: {v}")
	if len(msgs) > 0:
		msg = "\n>\t".join(["The following bones have duplicate rigidbodies:"] + msgs)
		flag = _opt.get("fullClean", False)
		if not flag: print(msg)
		if _opt.get("fullClean", False) or util.ask_yes_no("Clean them up (cleans the factory Rigids, keeps the new ones)", "n"):
			__internal_cleanup(rigid_dellist)

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
##:: CM3D2 Hair
## ca_slot
## -- N_move >> NUMBER=32  // no, NUMBER is not count(bones)
## -- -- joints.009 >> [all]: 00W_J._yure_hair:(_soft)?:_R06g:(.001, 002)?
## -- -- rigidbodies.018
## -- -- 32_arm
## -- -- -- Bone_face
## -- -- -- -- Hair_F >> Hair_F_end
## -- -- -- -- Hair_R >> [chains]: yure_hair:(_soft)?:(_hXX)?:R02a,b,c,...g,g_end
## -- -- -- [chains]: yure_hair:(_soft)?:R02a,b,c,...g,g_end
##  ---> 2x _hXX, 3x neither, 3x _soft (on the example)
## -- N_hairback00 >> 32_mesh
######

## [Mode 02]
##--- Hook a chain of RigidBodies to a static Body and anchor it to [head_body]
##
def patch_bone_array(pmx, head_body, arr, name, grp, overrideLast=True):
	"""
	Hook a chain of RigidBodies to a static Body and anchor it to [head_body]

	Chain-Actions:
	:: Return if [head_body is None] & root was already added
	:: Bind supplied bones
	:: Create root Rigid as "[name]_r"
	:: Call [AddBodyChainWithJoints]
	:: if nothing changed, remove root rigid & return
	:old: If [head_body] provided, connect first rigid to it, else remove first joint
	:new: Connect first new Joint to [head_body] (or root if None)
	:: Make first two bodies static because of MMD
	
	overrideLast :: Overwrite settings of last bone to a TailBone
	
	"""
	if True: ## To keep the History aligned
		if check_no_dupes(pmx, find_rigid, name+"_r"):
			if DEBUG: print(f"Already added a bone chain for {name}")
			return
		util.bind_bone(pmx, arr, overrideLast)
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
		if (new_bodies == 0 and new_joints == 0):
			## Cleanup extra root rigid if nothing was added
			del pmx.rigidbodies[num_bodies]
			return
		
		PREVIOUS = True
		## Connect with head rigid
		if PREVIOUS:
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
		else:# UNTESTED -- Provide the Root Rigid when not head
			if head_body is None or head_body < 0:
				head_body = root #del pmx.joints[num_joints]
			else:
				## Unbind unused root rigid to clean it up later.
				pmx.rigidbodies[root].bone_idx = 0
			joint = pmx.joints[num_joints]
			joint.rb1_idx = head_body
			joint.rb2_idx = num_bodies
			joint.movemin = [ 0.0, 0.0, 0.0]
			joint.movemax = [ 0.0, 0.0, 0.0]
			joint.rotmin  = [ 0.0, 0.0, 0.0]
			joint.rotmax  = [ 0.0, 0.0, 0.0]
		
		########### If using shorter chains
		## Make first body static
		body = pmx.rigidbodies[num_bodies]
		body.phys_move_damp = 0.999
		body.phys_rot_damp  = 0.9999
		## 
		if new_bodies > 1:
			### MMD needs two fixated rigids or one central anchored by multiple
			pmx.rigidbodies[num_bodies+1].phys_mode = 0
			##Copy Rot of 2nd last to last
			last = pmx.rigidbodies[-1]
			_rot = pmx.rigidbodies[-2].rot
			pmx.joints[-1].rot = _rot
			last.rot     = _rot
			last.pos     = pmx.bones[last.bone_idx].pos
			last.size[0] = 0.1
			#- Make it loose velocity faster
			last.phys_mass = 2
			last.phys_move_damp = 0.999
			last.phys_rot_damp  = 0.9999
		adjust_collision_groups(grp, pmx.rigidbodies[num_bodies:])
##########
	pass# To keep trailing comments inside

## [Step 03]
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
	printStage("split_merged_materials")
	verbose = _verbose()
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
	
	if DEBUG: print("----")
	
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
	if last in [-1,None]: last = find_bone(pmx, "KKS_Colliders_cf_j_root", False)
	if last in [-1,None]:#>> This branch is still untested
		## This means the model is already cleaned up. This one exists in both.
		last = find_bone(pmx, "cf_s_waist01", False)
		if last not in [-1,None]:
			tmp = [x for x in slots if x > last]
			# if there are any slots (an_*), get the last of it
			if len(tmp) > 0:
				try:
					tmp = get_children_map(pmx, tmp, True)[-1]
				##>> Avoid taking one of those bones we try to fix
					if tmp[-1]+1 == len(pmx.bones): last = tmp[-2]
					else: last = tmp[-1]
				except: last = tmp[0]
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
	if DEBUG: print("----")
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
		util.bind_bone(pmx, arr, True)
		if not reweight_bones(pmx, first_chain, arr, int(re.search(r"ca_slot(\d+)", name)[1]), False):
			if not chain_matched: first_chain = None
		else: chain_matched = True

## [Mode 03]
def split_rigid_chain(pmx, arr=None):
	verbose = _verbose()
#>	Move Rigid to linked Bone
	# Ask for list of Rigids to fix (only the first)
	if arr is None:
		arr = core.MY_GENERAL_INPUT_FUNC(util.is_csv_number, "List of Rigids (comma separated)" + f"?: ")
	slot_map = {}
	# Process list
	def __split_rigid_chain(idx):
		# Get Rigid
		rigid = pmx.rigidbodies[idx]
		# Get RigidBody1 (Rigid.Id+1)
		rigid2 = pmx.rigidbodies[idx+1]
		
		# Get Linked Bone of Rigid
		bone = pmx.bones[rigid.bone_idx]
		
		# Set Rigid.Position to Bone.Position
		rigid.pos = bone.pos
		# Set Rigid.Rotation to [0 0 0]
		rigid.rot = [0, 0, 0]
		# Set Rigid.Size to [0.1 -0.1]
		rigid.size = [0.1, -0.1, 0]
		
		# Store Bone.LinkTo as BoneLink
		tail = bone.tail
		if bone.tail_usebonelink == False:
			if verbose: print(f"{idx} is already an end (Bone {rigid.bone_idx} had no link)")
			return
		
		# Set RigidBody1.Type to Green
		old = rigid2.phys_mode
		rigid2.phys_mode = 0
		# Set Bone.LinkTo as [Offset: 0 0 -0.1]
		bone.tail_usebonelink = False
		bone.tail = [0, 0, -0.1]
		
		# Find Rigid linked to BoneLink (RigidBody2)
		rigid3 = None
		span = util.get_span_within_range(len(pmx.rigidbodies), idx-30, idx+30)
		for r in pmx.rigidbodies[span[0]:span[1]]:
			if r.bone_idx == tail:
				rigid3 = r
				break
		if rigid3 == None:
			print(f"{idx}: Could not find any rigid linked to bone {tail}, cannot verify joints")
			if DEBUG: print(f"> rbd={idx} with bone={rigid.bone_idx} linked to {tail}")
			return
		idx3 = find_rigid(pmx, rigid3.name_jp)
		## If we found one, set that instead, and revert the previous.
		rigid2.phys_mode = old
		rigid3.phys_mode = 0
		
		# Get responsible List of Joints
		try:    prefix = re.search("(ca_slot\d+)", rigid.name_jp)[1]
		except: prefix = rigid.name_jp.split(':')[0]
		if prefix in slot_map: joints = slot_map[prefix]
		else:
			joints = [x for x in pmx.joints if x.name_jp.startswith(prefix)]
			slot_map[prefix] = joints
		##-- Refresh Rotation to previous segment
		for j in joints:
			if j.rb2_idx == idx:
				if j.rb1_idx is None: break
				parRig = pmx.rigidbodies[j.rb1_idx]
				if parRig:
					rigid.rot = parRig.rot
					j.rot = parRig.rot
					break
		
		# Find Joint that connects Rigid & RigidBody1
		joint = None
		for j in joints:
			if j.rb1_idx == idx and j.rb2_idx == idx3:
				joint = j
				break
		if joint == None:
			if verbose: print(f"{idx}: Not connected by joint with {idx3}, so no need to change any.")
			return
		
		# Set A to RigidBody2
		joint.rb1_idx = idx3
	
	#[int(x.strip()) for x in arr.split(',')]
	if type(arr) is str:     [__split_rigid_chain(int(x.strip())) for x in arr.split(',')]
	elif type(arr) is list:  [__split_rigid_chain(int(x)) for x in arr]
	else: raise Exception(f"Unsupported type {type(arr)}")
	return arr

def shorter_skirt_rigids(pmx): pass
	# Determine how much shorter it should be (allow % or total Y-height)
	# Collect all Rigids
	# Collect all Joints
	# Collect all Bones(?)
	# Shrink all Rigids
	# Move all Joints
	# Move the Bones(?)

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
		if re.search(r"\[:AccId:\] \d+", m.comment):
			tmp = int(re.search(r"\[:AccId:\] (\d+)", m.comment)[1])
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
def AddBodyChainWithJoints(pmx, boneIndex: List[int], mode: int, radius: float, uvFlag: bool, name, group):
	"""
	Creates:
	:: @AddBaseBody()
	:: @add_joint() between each two chain segments with ROT:[-10:10, -5:5, -10:10]
	:: Assign rigidbodies to enclosed joint
	"""
	body_num: int = len(pmx.rigidbodies)
	AddBaseBody(pmx, boneIndex, mode, radius, uvFlag, name, group)
	added_bodies: int = len(pmx.rigidbodies) - body_num
	if (added_bodies <= 0):
		print(f"Did not add any chains for {name}, might already exist!")
		return
	
	dictionary = { body.bone_idx: i for (i, body) in enumerate(pmx.rigidbodies) if body.bone_idx in boneIndex }
	# Set first body to [Static] to avoid fluid
	pmx.rigidbodies[dictionary[boneIndex[0]]].phys_mode = 0
	
	dictionary2 = {}
	
	def isVisible(_bone): return pmxBone != None and (not uvFlag or pmxBone.has_visible)
	
	for bone_idx in boneIndex:
		# Don't add more Joints than bodies
		if len(dictionary) == len(dictionary2): break
		# Don't add Joint on last bone
		#if boneIndex[-1] == bone_idx: break

		pmxBone = pmx.bones[bone_idx]
		if (isVisible(pmxBone)):
			pmxJoint = pmx.joints[add_joint(pmx)]
			pmxJoint.name_jp = name + ":" + pmxBone.name_jp
			pmxJoint.pos = pmxBone.pos
			
			num3: Vector3 = Vector3(10, 5, 10)
			##--- Regen from PMXExport does [-10 to 10, -5 to 5, -10 to 10] for Ponytail
			pmxJoint.rotmax = num3.ToList()   #[  0.0,   0.0,   0.0] #Vector3(num3, num3, num3).ToList();
			pmxJoint.rotmin = (-num3).ToList()#[  0.0,   0.0,   0.0] #-pmxJoint.rotmax;
			##--- idk actually know what these do, but it makes it smoother
			pmxJoint.movespring = [500, 100, 20]
			pmxJoint.rotspring  = [250, 50, 10]
			
			dictionary2[bone_idx] = len(pmx.joints) - 1

	### @todo: [?] add hidden bone with [0, 0, -1] as pointer
	# TODO: If called directly (with only two bones), joints are always bound to rb = 0
	for key in dictionary.keys():
		pmxBone2 = pmx.bones[key]
		if key not in dictionary2: continue
		
		if pmxBone2.parent_idx not in boneIndex: continue
		#if pmxBone2.tail_usebonelink:
		#	if pmxBone2.tail not in boneIndex: continue
		pmxJoint2 = pmx.joints[dictionary2[key]]
		pmxJoint2.rb1_idx = dictionary[pmxBone2.parent_idx]
		pmxJoint2.rb2_idx = dictionary[key]
		pmxJoint2.rot = pmx.rigidbodies[dictionary[key]].rot

	if radius <= 0.0:
		## Reduce height by the size of a Joint, relative to the radiius
		# --- Otherwise the ends overlap too much
		for bodyX in pmx.rigidbodies[body_num:]:
			#msg = f"Size: {bodyX.size[1]}"
			bodyX.size[1] -= (bodyX.size[0]*10) * 0.2 ## 0.1 are exactly 0.2
			#print(msg + f" -> {bodyX.size[1]}")
	#######
	pass ##

##-- Adds the RigidBodies
def AddBaseBody(pmx, boneIndices: List[int], mode: int, radius: float, uvFlag: bool, name, group):
	"""
	:boneIndices: -- List of Bones to combine
	:mode:        -- phys_mode to set on all bodies
	:radius:      -- Set explicit radius
	:uvFlag:      -- if True, ignore hidden bones
	"""
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
			x: float = radius
			if (radius <= 0.0): x = num3 * 0.2
			body.size = Vector3(x, num3, 0.0).ToList()
			body.pos = zero.ToList()
			m: Matrix = GetPoseMatrix_Bone(pmx, idx)
			body.rot = MatrixToEuler_ZXY(m).ToDegree().ToList()
		else:
			body = pmx.rigidbodies[add_rigid(pmx)]
			body.shape = 0 # Sphere
			x2: float = radius
			if (radius <= 0.0): x2 = 0.2
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

def change_phy_mode(pmx, _arr, mode):
	if (find_rigid(pmx, _arr[0]) is None): return
	for name in _arr:
		body_idx = find_rigid(pmx, name, False)
		if body_idx is not None: pmx.rigidbodies[body_idx].phys_mode = mode

def get_bone_or_default(pmx, name_jp, idx, default):
	tmp = find_bone(pmx, name_jp, False)
	if tmp != -1:
		return pmx.bones[tmp].pos[idx]
	return default

def get_collision_group(group): ## returns [group, mask]
	mask = -1
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
	return [group, mask]
def merge_collision_groups(groups): ## returns mask
	mask = 65535
	groups.sort(reverse=True)
	for group in set(groups): # Ensure unique
		if group in range(1,17): mask = mask - (1 << group - 1)
	return mask
## TODO: Verify uses and merge these three properly later
def adjust_collision_groups(grp, bodies=[]): ## For a given group, adjust colliders to ignore conflict clusters
	mask = None
	# GRP_BODY    :1: 
	if grp == GRP_BODY:                   ## [1] -- Solid for everything
		mask = 65535
	if grp == GRP_CHESACC:                ## [5] -- Chest accessories should ignore Chest Physics
		mask = merge_collision_groups([GRP_CHESACC, GRP_CHEST_A, GRP_CHEST_B]) ## 5,8+14
	if grp in [GRP_CHEST_A, GRP_CHEST_B]: ## [8 or 14] -- Chest should ignore Body, all Accs (Hair, Body, Chest), SecondaryChest
		mask = merge_collision_groups([GRP_BODY, GRP_ARMS, GRP_CHEST_B, GRP_HAIRACC, GRP_CHESACC, GRP_BODYACC]) #24560 ## (1 2 14) + (3 5 16)
	if grp in [GRP_WAIST, GRP_TAIL]:      ## [13, 15]: Prevent conflict between Tail / Waist with Skirt
		mask = merge_collision_groups([GRP_TAIL, GRP_WAIST, GRP_SKIRT]) ## 13 + 15 << 4
	if grp in [GRP_SKIRT]:                ## [4]: Prevent conflict between Skirt and Tail
		mask = merge_collision_groups([GRP_TAIL, GRP_SKIRT]) ## 4 & 13
	
	# GRP_DEFHAIR :3: Currently only itself
	# GRP_SKIRT   :4: Currently only itself
	# GRP_HAIRACC --> Hair, Body ?
	# GRP_BODYACC :16: Currently only itself --> Hair, Body ?
	
	if mask is None: mask = merge_collision_groups([grp]) ### Only ignore self
	for body in bodies: body.nocollide_mask = mask
	return mask

def perform_on_all_weights(pmx, cb):
	for vert in pmx.verts:
		if vert.weighttype == 0: cb(vert, 0)
		elif vert.weighttype == 1: cb(vert, 0); cb(vert, 1)
		elif vert.weighttype == 2:
			cb(vert, 0); cb(vert, 1); cb(vert, 2); cb(vert, 3)
		else:
			raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))
def perform_on_weights__(vert, cb):
	if vert.weighttype == 0: cb(vert, 0)
	elif vert.weighttype == 1: cb(vert, 0); cb(vert, 1)
	elif vert.weighttype == 2:
		cb(vert, 0); cb(vert, 1); cb(vert, 2); cb(vert, 3)
	else:
		raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))
def perform_on_weights(vert, cond, newIdx):
	if vert.weighttype == 0:
		if(cond(vert.weight[0])): vert.weight[0] = newIdx
	elif vert.weighttype == 1:
		if(cond(vert.weight[0])): vert.weight[0] = newIdx
		if(cond(vert.weight[1])): vert.weight[1] = newIdx
	elif vert.weighttype == 2:
		if(cond(vert.weight[0])): vert.weight[0] = newIdx
		if(cond(vert.weight[1])): vert.weight[1] = newIdx
		if(cond(vert.weight[2])): vert.weight[2] = newIdx
		if(cond(vert.weight[3])): vert.weight[3] = newIdx
	else:
		raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))


#----
def printStage(text): print(f"-------- Stage '{text}' ...")
def printSubStage(text): print(f"---- {text}")
#----

def print_map(_mapObj):
	print("--->")
	for x in _mapObj.keys(): print(f"{x}: {_mapObj[x]}")
	print("<---")

def get_parent_map(pmx, bones):
	"""
	Arranges @bones into a dict of the form { @bone: [ancestors in @bones] }
	@bones:     List[int] or Range
	@return:    Dict[int, List[int]]
	"""
	boneMap = { -1: [], 0: [] }
	try:
		for bone in sorted(bones):
			if bone in boneMap: continue
			p = bone
			while p not in boneMap: p = pmx.bones[p].parent_idx
			if p not in [0,-1]: boneMap[bone] = boneMap[p] + [p]
			else:               boneMap[bone] = []
		del boneMap[-1]
		if 0 not in bones: del boneMap[0]
	except Exception as ex:
		print("[!!] error with " + str(p))
		raise ex
	return boneMap

def get_delta_map(pmx, boneMap, relative=True):
	vecDict = {}
	for bone in boneMap.keys():
		b = pmx.bones[bone]
		vector2 = Vector3.FromList(pmx.bones[b.parent_idx].pos)
		target  = Vector3.FromList(pmx.bones[bone].pos)
		## Reduce delta in relation to the already added delta from parent bones, accumulative
		delta = (target - vector2)
		if relative:
			for idx in boneMap[bone]: delta -= vecDict.get(idx, Vector3.Zero())
		vecDict[bone] = delta
	return vecDict

def get_children_map(pmx, bones, returnIdx=False, add_first=True, find_all=True):
	"""
	Arranges @bones into a dict of the form { "name": [list of children] }
	
	@bones:     Can be int or List[int]. Defaults to range(pmx.bones) if None
	@returnIdx: <dict.keys> will consist of the boneIndices instead
	@add_first: Adds @bone.index as first entry in each <dict.value>
	@find_all:  <dict.value> will collect from all existing bones 		<UNTESTED>
	"""
	if bones == None: bones = range(len(pmx.bones))
	elif type(bones) is not list: bones = [bones]
	par_map = get_parent_map(pmx, range(len(pmx.bones)) if find_all else bones) # Reusing Range causes an issue I think...
	bone_map = {}    ## dict of { "name": [bone, list of children] }
	for bone in bones:
		bone_key = pmx.bones[bone].name_jp
		children = [k for k in par_map.keys() if bone in par_map[k]]
		if returnIdx: bone_key = bone
		if add_first: children = [bone] + children
		bone_map[bone_key] = children
	return bone_map


def check_no_dupes(pmx, func, name, outParam={}):
	""" Checks if the given func [Finder from UTIL] reports existence or not. 
	:outParam: -- Store the index as "result" into this object
	"""
	if not local_state.get(OPT__NODUPES, False): return False
	idx = func(pmx, name, False)
	outParam["result"] = idx
	return idx != -1

def add_bone_default(pmx, name): ## Find and return this bone, or add it if missing.
	idx = find_bone(pmx, name, False)
	bone_idx = idx if idx > -1 else add_bone(pmx, name)
	return pmx.bones[bone_idx]

def add_bone(pmx,
			 name_jp: str = "New Bone1",
			 name_en: str = "",
			 pos: List[float] = [0,0,0],              ## "Position:"
			 parent_idx: int = -1,                    ## "P-Bone:"
			 deform_layer: int = 0,                   ## "Deform:"
			 deform_after_phys: bool = False,         ## [After Ph.]
			 has_rotate: bool = True,                 ## [ROT]
			 has_translate: bool = False,             ## [MVN]
			 has_visible: bool = True,                ## [VIS]
			 has_enabled: bool = True,                ## [Enable]
			 has_ik: bool = False,                    ## [IK]
			 tail_usebonelink: bool = False,          ## False=(Offset) \\ True=(Bone)
			 tail: Union[int, List[float]] = [0,0,0],
			 # NOTE: either int or list of 3 float, but always exists, never None
			 inherit_rot: bool = False,               ## [Rot+]
			 inherit_trans: bool = False,             ## [Mov+]
			 has_fixedaxis: bool = False,             ## [Axis Limit:]
			 has_localaxis: bool = False,             ## [Local Axis:]
			 has_externalparent: bool = False,        ## [External:]
			 # optional/conditional
			 inherit_parent_idx: int=None,            ## "Parent:"  --- [L] is missing 
			 inherit_ratio: float=None,               ## "Ratio:"   Apply <Parent> times this to own
			 fixedaxis: List[float]=None,             ## "0 0 0"
			 localaxis_x: List[float]=None,           ## "X: 1 0 0"
			 localaxis_z: List[float]=None,           ## "Z: 0 0 1"
			 externalparent: int=None,                ## "Parent Key:"
			 ik_target_idx: int=None,                 ## "Target:"
			 ik_numloops: int=None,                   ## "Loop:"
			 ik_angle: float=None,                    ## "Angle:"
			 ik_links=None,                           ## < Link >
			 _solo=False
			 ):
	args = locals()
	del args["pmx"]
	del args["_solo"]
	if name_en == "": args["name_en"] = name_jp
	if _solo: return pmxstruct.PmxBone(**args)
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

##############

##: Create a morph that transforms a model from one into the other only based on Vertices.
#> Use [do_mode_2] to include Bones. -- The only use for this is to construct small static Morphs for VRM
def Internal_MorphVertexDelta(pmx, input_filename_pmx):
	import kkpmx_core as kkcore
	(pmx1, input_filename_pmx1) = (pmx, input_filename_pmx)
	# load the morphed pmx as pmx2
	(pmx2, input_filename_pmx2) = util.main_starter(None, "Input the morphed PMX File")
	
	lOne = len(pmx1.verts)
	lTwo = len(pmx2.verts)
	
	if lOne != lTwo:
		bigger = "1st" if lOne > lTwo else "2nd"
		raise Exception(f"Models must be exactly equal for this to work! ({bigger} is bigger)")
	
	def invert(x): return (-(Vector3.FromList(x))).ToList()
	
	##############
	morphList = []
	morphList_rev = []
	def add_morph(idx: int, vert_idx: int, abs_idx=False): ## @vector = pos of @idx in pmx2 \\ @vert_idx in pmx1
		big_vert = pmx2.verts[idx]
		big_pos  = Vector3.FromList(big_vert.pos)
		big_idx  = big_vert.weight[0]
		#big_bone = Vector3.FromList(pmx3.bones[big_idx].pos)
		
		sma_vert = pmx1.verts[vert_idx]# if abs_idx else vertices[vert_idx]
		sma_pos  = Vector3.FromList(sma_vert.pos)
		sma_idx  = sma_vert.weight[0]
		#sma_bone = Vector3.FromList(pmx1.bones[sma_idx].pos)

		delta = (big_pos) - (sma_pos)
		kkcore.__append_vertexmorph(morphList_rev, idx, invert(delta.ToList()), None) ## Morphed into Unmorphed
		kkcore.__append_vertexmorph(morphList, idx, delta.ToList(), None) ## Unmorphed into Morphed
	##############
	
	def match_uv(src, dst):
		prec = 4
		return round(src[0], prec) == round(dst[0], prec) and round(src[1], prec) == round(dst[1], prec)
	wrong_vert = []
	
	# Verify that each vertex has roughly the same UV-Coordinate
	for idx in range(len(pmx2.verts)):
		vert = pmx2.verts[idx]
		if match_uv(pmx1.verts[idx].uv, vert.uv):
			add_morph(idx, idx, True)
		else: wrong_vert.append(idx)
	
	if len(wrong_vert) > 0: raise Exception(f"Found inequal Vertices at {wrong_vert}!")
	
	# write model
	pmx2.morphs.append(pmxstruct.PmxMorph("VertexMorph", "VertexMorph", 4, 1, morphList_rev))
	kkcore.end(pmx2, input_filename_pmx2, "_vmorph", [f"Added VertexMorph back into {input_filename_pmx1}"])
	
	pmx1.morphs.append(pmxstruct.PmxMorph("VertexMorph", "VertexMorph", 4, 1, morphList))
	kkcore.end(pmx1, input_filename_pmx1, "_vmorph", [f"Added VertexMorph towards {input_filename_pmx2}"])
	
	pass


###########
if __name__ == '__main__': util.main_starter(run)