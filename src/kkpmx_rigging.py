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
OPT__NODUPES = "no_dupes"

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

[Issues]:
- In rare cases, the Skirt Rigids named 'cf_j_sk12' point into the wrong direction. Simply negate the [RotX] value on the 5 segments.

[Options] '_opt':
- "mode":
-  - 0 -- Main mode
-  - 1 -- Reduce chest bounce
-  - 2 -- Rig a list of bones together (== fix unrecognized chain starts)
-  - 3 -- Cut morph chains (== fix unrecognized chain ends)
"""
	### Add some kind of list chooser & ask for int[steps] to execute
	import kkpmx_core as kkcore
	global_state["moreinfo"] = moreinfo or DEBUG
	modes = _opt.get("mode", -1)
	choices = [("Regular Fixes", 0), ("Reduce Chest bounce",1), ("Rig Bone Array", 2), ("Split Chains", 3)]
	modes = util.ask_choices("Choose Mode", choices, modes)
	if modes == 3:
		arr_log = ["Modified Rigging (Split Chains)"]
		arr_log += [split_rigid_chain(pmx)]
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", arr_log)
	if modes == 1:
		#rig_hair_joints(pmx)
		#return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", "Modified Rigging (Hair only)")
		#transform_skirt(pmx)
		#fix_skirt_rigs(pmx)
		#rig_rough_detangle(pmx)
		msg = "\n> ".join([""] + adjust_chest_physics(pmx))
		return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", "Modified Rigging (Chest only)" + msg)
	if modes == 0:
		adjust_body_physics(pmx)
		transform_skirt(pmx)
		split_merged_materials(pmx, None)
		rig_hair_joints(pmx)
		rig_other_stuff(pmx)
		rig_rough_detangle(pmx)
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

## [Step 01]
def adjust_body_physics(pmx):
	print("--- Stage 'Adjust Body Physics'...")
	mask = 65535 # == [1] is 2^16-1

	if find_bone(pmx, "左胸操作", False):
		chest_mask = 24560 ## 1 2 3 4 14 16
		def tmp(name):
			idx = find_rigid(pmx, name, False)
			if idx != -1: pmx.rigidbodies[idx].nocollide_mask = chest_mask
		tmp("左胸操作");     tmp("右胸操作")
		tmp("左AH1");       tmp("右AH1")
		tmp("左AH2");       tmp("右AH2")
		tmp("左胸操作接続"); tmp("右胸操作接続")
		tmp("左胸操作衝突"); tmp("右胸操作衝突")

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
		rot  = [0, 0, 90]
		
		add_rigid(pmx, name_jp="RB_shoulder_L", pos=pos, size=size, bone_idx=find_bone(pmx, "左肩"), rot=rot, **commonPill)
		neck_minX = minX
		
		####
		## Left arm
		#-- between cf_d_arm01_L & 左ひじ \\ [rad]: cf_s_elboback_L - cf_s_elbo_L (out)
		rIn  = pmx.bones[find_bone(pmx, "cf_s_elboback_L")].pos[2]
		rOut = pmx.bones[find_bone(pmx, "cf_s_elbo_L")].pos[2]
		lenIn = pmx.bones[find_bone(pmx, "cf_s_shoulder02_L")].pos[0]
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
		lenIn = pmx.bones[find_bone(pmx, "cf_s_shoulder02_R")].pos[0]
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

def fix_skirt_rigs(pmx):
	def replaceBone(target):
		if target == 202: return 192
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
	
	print("--- Stage 'Transform Skirt'...")
	moreinfo = global_state["moreinfo"]
	
	rotY = 0
	rigids = []
	for rigid in pmx.rigidbodies:
		## Change width of all but [05] to XX (start at 0.6)
		if not re.match(r"cf_j_sk", rigid.name_jp): continue
		rigids.append(rigid)
		m = re.match(r"cf_j_sk_(\d+)_(\d+)", rigid.name_jp)
		
		## Unify the Rotation for all lines (some assets mess them up)
		if int(m[2]) == 0: rotY = rigid.rot[1]
		else: rigid.rot[1] = rotY
		
		rigid.phys_mass = 2
		rigid.phys_move_damp = 0.5
		rigid.phys_rot_damp = 0.5
		rigid.phys_repel = 0
		rigid.phys_friction = 0
		if int(m[2]) == 5: continue
		
		## Change mode to 1 & set depth to 0.02
		rigid.shape = 1
		rigid.size[0] = 0.6
		rigid.size[2] = 0.02
		
		#-- Make front / back pieces a bit wider
		if int(m[1]) in [0,4]: rigid.size[0] = 0.7
	
	if len(rigids) == 0:
		print("> No Skirt rigids found, skipping")
		return
	elif len(rigids) > 48:
		print("> Skirt already rigged, skipping")
		return
	
	## Create more rigids inbetween
	
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
	
	if moreinfo: print("-------- Physics")
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
	
	################
	## Same for joints
	
	jlst = chunk(joints[0:8*5], 5)
	joint_dict = {
		"10": zip(jlst[0], jlst[1]), "12": zip(jlst[1], jlst[2]),
		"23": zip(jlst[2], jlst[3]), "34": zip(jlst[3], jlst[4]),
		"45": zip(jlst[4], jlst[5]), "56": zip(jlst[5], jlst[6]),
		"67": zip(jlst[6], jlst[7]), "70": zip(jlst[7], jlst[0]),
	}
	## Get pos,rot,size of both, and set the average as new
	if moreinfo: print("-------- Joints")
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
	if moreinfo: print("-------- Side Joints")
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

## [Step 04]
def rig_hair_joints(pmx): #--- Find merged / split hair chains --> apply Rigging to them
	print("--- Stage 'Rig Hair'...")
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
	
	#print(f"Limit: {limit}")

	global_state[OPT__HAIR] = True
	################################
	_patch_bone_array = lambda x,n: patch_bone_array(pmx, head_body, x, n, grp=3)
	__rig_acc_joints(pmx, _patch_bone_array, _limit)

## [Common of 04+05]
def __rig_acc_joints(pmx, _patch_bone_array, limit):
	"""
	:: private method as common node for both normal and hair chains
	"""
	
	### At least this exists for every accessory
	__root_Name = "N_move"
	bones = [i for (i,b) in enumerate(pmx.bones) if b.name_jp.startswith(__root_Name)]
	#print(bones)
	if len(bones) == 0:
		print("No acc chains found to rig.")
		return
	
	global_state[OPT__NODUPES] = True
	################################
	for bone in bones:
		##[Hair] Ignore the groups not anchored to the head
		##[Rest] Ignore the hair groups
		if limit(pmx.bones[bone].pos[1]): continue
		
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
		
		## These exist just to make it... less complicated
		def finder(name): return [x for x in root_arr0 if pmx.bones[x].name_jp.startswith(name)]
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
		
		
		##################
		#-- CM3D2 Handling -- because it contains [joints.xxx]
		root_arr1 = finder("Bone_Face")
		if any(root_arr1):
			##[C] Descend onto Hair_R etc.
			arr = descend_first(root_arr1) ## [Bone_Face -> all children]
			##[C] Reduce to children but keep first -- it contains some root weights
			##[A] Reduce to the chains whose first bone has "AS01_J_kami" as parent
			child_arr = []
			hair = finder2("Hair_F", arr)
			if len(hair) > 0: child_arr += get_direct_chains(arr, hair[0])
			hair = finder2("Hair_R", arr)
			if len(hair) > 0: child_arr += get_direct_chains(arr, hair[0])
			#child_arr = get_direct_chains(arr, arr[0])
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		##################
		#-- AS01 Handling  -- contains "SCENE_ROOT"
		root_arr1 = finder("AS01_N_kami")
		if any(root_arr1):
			##[C] Descend onto Hair_R etc.
			arr = descend_first(root_arr1)
			##[C] Reduce to children but keep first -- it contains some root weights
			##[A] Reduce to the chains whose first bone has "AS01_J_kami" as parent
			child_arr = get_direct_chains(arr, arr[0])
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		##################
		#-- Regular Joint Handling
		root_arr1 = finder("root") + finder("joint")
		if any(root_arr1):
			## Get parent of first bone
			first_parent = pmx.bones[root_arr1[0]].parent_idx
			child_arr = get_direct_chains(root_arr0, first_parent)
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		##################
		#-- p_cf_hair && cf_N_J_ Handling
		root_arr3 = finder("cf_N_J_")
		if any(root_arr3):
			continue ## Already pre-rigged ? --> Or simply add [Group 16] to pre-rigged ones
			arr = descend_first(root_arr3)
			child_arr = get_direct_chains(arr, arr[0])
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		#######################
		# Common Accs: Use all that have "name" as parent
		##################
		#-- Common hair
		root_arr2 = finder("cf_J_hairB_top")
		#-- [acs_j_top]: Cardigan -- needs more arm rigids
		#-- [j_acs_1]: acs_m_idolwaistribbon -- 
		root_arr2 += finder("acs_j_top") + finder("j_acs_1") + finder("acs_j_usamimi_00")
		if any(root_arr2):
			arr = descend_first(root_arr2)
			child_arr = get_direct_chains(arr, root_arr2[0])
			for i,arr in enumerate(child_arr): _patch_bone_array(arr, name+'_'+str(i))
			continue
		#######################
		arr = root_arr0
		if len(arr) == 0: continue
		if pmx.bones[arr[0]].name_jp.startswith("All_Root"): continue
		arr = [x for x in arr if not pmx.bones[x].name_jp.startswith("o_")]
		if len(arr) < 2: continue
		
		_patch_bone_array(arr, name)
	global_state[OPT__NODUPES] = False
####################
	pass

## [Step 05]
def rig_other_stuff(pmx):
	print("--- Stage 'Rig non hair stuff'...")
	## Get reference point for discard
	try: limit = pmx.bones[find_bone(pmx, "胸親", False)].pos[1]
	except: limit = 0.0
	_limit = lambda i: i > limit
	_patch_bone_array = lambda x,n: patch_bone_array(pmx, None, x, n, grp=16)
	__rig_acc_joints(pmx, _patch_bone_array, _limit)

### Annotation
# Maybe rig Tongue: weighted to [cf_J_MouthCavity] << cf_J_MouthBase_rx < ty < cf_J_FaceLow_tz < Base < J FaceRoot < J_N < p_cf_head_bone < cf_s_head
#>> But these exist: cf_s_head < cf_j_tang_01 < 02 < 03 < 04(< 05(< L+R), L+R), L+R -- Quite some below the mesh though

## [Step 06]
def rig_rough_detangle(pmx):
	print("--- Stage 'Detangle some chains'...")
	print("> aka perform [Mode: 3] for some obvious cases")
	## Get all rigging starting with ca_slot
	def collect(item):
		idx = item[0]
		rig = item[1]
		if not rig.name_jp.startswith("ca_slot"): return False
		if idx == len(pmx.rigidbodies) - 1: return False
		
		## "ca_slot05_0:joint1-3" > "ca_slot05_0:joint2-1"
		m = re.search(r"joint(\d+)-(\d+)", rig.name_jp)
		if m:
			n = re.search(r"joint(\d+)-\d+", pmx.rigidbodies[idx+1].name_jp)
			if not n: return False
			return int(m[1]) < int(n[1])
		
		## "left+1,2,3..." > "right+1,2,3"
		lst = "left|right|front|back|head|body"
		m = re.search(r"(?:"+lst+r")[LR]?(\d)$", rig.name_jp)
		if m:
			n = re.search(r"(?:"+lst+r")[LR]?(\d)$", pmx.rigidbodies[idx+1].name_jp)
			if not n: return False
			print(f"{m[0]} vs. {n[0]}")
			return int(m[1]) > int(n[1])
		
		## "R1,R2,R3" > "L1,L2,L3"
		m = re.search(r"[LR][TB]?(\d)$", rig.name_jp)
		if m:
			n = re.search(r"[LR][TB]?(\d)$", pmx.rigidbodies[idx+1].name_jp)
			if not n: return False
			return int(m[1]) > int(n[1])
		
		## "2_L" > "1_R"
		m = re.search(r"(\d+)_[LR]$", rig.name_jp)
		if m:
			n = re.search(r"(\d+)_[LR]$", pmx.rigidbodies[idx+1].name_jp)
			if not n: return False
			return int(m[1]) > int(n[1])
		
		## Nothing matched
		return False
	######
	arr = [item[0] for item in enumerate(pmx.rigidbodies) if collect(item)]
	return split_rigid_chain(pmx, arr)

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
def patch_bone_array(pmx, head_body, arr, name, grp):
	""" Hook a chain of RigidBodies to a static Body and anchor it to [head_body] """
	if True: ## To keep the History aligned
		if check_no_dupes(pmx, find_rigid, name+"_r"):
			if DEBUG: print(f"Already added a bone chain for {name}")
			return
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
		if (new_bodies == 0 and new_joints == 0):
			del pmx.rigidbodies[num_bodies]
			return
		
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
	print("--- Stage 'split_merged_materials'...")
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

## [Mode 03]
def split_rigid_chain(pmx, arr=None):
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
		# Set RigidBody1.Type to Green
		rigid2.phys_mode = 0
		
		# Store Bone.LinkTo as BoneLink
		tail = bone.tail
		if bone.tail_usebonelink == False:
			print(f"{bone.tail} was already without link")
			return
		# Set Bone.LinkTo as [Offset: 0 0 -0.1]
		bone.tail_usebonelink = False
		bone.tail = [0, 0, -0.1]
		
		# Find Rigid linked to BoneLink (RigidBody2)
		rigid3 = None
		for r in pmx.rigidbodies[idx-30:idx]:
			if r.bone_idx == tail:
				rigid3 = r
				break
		if rigid3 == None:
			print(f"Could not find any rigid linked to bone {tail}, cannot verify joints")
			return
		
		# Find Joint that connects Rigid & RigidBody1
		prefix = re.sub("(ca_slot\d+).*", "$1", rigid.name_jp)
		if prefix in slot_map: joints = slot_map[prefix]
		else:
			joints = [x for x in pmx.joints if x.name_jp.startswith(prefix)]
			slot_map[prefix] = joints
		joint = None
		for j in joints:
			if j.rb1_idx == idx and j.rb2_idx == idx+1:
				joint = j
				break
		if joint == None:
			print(f"Could not find any joint linking the two bodies. Skipping Joints")
			return
		
		# Set A to RigidBody2
		idx2 = find_rigid(pmx, rigid3.name_jp)
		joint.rb1_idx = idx2
	
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
	"""
	Creates:
	:: @AddBaseBody()
	:: @add_joint() between each two chain segments with ROT:[-10:10, -5:5, -10:10]
	:: Assign rigidbodies to enclosed joint
	"""
	body_num: int = len(pmx.rigidbodies)
	AddBaseBody(pmx, boneIndex, mode, r, uvFlag, name, group)
	added_bodies: int = len(pmx.rigidbodies) - body_num
	if (added_bodies <= 0):
		print(f"Did not add any chains for {name}, might already exist!")
		return
	
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

def check_no_dupes(pmx, func, name):
	return global_state[OPT__NODUPES] and func(pmx, name, False) != -1

#### Calculate nocollide_mask
# Given a group X in [1 to 16]
#>	remove X only           : 2^(X-1)         # == Keep all except X
#>	remove all lower  groups: 2^(X-1) - 1
#>	remove all higher groups: sum([2^(i-1) for i in range(16, X, -1)])
#>	remove all but X        : sum([2^(i-1) for i in range(16, X, -1)], 2^(X-1) - 1) == higher(X) + lower(X)
#>	>	## For 14: Sum 2^14 + 2^15 + 2^13 - 1
#>	int(math.pow(2, 15))


## /(\w+): (List\[\w+\]|\w+), *:: (.+)/  -- /\1: \2 = \3,/
######
##-- Add a new object with default values unless specified

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

##############

def start_fancy_things(pmx, input_filename_pmx):
	import kkpmx_core as kkcore
	(pmx1, input_filename_pmx1) = (pmx, input_filename_pmx)
	## Load 2nd model
	(pmx2, input_filename_pmx2) = util.main_starter(None)
	## Ask for Mode 1, Mode 2
	choices = [("<< Mode 1 >>", do_mode_1), ("<< Mode 2 >>", do_mode_2), ("<< Invert >>", do_invert)]
	mode = util.ask_choices("Select direction to calculate growth morph for", choices)
	## Ask which is the small == Morph Target
	choices = [("Add Morph to 2nd, becomes 1st at 100%", 1), ("Add Morph to 1st, becomes 2nd at 100%", 2)]
	dirFlag = util.ask_choices("Select direction to calculate growth morph for", choices)
	## Call Mode
	if dirFlag == 1: mode(pmx1, pmx2, input_filename_pmx2)
	else:            mode(pmx2, pmx1, input_filename_pmx1)
	pass

def do_mode_1(pmx, pmx2, input_filename_pmx):
	import kkpmx_core as kkcore
	(pmx1, input_filename_pmx2) = (pmx, input_filename_pmx)
	##########
	# do the bones stuff
	morphBones = range(len(pmx1.bones))
	vecDictRel = get_delta_map(pmx, pmx2, get_parent_map(pmx, morphBones), True)
	
	boneList = []
	def add_morph_bone(bone_idx):
		delta = vecDictRel[bone_idx].ToList()
		kkcore.__append_bonemorph(boneList, bone_idx, delta, [0,0,0], None)
	[add_morph_bone(idx) for idx in morphBones]
	import nuthouse01_pmx_struct as pmxstruct
	pmx2.morphs.append(pmxstruct.PmxMorph("BoneMorph", "BoneMorph", 4, 2, boneList))
	flag = util.ask_yes_no("Do you want me to wait for the 3rd and execute Mode 2 afterwards?")
	##########
	# Ask if we should wait or doing it later(end)
	kkcore.end(pmx2, input_filename_pmx2, "_vmorph_v1")
	##-- Wait
	if flag:
	# Write the model
	# Tell instructions
	# Wait for input to continue
		util.ask_yes_no("Press Enter or 'y' to continue", "y")
	# Call do_mode_2
		print("--------------")
		do_mode_2(pmx1, pmx2, input_filename_pmx2)
	##-- Do later
	else:
	# Write the model
	# Tell instructions
	# exit
		pass
#########
	pass

def do_mode_2(pmx, pmx2, input_filename_pmx):
	import kkpmx_core as kkcore
	(pmx1, input_filename_pmx2) = (pmx, input_filename_pmx)
	# load the morphed pmx as pmx3
	(pmx3, input_filename_pmx3) = util.main_starter(None)
	
	##############
	morphList = []
	def add_morph(idx: int, vert_idx: int, abs_idx=False): ## @vector = pos of @idx in pmx2 \\ @vert_idx in pmx1
		big_vert = pmx3.verts[idx]
		big_pos  = Vector3.FromList(big_vert.pos)
		big_idx  = big_vert.weight[0]
		big_bone = Vector3.FromList(pmx3.bones[big_idx].pos)
		
		sma_vert = pmx1.verts[vert_idx]# if abs_idx else vertices[vert_idx]
		sma_pos  = Vector3.FromList(sma_vert.pos)
		sma_idx  = sma_vert.weight[0]
		sma_bone = Vector3.FromList(pmx1.bones[sma_idx].pos)

		delta = (big_bone - big_pos) - (sma_bone - sma_pos)
		kkcore.__append_vertexmorph(morphList, idx, delta.ToList(), None)
	##############
	
	def match_uv(src, dst):
		prec = 4
		return round(src[0], prec) == round(dst[0], prec) and round(src[1], prec) == round(dst[1], prec)
	wrong_vert = []
	
	# do the vertices stuff for all materials
	for idx in range(len(pmx3.verts)):#vertices2:
		vert = pmx3.verts[idx]
		#vector = Vector3.FromList(vert.pos)
		if match_uv(pmx1.verts[idx].uv, vert.uv):
			add_morph(idx, idx, True)
		else: wrong_vert.append(idx)#raise Exception(f"Vertices at {idx} are not equal")
	
	if len(wrong_vert) > 0: raise Exception(f"Found inequal Vertices at {wrong_vert}!")
	
	# write model
	pmx2.morphs.append(pmxstruct.PmxMorph("VertexMorph", "VertexMorph", 4, 1, morphList))
	finalizer(pmx2)
	input_filename_pmx2 = re.sub(r"_vmorph_v1","_vmorph_v2",input_filename_pmx2)
	kkcore.end(pmx2, input_filename_pmx2, "", ["Added GrowthMorph"])
	# Ask if it also should do the inverted version
	pass

def do_invert(pmx, pmx2, input_filename_pmx):
	"""
	@pmx (== old @pmx2) contains an already completed GrowthMorph based on @pmx2 (== old @pmx1)
	Now @pmx2 should get the same morph, but inverted
	"""
	import kkpmx_core as kkcore
	(pmx_big, pmx_sma) = (pmx, pmx2)
	if find_morph(pmx_big, "GrowthMorph") is None:
		print("<< GrowthMorph not found >>")
		return
	def invert(x): return (-(Vector3.FromList(x))).ToList()
	
	## Invert BoneMorph
	boneList = []
	morph_b = pmx_big.morphs[find_morph(pmx_big, "BoneMorph")]
	for bone in morph_b.items: kkcore.__append_bonemorph(boneList, bone.bone_idx, invert(bone.move), [0,0,0], None)
	
	## Invert VertexMorph
	morphList = []
	morph_v = pmx_big.morphs[find_morph(pmx_big, "VertexMorph")]
	for vert in morph_v.items: kkcore.__append_vertexmorph(morphList, vert.vert_idx, invert(vert.move), None)
	
	## Create Morphs
	pmx_sma.morphs.append(pmxstruct.PmxMorph("BoneMorph", "BoneMorph", 4, 2, boneList))
	pmx_sma.morphs.append(pmxstruct.PmxMorph("VertexMorph", "VertexMorph", 4, 1, morphList))
	finalizer(pmx_sma)
	kkcore.end(pmx_sma, input_filename_pmx, "_vmorph_Invert", ["Added inverted GrowthMorph"])

def finalizer(pmx):
	group = [ ]
	group.append(pmxstruct.PmxMorphItemGroup(find_morph(pmx, "BoneMorph"), value = 1))
	group.append(pmxstruct.PmxMorphItemGroup(find_morph(pmx, "VertexMorph"), value = 1))
	pmx.morphs.append(pmxstruct.PmxMorph("GrowthMorph", "GrowthMorph", 4, 0, group))
	
	## Repair some Physics
	change_phy_mode(pmx, ["左AH1","左AH2","左胸操作接続","左胸操作衝突","右AH1","右AH2","右胸操作接続","右胸操作衝突"], 2)
##########
	pass


def do_fancy_things(pmx, input_filename_pmx):
	import kkpmx_core as kkcore
	#Load Model Full    = pmx
	#Load Model Partial = pmx2
	#pmx2 = None
	#input_filename_pmx2 = None
	#def caller(_pmx, _input_filename_pmx):
	#	pmx2 = _pmx
	#	input_filename_pmx2 = _input_filename_pmx
	(pmx2, input_filename_pmx2) = util.main_starter(None)

	mat_idx = kkcore.ask_for_material(pmx, returnIdx=True)
	faces = kkcore.from_material_get_faces(pmx, mat_idx, returnIdx=False)
	vertices = kkcore.from_faces_get_vertices(pmx, faces, returnIdx=False)
	vertIdxs = kkcore.from_faces_get_vertices(pmx, faces, returnIdx=True)
	bones = kkcore.from_vertices_get_bones(pmx, vertIdxs, returnIdx=True)
	
	uv_map = [ v.uv for v in vertices ]
	uv_enum = tuple(enumerate(uv_map))

	mat_idx2 = kkcore.ask_for_material(pmx2, returnIdx=True)
	faces2 = kkcore.from_material_get_faces(pmx2, mat_idx2, returnIdx=False)
	vertices2 = kkcore.from_faces_get_vertices(pmx2, faces2, returnIdx=True)
	bones2 = kkcore.from_vertices_get_bones(pmx, vertices2, returnIdx=True)
	
	from kkpmx_handle_overhang import get_bounding_box
	print(get_bounding_box(pmx, mat_idx))
	print(get_bounding_box(pmx2, mat_idx2))

	morphList = []
	
	def match_uv(src, dst):
		prec = 4
		flag = round(src[0], prec) == round(dst[0], prec) and round(src[1], prec) == round(dst[1], prec)
		return flag
		if flag: return True
		prec = 5
		return round(src[0], prec) == round(dst[0], prec) or round(src[1], prec) == round(dst[1], prec)
	morphBones = range(len(pmx.bones))#
	vecDictRel = get_delta_map(pmx, pmx2, get_parent_map(pmx, morphBones), True)
	
	def add_morph(vector: Vector3, idx: int, vert_idx: int, abs_idx=False): ## @vector = pos of @idx in pmx2 \\ @vert_idx in pmx
		big_vert = pmx2.verts[idx]
		big_pos  = Vector3.FromList(big_vert.pos)
		big_idx  = big_vert.weight[0]
		big_bone = Vector3.FromList(pmx2.bones[big_idx].pos)
		
		sma_vert = pmx.verts[vert_idx] if abs_idx else vertices[vert_idx]
		sma_pos  = Vector3.FromList(sma_vert.pos)
		sma_idx  = sma_vert.weight[0]
		sma_bone = Vector3.FromList(pmx.bones[sma_idx].pos)

		delta = (big_bone - big_pos) - (sma_bone - sma_pos)
		
		kkcore.__append_vertexmorph(morphList, idx, delta.ToList(), None)
		
	if True:
		boneList = []
		def add_morph_bone(bone_idx):
			delta = vecDictRel[bone_idx].ToList()
			kkcore.__append_bonemorph(boneList, bone_idx, delta, [0,0,0], None)
		[add_morph_bone(idx) for idx in morphBones]
		import nuthouse01_pmx_struct as pmxstruct
		pmx2.morphs.append(pmxstruct.PmxMorph("BoneMorph", "BoneMorph", 4, 2, boneList))

	miss_list = []
	####
	for idx in vertices2:
		vert = pmx2.verts[idx]
		vector = Vector3.FromList(vert.pos)
		if match_uv(pmx.verts[idx].uv, vert.uv):
			add_morph(vector, idx, idx, True)
			continue
		raise Exception("Vertices are not equal")
	
	##### Finalize
	import nuthouse01_pmx_struct as pmxstruct
	pmx2.morphs.append(pmxstruct.PmxMorph("Test", "Test", 4, 1, morphList))
	
	kkcore.end(pmx2, input_filename_pmx2, "_vmorph")

###########
if __name__ == '__main__': util.main_starter(run)