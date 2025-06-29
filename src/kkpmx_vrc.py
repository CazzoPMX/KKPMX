# Cazoo - 2025-03-04
#####################
from typing import List
import re
import os
import copy
from datetime import datetime ### used in [end]

import kkpmx_property_parser as PropParser ## parseMatComments
import kkpmx_utils as util
from kkpmx_utils import find_bone, find_mat, find_disp, find_morph, find_rigid, process_weight
import kkpmx_rigging as kkrig
#from kkpmx_core import end
from kkpmx_handle_overhang import run as runOverhang
from kkpmx_json_generator import GenerateJsonFile
from kkpmx_morphs import emotionalize, sort_morphs#, prepare_for_export
try:
	import nuthouse01_core as core
	import nuthouse01_pmx_parser as pmxlib
	import nuthouse01_pmx_struct as pmxstruct
	import _translation_tools as tlTools
	import _translate_to_english as pmxTL
	import morph_scale
	from kkpmx_csv import csv__from_bones, csv__from_mat, csv__from_vertex, export_material_surface
except ImportError as eee:
	print(eee.__class__.__name__, eee)
	print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
	print("...press ENTER to exit...")
	input()
	exit()
	core = pmxlib = pmxstruct = morph_scale = None


name_map = {# Key: [idx, OrgEN name, varargs Replacement]
	"全ての親":		["",   "MotherBone",		"RootBone",		"",		""],
	"センター":		["",   "Center",			"Center",		"",		""],
	"グルーブ":		["",   "groove",			"Groove",		"",		""],
	"腰":			["",   "waist",				"Waist",		"",		""],
	"上半身":		["",   "upper body",		"Spine",		"",		""],
	"上半身2":		["",   "upper body2",		"Chest",		"",		""],
	"上半身3":		["",   "upper body3",		"UpperChest",	"",		""],
	# Right Arm
	"右肩P":			["--", "shoulderP_R",		"",		"",		""],
	"右肩":			["",   "shoulder_R",		"Right",		"Shoulder",		""],
	"右肩C":			["--", "shoulderC_R",		"",		"",		""],
	"右腕":			["",   "arm_R",				"Right",		"Upper",		"Arm"],
	"右腕捩":		["--", "arm twist_R",		"",		"",		""],
	"右腕捩1":		["--", "arm twist_R1",		"",		"",		""],
	"右腕捩2":		["--", "arm twist_R2",		"",		"",		""],
	"右腕捩3":		["--", "arm twist_R3",		"",		"",		""],
	"右ひじ":			["",   "elbow_R",			"Right",		"Lower",		"Arm"],
	"右手捩":		["--", "wrist twist_R",		"",		"",		""],
	"右手捩1":		["--", "wrist twist_R1",	"",		"",		""],
	"右手捩2":		["--", "wrist twist_R2",	"",		"",		""],
	"右手捩3":		["--", "wrist twist_R3",	"",		"",		""],
	"右ひじ_Rot":		["",   "elbow_R_Rot",		"",		"",		""],
	"右手首":		["",   "wrist_R",			"",		"",		""],
	"cf_s_hand_R":	["",   "cf_s_hand_R",		"Right",		"Hand",		""],  ## This one has the vertices, so we use it instead of the above
	"右手首Sleeve":	["",   "wristSleeve_R",		"",		"",		""],
	"右ダミー":		["",   "dummy_R",			"",		"",		""],
	"右小指１":		["",   "little1_R",			"Right",		"Little",		"Proximal"],
	"右小指２":		["",   "little2_R",			"Right",		"Little",		"Intermediate"],
	"右小指３":		["",   "little3_R",			"Right",		"Little",		"Distal"],
	"右小指先":		["**", "little_R end",		"Right",		"Little",		"Distal", "_end"],
	"右薬指１":		["",   "third1_R",			"Right",		"Ring", 		"Proximal"],
	"右薬指２":		["",   "third2_R",			"Right",		"Ring", 		"Intermediate"],
	"右薬指３":		["",   "third3_R",			"Right",		"Ring", 		"Distal"],
	"右薬指先":		["**", "third_R end",		"Right",		"Ring", 		"Distal", "_end"],
	"右中指１":		["",   "middle1_R",			"Right",		"Middle",		"Proximal"],
	"右中指２":		["",   "middle2_R",			"Right",		"Middle",		"Intermediate"],
	"右中指３":		["",   "middle3_R",			"Right",		"Middle",		"Distal"],
	"右中指先":		["**", "middle_R end",		"Right",		"Middle",		"Distal", "_end"],
	"右人指１":		["",   "fore1_R",			"Right",		"Index",		"Proximal"],
	"右人指２":		["",   "fore2_R",			"Right",		"Index",		"Intermediate"],
	"右人指３":		["",   "fore3_R",			"Right",		"Index",		"Distal"],
	"右人指先":		["**", "fore_R end",		"Right",		"Index",		"Distal", "_end"],
	"右親指０":		["",   "thumb0_R",			"Right",		"Thumb",		"Proximal"],
	"右親指１":		["",   "thumb1_R",			"Right",		"Thumb",		"Intermediate"],
	"右親指２":		["",   "thumb2_R",			"Right",		"Thumb",		"Distal"],
	"右親指先":		["**", "thumb_R end",		"Right",		"Thumb",		"Distal", "_end"],
	"右肩Solo":		["",   "shoulder_R_solo",	"",		"",		""],
	# Left Arm
	"左肩P":			["--", "shoulderP_L",		"",		"",		""],
	"左肩":			["",   "shoulder_L",		"Left", 		"Shoulder",		""],
	"左肩C":			["--", "shoulderC_L",		"",		"",		""],
	"左腕":			["",   "arm_L",				"Left", 		"Upper",		"Arm"],
	"左腕捩":		["--", "arm twist_L",		"",		"",		""],
	"左腕捩1":		["--", "arm twist_L1",		"",		"",		""],
	"左腕捩2":		["--", "arm twist_L2",		"",		"",		""],
	"左腕捩3":		["--", "arm twist_L3",		"",		"",		""],
	"左ひじ":			["",   "elbow_L",			"Left", 		"Lower",		"Arm"],
	"左手捩":		["--", "wrist twist_L",		"",		"",		""],
	"左手捩1":		["--", "wrist twist_L1",	"",		"",		""],
	"左手捩2":		["--", "wrist twist_L2",	"",		"",		""],
	"左手捩3":		["--", "wrist twist_L3",	"",		"",		""],
	"左ひじ_Rot":		["",   "elbow_L_Rot",		"",		"",		""],
	"左手首":		["",   "wrist_L",			"", 	"", 	""],## Same as with right hand
	"cf_s_hand_L":	["",   "cf_s_hand_L",		"Left",		"Hand",		""], 
	"左手首Sleeve":	["",   "wrist_L_Sleeve",	"",		"",		""],
	"左ダミー":		["",   "dummy_L",			"",		"",		""],
	"左小指１":		["",   "little1_L",			"Left", 		"Little",		"Proximal"],
	"左小指２":		["",   "little2_L",			"Left", 		"Little",		"Intermediate"],
	"左小指３":		["",   "little3_L",			"Left", 		"Little",		"Distal"],
	"左小指先":		["**", "little_L end",		"Left", 		"Little",		"Distal", "_end"],
	"左薬指１":		["",   "third1_L",			"Left", 		"Ring", 		"Proximal"],
	"左薬指２":		["",   "third2_L",			"Left", 		"Ring", 		"Intermediate"],
	"左薬指３":		["",   "third3_L",			"Left", 		"Ring", 		"Distal"],
	"左薬指先":		["**", "third_L end",		"Left", 		"Ring", 		"Distal", "_end"],
	"左中指１":		["",   "middle1_L",			"Left", 		"Middle",		"Proximal"],
	"左中指２":		["",   "middle2_L",			"Left", 		"Middle",		"Intermediate"],
	"左中指３":		["",   "middle3_L",			"Left", 		"Middle",		"Distal"],
	"左中指先":		["**", "middle_L end",		"Left", 		"Middle",		"Distal", "_end"],
	"左人指１":		["",   "fore1_L",			"Left", 		"Index",		"Proximal"],
	"左人指２":		["",   "fore2_L",			"Left", 		"Index",		"Intermediate"],
	"左人指３":		["",   "fore3_L",			"Left", 		"Index",		"Distal"],
	"左人指先":		["**", "fore_L end",		"Left", 		"Index",		"Distal", "_end"],
	"左親指０":		["",   "thumb0_L",			"Left", 		"Thumb",		"Proximal"],
	"左親指１":		["",   "thumb1_L",			"Left", 		"Thumb",		"Intermediate"],
	"左親指２":		["",   "thumb2_L",			"Left", 		"Thumb",		"Distal"],
	"左親指先":		["**", "thumb_L end",		"Left", 		"Thumb",		"Distal", "_end"],
	"左肩Solo":		["",   "shoulder_L_solo",	"",			"",		""],
	#-- Head
	"首":			["",   "neck",				"Neck", 		"",		""],
	"頭":			["",   "head",				"Head", 		"",		""],
	"両目":			["",   "Viewangle"],
	"左目":			["",   "Eye_L",				"Left", 		"Eye",		""],
	"右目":			["",   "Eye_R",				"Right",		"Eye",		""],
	#"胸親":			["",   "breast parent"],
	#"左胸操作":  	["",   "breast control_L"],
	"左AH1":			["",   "AH1_L"],
	"左AH2":			["",   "AH2_L"],
	#"右胸操作":  	["",   "breast control_R"],
	"右AH1":			["",   "AH1_R"],
	"右AH2":			["",   "AH2_R"],
	#-- LowerBody
	"下半身":		["",   "lower body",		"Hips", 		"",		""],
	"腰キャンセル右":	["--", "waist_cancel_R"],
	"右足":			["",   "leg_R",				"Right",		"Upper",		"Leg"],
	"右ひざ":			["",   "knee_R",			"Right",		"Lower",		"Leg"],
	"右足首":		["",   "foot_R",			"Right",		"Foot", 		""],
	"右つま先":		["",   "toe_R",				"Right",		"Toe",  		""],
	"右足IK親":		["--", "leg IKP_R",			"Right",		"Foot", 		"IK", "Parent"],
	"右足ＩＫ":		["**", "leg IK_R",			"Right",		"Foot", 		"IK"],
	"右つま先ＩＫ":		["**", "toe IK_R",			"Right",		"Toe",  		"IK"],
	"腰キャンセル左":	["--", "waist_cancel_L"],
	"左足":			["",   "leg_L",				"Left", 		"Upper",		"Leg"],
	"左ひざ":			["",   "knee_L",			"Left", 		"Lower",		"Leg"],
	"左足首":		["",   "foot_L",			"Left", 		"Foot", 		""],
	"左つま先":		["",   "toe_L",				"Left", 		"Toe",  		""],
	"左足IK親":		["--", "leg IKP_L",			"Left", 		"Foot", 		"IK", "Parent"],
	"左足ＩＫ":		["**", "leg IK_L",			"Left", 		"Foot", 		"IK"],
	"左つま先ＩＫ":		["**", "toe IK_L",			"Left", 		"Toe",  		"IK"],
	"右足D":			["",   "leg_RD",			"Right",		"Upper",		"Leg", "Detach"],
	"右ひざD":		["",   "knee_RD",			"Right",		"Lower",		"Leg", "Detach"],
	"右足首D":		["",   "foot_RD",			"Right",		"Foot", 				"Detach"],
	"右足先EX":		["",   "toe2_R",			"Right",		"Toe",  				"Detach"],
	"左足D":			["",   "leg_LD",			"Left", 		"Upper",		"Leg", "Detach"],
	"左ひざD":		["",   "knee_LD",			"Left", 		"Lower",		"Leg", "Detach"],
	"左足首D":		["",   "foot_LD",			"Left", 		"Foot", 				"Detach"],
	"左足先EX":		["",   "toe2_L",			"Left", 		"Toe",  				"Detach"],
	"cf_j_spine03":	["",   "cf_j_spine03",		"Upper",		"Chest",		""],
	}
index_bones = [
	"全ての親", "センター", "グルーブ",                 # Main
	"下半身",                                    # LowerBody
	## UpperBody
	"上半身", "上半身2", "cf_j_spine03",          # UpperBody
	"左肩", "左腕", "左ひじ", "cf_s_hand_L",       # Left Arm
	"首", "頭", ## "Viewangle", "左目", "右目",   # Head
	"右肩", "右腕", "右ひじ", "cf_s_hand_R",       # Right Arm
	## LowerBody
	"左足", "左ひざ", "左足首", "左つま先",          # Left Leg
	#"左足ＩＫ", "左つま先ＩＫ",                        # Left IK
	"右足", "右ひざ", "右足首", "右つま先",          # Right Leg
	#"右足ＩＫ", "右つま先ＩＫ",                        # Right IK
]
english_index = ["cf_j_spine03", "cf_s_hand_L", "cf_s_hand_R"]



detailedMap_Min = {
	"LeftShoulder":  [  ],
	"LeftUpperArm":  [ "左腕捩", "左腕捩1", "左腕捩2", "左腕捩3", ],
	"LeftLowerArm":  [ "左手捩", "左手捩1", "左手捩2", "左手捩3", ],
	"LeftHand":      [  ],
	"RightShoulder": [  ],
	"RightUpperArm": [ "右腕捩", "右腕捩1", "右腕捩2", "右腕捩3", ],
	"RightLowerArm": [ "右手捩", "右手捩1", "右手捩2", "右手捩3", ],
	"RightHand":     [  ],
	# Legs
	"LeftUpperLeg":  [ "左足D", ],
	"LeftLowerLeg":  [ "左ひざD", ],
	"LeftFoot":      [ "左足首D", ],
	"LeftToe":       [ "左足先EX", ],
	"RightUpperLeg": [ "右足D", ],
	"RightLowerLeg": [ "右ひざD", ],
	"RightFoot":     [ "右足首D", ],
	"RightToe":      [ "右足先EX", ],
}

detailedMap_Max = {
	# Torso
	"Head":       [
		"cf_s_head", "cf_J_LowerFace", "cf_J_CheekUp_s_L", "cf_J_CheekUp_s_R", 
		"cf_J_MouthBase_ty", "cf_J_MouthBase_rx", "cf_J_MouthCavity", "cf_J_MouthMove", 
		"cf_J_Mouth_L", "cf_J_Mouth_R", "cf_J_MouthLow", "cf_J_Mouthup", 
		"cf_J_Mayu_ty", "cf_J_Mayumoto_L", "cf_J_Mayumoto_R", 
	],
	"Neck":       [ "cf_s_neck", ],
	"UpperChest": [ "cf_s_spine03", "cf_j_spine03", ],
	"Chest":      [ "cf_s_spine02", ],
	"Spine":      [ "cf_s_spine01", ],
	"Hips":       [ "cf_s_waist01", "cf_s_waist02", ],
	# Arms
	"LeftShoulder":  [ "cf_d_shoulder_L", "左肩Solo", "cf_s_shoulder02_L", ],
	"LeftUpperArm":  [  ],
	"LeftLowerArm":  [ "左ひじ_Rot", "cf_s_elbo_L", "cf_s_elboback_L", ],
	"LeftHand":      [ "cf_d_hand_L", "cf_s_hand_L", ],
	"RightShoulder": [ "cf_d_shoulder_R", "右肩Solo", "cf_s_shoulder02_R", ],
	"RightUpperArm": [  ],
	"RightLowerArm": [ "右ひじ_Rot", "cf_s_elbo_R", "cf_s_elboback_R", ],
	"RightHand":     [ "cf_d_hand_R", "cf_s_hand_R", ],
	# Legs
	"LeftUpperLeg":  [ "cf_s_thigh01_L", "cf_s_thigh02_L", "cf_s_thigh03_L", ],
	"LeftLowerLeg":  [ "cf_s_leg01_L", "cf_s_leg02_L", "cf_s_leg03_L", "cf_d_kneeF_L", "cf_s_kneeB_L", ],
	"LeftFoot":      [  ],
	"LeftToe":       [  ],
	"RightUpperLeg": [ "cf_s_thigh01_R", "cf_s_thigh02_R", "cf_s_thigh03_R", ],
	"RightLowerLeg": [ "cf_s_leg01_R", "cf_s_leg02_R", "cf_s_leg03_R", "cf_d_kneeF_R", "cf_s_kneeB_R", ],
	"RightFoot":     [  ],
	"RightToe":      [  ],
}


###############
#### Translate Model into Non-MMD form
## Rearrange Armature into VRChat order + Translate them
## Translate Morphs, combine some into singular VertexMorph for VRChat

def rename_bones_for_export(pmx, input_file_name):
	from _prune_unused_bones import insert_single_bone, apply_bone_remapping_dyn
	from kkpmx_rigging import add_bone
	import kkpmx_special as kkspec
	import copy
	from kkpmx_core import end
	
	vrcFlags = {}
	vrcFlags["detailed"] = True
	#TODO: Inquiry about UserPrompt for "Simplify Heavy, keep NSFW, Light (no detailed)"
	def __getFlag(_dict, _flag): return _dict.get(_flag, False)
	getFlag = lambda _flag: __getFlag(vrcFlags, _flag)
	
	#--- Prepare the Dict to ensure order
	def prematureEnd(extraSuffix):
		return end(pmx if True else None, input_file_name, "_export"+"--"+extraSuffix, ["Did stuff"])
	
	print(f"==== Stage -1: Verify")
	hasGroove = find_bone(pmx, "グルーブ", False) != -1
	#if idx == -1:
	#	print("-- No 'グルーブ' bone found. Please run SemiStandard-Bones Extension and add them.")
	#	return
	
	if (getFlag("detailed")):
		print(f"==== Stage 0-pre: Rerun Simplify-lite")
		flag_SFW = util.ask_yes_no("Merge certain Bones for SFW export", "y")
		spec_opt = {
			kkspec.OPT_SILENT: True,
			kkspec.OPT_CHEST: True,
			kkspec.OPT_SFW: flag_SFW,
			"soloMode": False,
			"fullClean": True,
		}
		_bArr = util.find_bones(pmx, ["cf_s_bust01_L", "cf_s_bnip02_L", "cf_s_bust01_R", "cf_s_bnip02_R"], False, False)
		if all(_bArr):
			vrcFlags["tail.l"] = util.arrSub(_bArr[1].pos, _bArr[0].pos)
			vrcFlags["tail.r"] = util.arrSub(_bArr[3].pos, _bArr[2].pos)
			print(vrcFlags["tail.l"])
			print(vrcFlags["tail.r"])
		
		kkspec.simplify_armature(pmx, input_file_name, spec_opt)
	
	
	print(f"==== Stage 0: Prepare")
	maxSize = 32; trDict = { }	## int: List[PmxBone, PmxBone, int]
	for x in range(maxSize): trDict[x] = [None, None, -1] ## New Bone, Old Bone, Master Order
	
	idx = 0 ## Pre-Fill the desired Bones in order of [index_bones]
	for name in index_bones:
		if not hasGroove and name == "グルーブ": continue
		name_map[name][0] = f"{idx}"
		print(f"{name} receives {idx}")
		idx += 1
	
	# Handle surprise UpperChest
	idx = find_bone(pmx, "上半身3", True)
	if idx != -1: name_map["上半身3"][0] = name_map["cf_j_spine03"][0]
	
	##-- HotFix in case the Bones have been Hyper-Merged
	def checkHand(expect, fallback):
		if find_bone(pmx, expect, True) == -1:
			print("-- Fake one not found, use correct one instead")
			name_map[fallback][0] = name_map[expect][0]
			name_map[fallback][2:] = name_map[expect][2:]
			name_map[expect][0] = ""
			print(name_map[fallback])
			print(name_map[expect])
	checkHand("cf_s_hand_L", "左手首")
	checkHand("cf_s_hand_R", "右手首")
	
	print(f"==== Stage 1: Parsing")
	delDict = []
	idx = 0
	
	rgx = re.compile("^[a-zA-Z0-9_.\-* +]+$")
	rgxFix = re.compile("^(ca_slot\d\d)\*\d$")
	for bone in pmx.bones: ### Translate Japanese Names
		name = bone.name_jp
		if rgxFix.search(name): bone.name_jp = rgxFix.sub(r"\1", name)
		if rgx.search(name):
			if name not in english_index:
				#print(f"--- Skip {name}")
				continue ## Skip any bone that does not contain any CJK letter
		if not name in name_map:
			print(f"'{name}' was not found in the Map!")
			continue
		values = name_map[name]
		delSfx = ""
		if len(values[0]) > 0:
			_idx = values[0]
			if _idx == "--": ## All entries with "--" on idx[0] are deleted without asking
				delDict.append(bone)
				delSfx = "_DELME--LinePrune"
			elif getFlag("detailed") and _idx == "**":
				delDict.append(bone)
				delSfx = "_DELME--DetailPrune"
			else:
				b = add_bone(pmx, name_jp=f"{_idx}", _solo=True)
				idx = int(_idx)
				trDict[idx] = [b, bone, idx] ## New Bone, Old Bone, Master Order
				print(f"--- Register new Bone {b.name_jp} for {bone.name_jp}")
		else: print(f"--- Not registering anything for bone {bone.name_jp}::({values})")
		
		value = "" if len(values) < 3 else ''.join([*values[2:]])
		if len(value) == 0: value = values[1]
		#if len(delSfx) != 0: bone.name_jp +=  delSfx
		#else: bone.name_jp = value
		bone.name_jp = value # + delSfx
		if len(delSfx) != 0: bone.name_en = delSfx
	
	#-- If the model has this, change it manually
	idx = find_bone(pmx, "上半身3", False)
	if (idx != -1): idx = find_bone(pmx, "cf_j_spine03", True)
	if (idx != -1):
		_idx = name_map["cf_j_spine03"][0] ## Get new target index
		b = add_bone(pmx, name_jp=f"{_idx}", _solo=True)
		bone = pmx.bones[idx]
		bone.name_jp = "UpperChest"
		print(f"--- Register new Bone {b.name_jp} for {bone.name_jp}")
		trDict[int(_idx)] = [b, bone, _idx]

	print(f"==== Stage 2: Insert Bones")
	newIdx = 0
	
	for item in range(len(trDict)):
		if not item in trDict: continue
		(k, v1, v2) = (item, trDict[item][0], trDict[item][1])
		if (v1 is None): continue ## Skip those we have not registered
		
		## Insert the actually existing / used bones in order
		print(f"--- Insert new Bone {v1.name_jp} for {v2.name_jp}")
		insert_single_bone(pmx, v1, newIdx)
		trDict[item][2] = newIdx ## Rebind the order to only use actually used ones
		newIdx += 1
	
	idxMap  = {} ## {int: int} = "If Idx is this" : "Replace with this"
	nameMap = {} ## {str: int} = "Translated Name": "Is now found at Idx=X"
	for entry in trDict.items():
		(k, v1, v2) = (entry[1][2], entry[1][0], entry[1][1])
		if (v2 is None): continue ## Skip those we have not registered
		val = find_bone(pmx, v2.name_jp, False)
		nameMap[v2.name_jp] = k ## Used for Fixing Parents
		idxMap[val] = k         ## Used for Remapping
	
	#prematureEnd("02")
	
	############ Replace their uses
	print(f"==== Stage 3: Replace Uses")
	
	def addToIdx(_nameJP, _dst):
		_idx1 = find_bone(pmx, _nameJP, False)
		if _idx1 == -1:
			values = name_map.get(_nameJP, None)
			if not values: return
			_nameEN = "".join(values[2:])# + values[3] + values[4]
			_idx1 = find_bone(pmx, _nameEN, False)
			if _idx1 == -1: return
		_idx2 = find_bone(pmx, _dst, False)
		if _idx2 == -1: return
		idxMap[_idx1] = idxMap[_idx2]
	
	##-- Add some more replacements
	flag_order = True## util.ask_yes_no("Simplified before SemiStandard", "y")
	if flag_order:
		for entry in detailedMap_Min.items():
			key = entry[0]
			for elem in entry[1]: addToIdx(elem, key)
		if (getFlag("detailed")):
			for entry in detailedMap_Max.items():
				key = entry[0]
				for elem in entry[1]: addToIdx(elem, key)
			#####--- Cleanup Twists
			replace_with_parent = lambda x: util.replace_with_parent(pmx, x)
			replace_with_parent("cf_hit_wrist_L") ## Frees wrist_twist L2
			replace_with_parent("cf_hit_wrist_R") ## Frees wrist_twist R2
			replace_with_parent("a_n_wrist_L") ## Frees wrist_twist L3
			replace_with_parent("a_n_wrist_R") ## Frees wrist_twist R3
			#####--- Fix Chest
			fbx = util.get_bone_lambdas(pmx)[1]
			addToIdx("cf_d_bust00", "UpperChest" if "UpperChest" in nameMap else "Chest")
			#- Move Main Physic
			util.set_parent_if_found(pmx, "cf_hit_bust02_L", "cf_s_bust00_L", False)
			util.set_parent_if_found(pmx, "cf_hit_bust02_L", "cf_s_bust00_L", True)
			util.set_parent_if_found(pmx, "cf_hit_bust02_R", "cf_s_bust00_R", False)
			util.set_parent_if_found(pmx, "cf_hit_bust02_R", "cf_s_bust00_R", True)
			#- Change the pos
			_bLeft = pmx.bones[fbx("cf_s_bust00_L")]; _tailLeft = vrcFlags.get("tail.l", [0,0,-1])
			_bRght = pmx.bones[fbx("cf_s_bust00_R")]; _tailRght = vrcFlags.get("tail.r", [0,0,-1])
			
			_bArr = util.find_bones(pmx, ["cf_hit_bust02_L", "左胸操作"], False, False)
			_bArr = [x for x in _bArr if x]
			if any(_bArr):
				_bLeft.pos = _bArr[0].pos
				_bLeft.tail_usebonelink = False
				_bLeft.tail = _tailLeft
			
			_bArr = util.find_bones(pmx, ["cf_hit_bust02_R", "右胸操作"], False, False)
			_bArr = [x for x in _bArr if x]
			if any(_bArr):
				_bRght.pos = _bArr[0].pos
				_bRght.tail_usebonelink = False
				_bRght.tail = _tailRght
			
			#### Delete everything else to orphan the physics
			def get_or_ret(_name):
				_idx = fbx(_name)
				if _idx == -1: return None
				_bone = pmx.bones[_idx]
				_bone.name_jp = "DELME_" + _bone.name_jp
				return _bone
			
			delDict.append(get_or_ret("胸親"))
			delDict.append(get_or_ret("cf_d_bust01_L"))
			delDict.append(get_or_ret("cf_j_bust01_L"))
			delDict.append(get_or_ret("cf_d_bust02_L"))
			delDict.append(get_or_ret("左胸操作"))
			delDict.append(get_or_ret("AH1_L"))
			delDict.append(get_or_ret("AH2_L"))
			delDict.append(get_or_ret("cf_d_bust01_R"))
			delDict.append(get_or_ret("cf_j_bust01_R"))
			delDict.append(get_or_ret("cf_d_bust02_R"))
			delDict.append(get_or_ret("右胸操作"))
			delDict.append(get_or_ret("AH1_R"))
			delDict.append(get_or_ret("AH2_R"))
			delDict.append(get_or_ret("cf_d_hit_bust_L"))
			delDict.append(get_or_ret("cf_d_hit_bust_R"))
			delDict.append(get_or_ret("ChestRigidRoot"))
			util.rename_bone(pmx, "cf_s_bust00_L", "Breast.L", True)
			util.rename_bone(pmx, "cf_s_bust00_R", "Breast.R", True)
			util.rename_bone(pmx, "cf_d_siri_L", "Butt.L", True)
			util.rename_bone(pmx, "cf_d_siri_R", "Butt.R", True)
			util.rename_bone(pmx, "cf_d_sk_top", "Skirt-Root", True)
			util.rename_bone(pmx, "cf_d_spinesk_00", "Sailor.Tie", True)
			util.rename_bone(pmx, "cf_d_backsk_00", "Sailor.Cape", True)
			
		## TODO: Add Twists from tempTwist()
	else:
		#addToIdx("腰キャンセル右", "Hips")
		#addToIdx("腰キャンセル左", "Hips")
		addToIdx("右足首D", "RightToe")
		addToIdx("左足首D", "LeftToe")
		addToIdx("右ひざD", "RightFoot")
		addToIdx("左ひざD", "LeftFoot")
		addToIdx("右足D", "RightUpperLeg")
		addToIdx("左足D", "LeftUpperLeg")
		#:: TODO: Too much of Foot ends up in the Toes --> Makes VRC auto-choose cf_s_leg03_L too
	
	
	#findIdx of _idx in _dict[0] --> return dict[1][_idx] if found, else _idx
	def replace_boneIdx(_idx, _dict): return idxMap.get(_idx, _idx)
	apply_bone_remapping_dyn(pmx, [], None, replace_boneIdx)
	#prematureEnd("03")
	
	###### Clone their contents
	print(f"==== Stage 4: Clone Contents")
	for entry in trDict.items():
		(k, v1, v2) = (entry[0], entry[1][0], entry[1][1])
		if (v2 is None): continue
		pmx.bones[k] = copy.deepcopy(v2)
		v2.name_jp += "_DELME--Cloned"
	#prematureEnd("04")
	
	print(f"==== Stage 5: Rebind Parents")
	n = nameMap
	print(len(n))
	[print(x) for x in nameMap.items()]
	
	def rebinder(_bone, parent, child):
		bone.parent_idx = n[parent]
		if child:
			bone.tail_usebonelink = True
			bone.tail = n[child]
	def rebinderList(arr):
		lastParent = -1
		while len(arr) > 1:
			parent = arr[0]
			child = arr[1]
			bone = pmx.bones[parent]
			if lastParent != -1: bone.parent_idx = lastParent
			lastParent = parent
			if child != -1:
				bone.tail_usebonelink = True
				bone.tail = child
			arr.pop(0)
		if lastParent != -1:
			pmx.bones[arr[0]].parent_idx = lastParent
	bnCenter = "Groove" if hasGroove else "Center"
	pmx.bones[n["Hips"]]			.parent_idx = n[bnCenter]			## Hips to Groove << Waist
	pmx.bones[n["LeftUpperLeg"]]	.parent_idx = n["Hips"]				## Leg to Hips << Waist Cancel
	rebinderList([n["LeftUpperLeg"], n["LeftLowerLeg"], n["LeftFoot"], n["LeftToe"]]) ## Leg to Hips << Waist Cancel
	#pmx.bones[n["LeftFootIK"]]		.parent_idx = n["RootBone"]			## Foot IK to Motherbone << IKParent
	
	pmx.bones[n["RightUpperLeg"]]	.parent_idx = n["Hips"] 			## Leg to Hips << Waist Cancel
	rebinderList([n["RightUpperLeg"], n["RightLowerLeg"], n["RightFoot"], n["RightToe"]]) ## Leg to Hips << Waist Cancel
	#pmx.bones[n["RightFootIK"]]		.parent_idx = n["RootBone"]		## Foot IK to Motherbone << IKParent
	
	pmx.bones[n["Spine"]]			.parent_idx = n["Hips"]				## Spine to Hips
	
	
	##-- Only add UpperChest if it exists (although it should always exist)
	bnChest = "UpperChest"
	if not "UpperChest" in n:
		bnChest = "Chest"
		rebinderList([n["Spine"], n["Chest"]])
	else:
		rebinderList([n["Spine"], n["Chest"], n["UpperChest"]])
		#pmx.bones[n["UpperChest"]].parent_idx = n["Chest"]
	
	pmx.bones[n["LeftShoulder"]].parent_idx = n[bnChest]		## 
	rebinderList([
		n["LeftShoulder"],	## [If Presorted: Rebind Child]
		n["LeftUpperArm"],	## Shoulder P
		n["LeftLowerArm"],	## Shoulder C
		n["LeftHand"]		## Arm Twist
	])
	##[TODO](Advanced): If kept, reorder twist bones
	#-- wrist_twist, cf_s_forearm01_L, cf_s_forearm02_L, cf_s_wrist_L
	#-- Ponder if [vert_hand_L] should be child of [wrist_twist] bc correct purpose
	#----- [Legs] should mirror that behaviour
	#-- cf_s_leg01_L == leg twist (with calf collider & knee back)
	#-- cf_s_kneeB_L ~~ similar to cf_s_elboback_L, so part of twist ?
	#-- cf_s_kneeF_L ~~ similar to cf_s_elbo_L, so part of twist ?
	#-- cf_s_leg02_L, 03 ~~ like arm 02 03
	
	#pmx.bones[n["26"]].parent_idx = n["25"]
	#pmx.bones[n["26"]].parent_idx = n["25"]
	
	pmx.bones[n["Neck"]].parent_idx = n[bnChest]
	pmx.bones[n["Head"]].parent_idx = n["Neck"]
	
	pmx.bones[n["RightShoulder"]]	.parent_idx = n[bnChest]
	rebinderList([
		n["RightShoulder"],	
		n["RightUpperArm"],	## Shoulder P
		n["RightLowerArm"],	## Shoulder C
		n["RightHand"]		## Arm Twist
	])
	
	#prematureEnd("05_preBodyTop")
	#--- Set the Model Name as RootBone
	top = find_bone(pmx, "BodyTop", False)
	if top != -1:
		modelBone = pmx.bones[pmx.bones[top].parent_idx]
		pmx.bones[n["RootBone"]].name_jp = modelBone.name_jp + "_root" # Prevents issues later (duplicate names for AvatarGeneration)
		modelBone.name_jp += "_DELME--BodyTop"
	
	#prematureEnd("05")
	print(f"==== Stage 6: Cleanup effects of certain bones") ## Already gone
	## Cancels are disolved
	## Twists never changed to begin with... But maybe keep them anyway for potential Twist Bones
	
	#<todo>: Make Wrist Twist have fading out effect on Lower Arm
	#<todo>: Make Arm  Twist have fading out effect on Upper Arm
	#<todo>: Do smt with this: Vertices and Fingers are attached to [cf_s_hand_R], but [右手首] is the wrist Bone (additionally has [dummy_R])
	#> Causes no issues, but AvatarGeneration uses this as [Hand] Slot
	
	#-- Has the actual Toe vertices if they exist
	util.set_parent_if_found(pmx, "cf_j_toes_L", n["LeftToe"])
	util.set_parent_if_found(pmx, "cf_j_toes_R", n["RightToe"])
	#-- For VRChat -- Legs must actually be pointing upwards... or rather, the Hips opposite to legs
	_boneHips = pmx.bones[n["Hips"]]
	_boneHips.tail_usebonelink = False
	_boneHips.tail = [0, 1, 0]
	if (getFlag("detailed")):
		## If we go all the way, then combine Center & Groove into it
		_boneUtil = find_bone(pmx, "cf_j_waist02", True)
		if (_boneUtil != -1):
			_boneNew = pmx.bones[_boneUtil]
			_boneHips.pos = [0, _boneNew.pos[1], 0]
			_boneHips.parent_idx = n["RootBone"];
			_idxMapNew = {
				_boneUtil:   n["Hips"],
				n["Center"]: n["Hips"],
			}
			if hasGroove: _idxMapNew[n["Groove"]] = n["Hips"]
			
			def replace_boneIdx2(_idx, _dict): return _idxMapNew.get(_idx, _idx)
			apply_bone_remapping_dyn(pmx, [], None, replace_boneIdx2)
	
	#----- Cleanup weird vertices between feet
	
	from kkpmx_utils import process_weight
	(idx_LF,idx_LT,idx_RF,idx_RT) = (n["LeftFoot"], n["LeftToe"], n["RightFoot"], n["RightToe"])
	threshold = pmx.bones[n["LeftLowerLeg"]].pos[1]
	def replLeft(weight):
		if weight == idx_RF: return idx_LF
		if weight == idx_RT: return idx_LT
		return weight
	def replReight(weight):
		if weight == idx_LF: return idx_RF
		if weight == idx_LT: return idx_RT
		return weight
	for vert in pmx.verts:
		# Ignore if too high
		if vert.pos[1] > threshold: continue
		if vert.pos[0] > 0: process_weight(vert, replLeft)
		else:               process_weight(vert, replReight)
	#######
	
	tempTwist(pmx, None) ## TODO remove when adding to [04] // DevNote: Was after Stage 8 in v1
	
	print(f"==== Stage 7: Delete unneccessary bones")
	## Delete Arm Twist Parents because empty bones
	## Keep wrist Twist -- or relocate wristSleeve_R
	
	
	#print("Do not forget to make the fingers even with the morph")
	#print("Cleanup the dead ones")
	delList = []
	for entry in delDict:
		#(k, v1, v2) = (entry[0], entry[1][0], entry[1][1])
		if (entry is None): continue
		print(f"[D] Canceling {entry.name_jp}....")
		## Only add those which have a DELME_ prefix (as those are manual)
		#if entry.name_jp.startswith("DELME_") or entry.name_jp.endswith("--DetailPrune"):
		#	#delList.append(find_bone(pmx, entry.name_jp, False))
		#	#print(f"-- Marked {entry.name_jp} as force-deleted")
		entry.name_jp = "DELME_" + re.sub(r"(?:DELME_)?(\w+?)(?:_DELME)?(--\w+)?", r"\1\2", entry.name_jp)
		## Reset flags cause IK & "Not visible" are usually ignored by prune_unused_bones
		entry.has_rotate = False
		entry.has_translate = False
		entry.has_visible = True
		entry.has_enabled = True
		entry.has_ik = False
		entry.inherit_rot = False
		entry.inherit_trans = False
	
	
	from _prune_unused_bones import prune_unused_bones, delete_multiple_bones
	print("-- Prune original ones")
	prune_unused_bones(pmx, True)
	
	print("-- Scan again....")
	foundNether = []
	for _bone in pmx.bones:
		_name = _bone.name_jp
		if _name.startswith("DELME_") or "DELME" in _bone.name_en: ###
			print(f"Found deletable bone '{_name}'.....")
			delList.append(find_bone(pmx, _name, False))
		elif _name.endswith("*1"): ## Minor optimization
			_par = util.get_idx_and_name(pmx, _bone.parent_idx, False)
			if _par[0] == -1: continue
			if not _name.startswith(_par[1]): continue
			print(f"Found Acc-Optimization '{_par[1]}' <- '{_name}'.....")
			_own = find_bone(pmx, _name)
			kkrig.ReplaceAllWeights(pmx, _own, _par[0])
			_bone.name_jp = "DELME_" + _bone.name_jp + "--AccOpt"
			delList.append(_own)
		elif _name.startswith("a_n_"):
			# If invisible, then it had no children
			if not _bone.has_visible: delList.append(find_bone(pmx, _name))
			else:
				_bone.name_jp = re.sub("a_n_", "AccGrp-", _name)
				_bone.has_visible = False
				_bone.tail_usebonelink = True
				_bone.tail = -1
		elif _name.startswith("cf_hit_"):
			_bone.name_jp = re.sub("cf_hit_", "PhyAnchor-", _name)
			_bone.has_visible = False
		elif _name.startswith("cf_J_Vag"): foundNether.append(_bone)
			
	delete_multiple_bones(pmx, delList)
	
	if any(foundNether):
		_curIdx = find_bone(pmx, foundNether[0].name_jp, False)
		_pos = pmx.bones[_curIdx].pos
		_newPar = add_bone(pmx, name_jp=f"NetherBone", _solo=True)
		insert_single_bone(pmx, _newPar, _curIdx)
		
		_par = pmx.bones[find_bone(pmx, "RightUpperLeg")]
		_newPar.pos        = [_pos[0], _pos[1], _par.pos[2]]
		_newPar.parent_idx = _par.parent_idx
		_idx = find_bone(pmx, _newPar.name_jp)
		for b in foundNether: b.parent_idx = _idx
	##--- Then it is equally likely that we still have chest physics
	if find_bone(pmx, "AH1_L", False) == -1:
		util.set_parent_if_found(pmx, "左胸操作", n["UpperChest"], True)
		util.set_parent_if_found(pmx, "左AH1", "Breast.L", True)
		util.set_parent_if_found(pmx, "左AH2", "Breast.L", True)
		util.set_parent_if_found(pmx, "左胸操作接続", "Breast.L", True)
		util.set_parent_if_found(pmx, "左胸操作衝突", "Breast.L", True)
		util.set_parent_if_found(pmx, "右胸操作", n["UpperChest"], True)
		util.set_parent_if_found(pmx, "右AH1", "Breast.R", True)
		util.set_parent_if_found(pmx, "右AH2", "Breast.R", True)
		util.set_parent_if_found(pmx, "右胸操作接続", "Breast.R", True)
		util.set_parent_if_found(pmx, "右胸操作衝突", "Breast.R", True)
	
	#print("Delete kokan and other genital bones")
	#print("Simplify Chest")
	
	def rebind_Collider(target, newParent):
		_idx = find_bone(pmx, target, False)
		if _idx != -1:
			pmx.bones[_idx].parent_idx = newParent
	rebind_Collider("Collider Leg_L", n["LeftLowerLeg"])
	rebind_Collider("Collider Leg_R", n["RightLowerLeg"])
	
	if not util.is_univrm():
		print(f"==== Stage 8: Morphs & Cleanup")
		from kkpmx_morphs import OPT_sort_useVRC, OPT_sort_delVMorph
		prepare_for_export(pmx)
		
		flag_pruneVMorphs = util.ask_yes_no("-- Delete Morph-Components? [Allows assembling custom expressions, but heavy]")
		if util.ask_yes_no("-- Delete all Physics (RBodies/Joints)? [Discarded on Blender import anyway]", "y"):
			pmx.rigidbodies = []
			pmx.joints = []
		flag_pruneDispFrames = util.ask_yes_no("-- Delete all Displayframes? [Discarded on Blender import anyway]", "y")
		_optSort = {
			OPT_sort_useVRC: True,
			OPT_sort_delVMorph: flag_pruneVMorphs
		}
		sort_morphs(pmx, _optSort)
		if flag_pruneDispFrames: pmx.frames = []
	

	return end(pmx if True else None, input_file_name, "_export", ["Did stuff"])
rename_bones_for_export.__doc__ = """

Transforms a MMD style model into a VRC style model.
Afterwards it can be imported into Blender and re-exported as FBX

Actions:
-- Removes NSFW Bones for VRC ToS compliance (prompts to keep)
-- Rename Armature for Humanoid Skeleton
-- Reorder into expected Hierarchy
-- Merges most body/facial bones as required
-- -- Accessories are left in as-is as an exercise for the user
-- Assembles basic morphs for VRC (AEIOU Blink Smile)
-- Converts all Group Morphs into Vertex Morphs
-- Removes all non-Vertex Morphs

[Options] (at the end):
-- Asks if former Group-Components should be deleted or kept
-- Asks if all Physics(RBod/Joints) should be deleted (ignored by FBX)
-- Asks if all Displayframes should be deleted (ignored by FBX)

[Output]: PMX file '[modelname]_export.pmx'
"""

def tempTwist(pmx, input_filename_pmx): ## Untwist ArmTwist for Reexport of VRM into Blender
	def find_either(name_jp, name_en):
		idx = find_bone(pmx, name_jp, False);
		if idx != -1: return idx
		return find_bone(pmx, name_en);
	def runRepl(twist, arm):
		if arm == -1: return
		if twist != -1: kkrig.ReplaceAllWeights(pmx, twist, arm)
	##: Legacy Remark: Original func only added all 4 wrist twist to LeftLowerArm and RightLowerArm
	x = """
	Shoulder
	: Upper Arm                                             
	: : Lower Arm                                           
	: : : Hand                                              
	: : : wrist_twist >> wrist                                                      :: onto Hand
	: : : wrist_twist 2 >> cf_hit_wrist_R                   Adds 0.50               :: onto Hand
	: : : wrist_twist 3 >> cf_d_wrist_R                     Adds 0.75               :: onto Hand
	: : : wrist_twist 1                                     Adds 0.25               :: onto Hand
	: : arm_twist                                           
	: : : elbow_R_Rot >> cf_s_elbo_R, cf_s_elboback_R       0.5 onto Lower Arm		:: onto Lower Arm
	: : arm_twist 1                                         Adds 0.25
	: : arm_twist 2                                         Adds 0.50
	: : arm_twist 3                                         Adds 0.75
	: : cf_hit_**                                           
	: shoulder_R_solo >> cf_s_shoulder02_R                  						:: onto Upper Arm
	
	"""
	
	# Test:: Shoulder_solo part of Upper Arm
	
	## Lower Arm with all 4 arm twists
	## Hand with main + 2 + 3 wrist twists 
	#elbow_L = find_either("左ひじ", "LeftLowerArm");
	elbow_L = find_either("左ひじ", "LeftUpperArm");
	runRepl(find_either("左腕捩",  "arm twist_L"),  elbow_L)
	runRepl(find_either("左腕捩1", "arm twist_L1"), elbow_L)
	runRepl(find_either("左腕捩2", "arm twist_L2"), elbow_L)
	runRepl(find_either("左腕捩3", "arm twist_L3"), elbow_L)
	
	#hand_L = find_either("左手首", "LeftHand");
	hand_L = find_either("左手首", "LeftLowerArm");
	runRepl(find_either("左手捩",  "wrist twist_L"),  hand_L)
	runRepl(find_either("左手捩1", "wrist twist_L1"), hand_L)
	runRepl(find_either("左手捩2", "wrist twist_L2"), hand_L)
	runRepl(find_either("左手捩3", "wrist twist_L3"), hand_L)
	
	#elbow_R = find_either("右ひじ", "RightLowerArm");
	elbow_R = find_either("右ひじ", "RightUpperArm");
	runRepl(find_either("右腕捩",  "arm twist_R"),  elbow_R)
	runRepl(find_either("右腕捩1", "arm twist_R1"), elbow_R)
	runRepl(find_either("右腕捩2", "arm twist_R2"), elbow_R)
	runRepl(find_either("右腕捩3", "arm twist_R3"), elbow_R)
	
	#hand_R = find_either("右手首", "RightHand");
	hand_R = find_either("右手首", "RightLowerArm");
	runRepl(find_either("右手捩",  "wrist twist_R"),  hand_R)
	runRepl(find_either("右手捩1", "wrist twist_R1"), hand_R)
	runRepl(find_either("右手捩2", "wrist twist_R2"), hand_R)
	runRepl(find_either("右手捩3", "wrist twist_R3"), hand_R)
	
	
	if (input_filename_pmx is None): return
	return end(pmx, input_filename_pmx, "_fixed", "Swapping Twist")


def prepare_for_export(pmx, isVRC=True): ## TODO: Remap the manually translated morphs from [core] or remove them
	from kkpmx_morphs import translateItem, addOrReplace, make_vert_morph, infixes, make_vert_item
	from _translation_tools import is_jp, is_latin
	if not isVRC:
		for morph in pmx.morphs:
			morph.name_jp = translateItem(morph.name_jp)
			morph.name_en = translateItem(morph.name_en, True)
		
	### -- Generate the basic VRM ones at least
	arr = [[],[]]
	addOrReplaceEye   = lambda jp,en,it: addOrReplace(pmx, jp, en, 2, it, morphtype=1)
	addOrReplaceMouth = lambda jp,en,it: addOrReplace(pmx, jp, en, 3, it, morphtype=1)
	addOrReplaceBrow  = lambda jp,en,it: addOrReplace(pmx, jp, en, 1, it, morphtype=1)
	addOrReplaceOther = lambda jp,en,it: addOrReplace(pmx, jp, en, 4, it, morphtype=1)
	
	print(f"=== Generate VRC Morphs ===")
	holder = {"newMorphs": [], "skipCombine": not isVRC}
	
	def combine_morph(srcJP, srcEN, dst, callback):
		if holder["skipCombine"]: return
		print(f"= Combine {srcJP}....")
		def gather(srcJP, srcEN):
			m_idx = find_morph(pmx, srcJP, False)
			if m_idx == -1:
				m_idx = find_morph(pmx, srcEN, True)
				if m_idx == -1: return None
			grp_morph = pmx.morphs[m_idx]
			if grp_morph.morphtype != 0: return None ## 0 = Group, 1 = Vertex
			return grp_morph.items
		_arr = []; morphs = []
		if type(srcJP) is type(""):
			morphs = gather(srcJP, srcEN)
		else:
			for m in srcJP:
				x = gather(m, m)
				if not x is None: morphs += x
		## Idea of own method was that some of the groups could be nested? only do if actually required
		def combine_group(__arr, _grp_morph):
			if _grp_morph is None: return
			for grp in _grp_morph:
				(grpIdx, grpVal) = (grp.morph_idx, grp.value)
				
				#print(f"Generate with GroupIdx '{grpIdx}' = {grpVal} from ({srcJP}, {srcEN})")
				
				if grpVal == 1: __arr += [x for x in pmx.morphs[grpIdx].items] ## Make a copy
				elif grpVal == 0: pass
				elif grpIdx == -1:
					print(f"Invalid GroupIdx '-1' from ({srcJP}, {srcEN})")
				else:
					_arr2 = []
					for i in pmx.morphs[grpIdx].items:
						try:
							(x,y,z) = (i.move[0], i.move[1], i.move[2])
							_arr2.append(pmxstruct.PmxMorphItemVertex(i.vert_idx, [x * grpVal, y * grpVal, z * grpVal]))
						except Exception as ex:
							print(f"-- Error in Group: {grp}")
							print(i)
							raise
					__arr += _arr2
		combine_group(_arr, morphs)
		#print(f"Call callback for {srcJP}/{srcEN} with {len(_arr)}")
		#holder["newMorphs"].push((dst, _arr, callback))
		if isVRC: callback(dst, dst, _arr)
		else: callback(srcJP, srcEN, _arr)
	## // https://docs.vrchat.com/docs/avatars-30#blendshape--bone-based-visemes
	#---- https://visagetechnologies.com/uploads/2012/08/MPEG-4FBAOverview.pdf
	#---- https://docs.vrcft.io/docs/tutorial-avatars/tutorial-avatars-extras/unified-blendshapes#ue-blended-shapes
	##:: Eye Viseme
	combine_morph("あ", "A", "vrc.aa", addOrReplaceMouth)   ## A:  \\ car
	combine_morph("え", "E", "vrc.e", addOrReplaceMouth)    ## e   \\ bed
	combine_morph("い", "I", "vrc.ih", addOrReplaceMouth)   ## ih  \\ tip
	combine_morph("お", "O", "vrc.oh", addOrReplaceMouth)   ## oh  \\ toe
	combine_morph("う", "U", "vrc.ou", addOrReplaceMouth)   ## ou  \\ book
	combine_morph("ん", "N", "vrc.nn", addOrReplaceMouth)   ## n,l \\ lot, not
	##sil = silence   \\ << neutral >> 
	##PP  = p, b, m   \\ put, bat, mat     \\ Press lips together
	##FF  = f, v      \\ fat, vat          \\ Front teeth on lower lip
	##TH  = th        \\ think, that       \\ half curved upper, open lower lip, tongue behind upper
	##DD  = t, d      \\ tip, doll         \\ curved upper, exposed lower teeth, tongue behind upper
	##kk  = k, g      \\ call, gas         \\ curved upper, exposed lower teeth, tongue pulled behind
	##CH  = tS, dZ, S \\ chair, join, she  \\ Roof upper, rolled down lower lip
	##SS  = s, z      \\ sir, zeal         \\ snake sssssss
	##RR  = r         \\ red               \\ Arrrrrrrrrr
	
	##:: Eyelid Blendshapes
	combine_morph("まばたき", "Blink", "vrc.blink", addOrReplaceEye)
	## "LookingUp", "LookingDown",
	
	##----- Others
	combine_morph("ウィンク", "Wink", "vrc.EyeClosedLeft", addOrReplaceEye)
	combine_morph("ウィンク右", "Wink R", "vrc.EyeClosedRight", addOrReplaceEye)
	combine_morph("笑い", "Smile", "vrm.smile", addOrReplaceEye) ## smile
	combine_morph("怒り", "Angry", "vrm.angry", addOrReplaceEye) ## ikari
	
	combine_morph("[E] _setunai", "[E] Sad", "vrm.sad", addOrReplaceEye)
	combine_morph("[E] _rakutan", "[E] Upset", "vrm.upset", addOrReplaceEye)
	#combine_morph(["[E] _tere", "[M] _pero_cl", "[M] TongueOut (closed)"], "", "vrm.tongue", addOrReplaceMouth)
	#combine_morph([
	#	"[E] _doya", "[M] _doya_cl"
	#], "", "vrm.smug", addOrReplaceMouth)
	tlDict = { x[0]: x[1] for x in infixes }
	tabu = {}
	sortList = { "B":[], "E":[], "M":[], "O":[] }
	holder["skipCombine"] = False
	for m in pmx.morphs:
		# Reduce name
		name = m.name_jp
		if not name.startswith("["):
			if isVRC or is_latin(name): continue
			prefix = {1: "B", 2: "E", 3: "M"}.get(m.panel, "O")
			print(f"> Identify morph {name} as {prefix}")
		else: prefix   = name[1]; name = name[4:]
		isOpen   = name.endswith("_op")
		isClosed = name.endswith("_cl")
		if isOpen or isClosed: name = name[:-3]
		
		data = [m.name_jp, m.name_en]
		if   prefix == "M": data += ["Mouth.", addOrReplaceMouth]
		elif prefix == "E": data += ["Face.",  addOrReplaceEye  ]
		elif prefix == "B": data += ["Brow.",  addOrReplaceBrow ]
		else              : data += ["Other.", addOrReplaceOther]
		if name in tlDict: data[2] += tlDict[name]
		else: data[2] += name
		if isOpen: data[2] += ".Open"
		if isClosed: data[2] += ".Closed"
		
		## Handle duplicates
		x = data[2]
		if x in tabu:
			data[2] = x + "*" + str(tabu[x])
			tabu[x] += 1
		else: tabu[x] = 1
		sortList[prefix].append(data)
	for mList in sortList.values(): ## Sort by Brow Eye Mouth
		mList.sort(key=lambda v: v[2]) ## Sort by final Name
		for data in mList: combine_morph(*data)
	###########
	return
	###########
	## Calc hitomi-small
	eyeL = find_mat(pmx, "Eye.Left")
	if eyeL == -1: eyeL = find_mat(pmx, "LeftEye")
	if eyeL == -1: eyeL = find_mat(pmx, "cf_m_hitomi_00")
	eyeR = find_mat(pmx, "Eye.Right")
	if eyeR == -1: eyeR = find_mat(pmx, "RightEye")
	if eyeR == -1: eyeR = find_mat(pmx, "cf_m_hitomi_00*1")
	
	shift_by_Y = (0.03563594)*3.5
	def adjust_pos(items):
		pass
		for item in items:
			item.move[1] -= shift_by_Y
	
	def calc_one_eye_X(idx, name):
		if idx == -1: return
		##### I guess..? Everything is gone at Change=0.40, but otherwise works...
		(verts, bounds) = util.get_vertex_box(pmx, idx, True)
		# Get far left & right
		farLeft = bounds["Left"][0]; farRight = bounds["Right"][0]
		# Get center
		center = (farLeft + farRight) / 2
		# set target width -> get ratio
		orgWidth    = (farLeft + abs(farRight)) if farLeft > 0 else abs(farLeft - farRight)
		targetRatio = 0.60
		# Calc % of pos between original -> mul by ratio
		items = []
		
		relLeft  = max(farLeft, center) - min(farLeft, center)
		relRight = (max(farRight, center) - min(farRight, center))
		for vert_idx in verts:
			vert = pmx.verts[vert_idx]
			pos_x = vert.pos[0]
			if pos_x > center: ## is left of Center
				# Get Pos to farLeft: ((-2) - (-3)) = 1
				relPos = (pos_x - center) / relLeft
				newPos = relPos * targetRatio
				move = [-newPos, 0, 0]
				items.append(make_vert_item(pmx, vert_idx, move))
			else:
				relPos = (center - pos_x) / relRight
				newPos = relPos * targetRatio
				move = [+newPos, 0, 0]
				items.append(make_vert_item(pmx, vert_idx, move))
		adjust_pos(items)
		make_vert_morph(pmx, name, items, True)
	def calc_one_eye_Y(idx, name):
		if idx == -1: return
		##### I guess..? Everything is gone at Change=0.40, but otherwise works...
		(verts, bounds) = util.get_vertex_box(pmx, idx, True)
		# Get far left & right
		farLeft = bounds["Up"][1]; farRight = bounds["Down"][1]
		# Get center
		center = (farLeft + farRight) / 2
		# set target width -> get ratio
		orgWidth    = (farLeft + abs(farRight)) if farLeft > 0 else abs(farLeft - farRight)
		targetRatio = 0.60
		# Calc % of pos between original -> mul by ratio
		items = []
		
		relLeft  = max(farLeft, center) - min(farLeft, center)
		relRight = (max(farRight, center) - min(farRight, center))
		for vert_idx in verts:
			vert = pmx.verts[vert_idx]
			pos_x = vert.pos[1]
			if pos_x > center: ## is left of Center
				# Get Pos to farLeft: ((-2) - (-3)) = 1
				relPos = (pos_x - center) / relLeft
				newPos = relPos * targetRatio
				move = [0, -newPos, 0]
				items.append(make_vert_item(pmx, vert_idx, move))
			else:
				relPos = (center - pos_x) / relRight
				newPos = relPos * targetRatio
				move = [0, +newPos, 0]
				items.append(make_vert_item(pmx, vert_idx, move))
		adjust_pos(items)
		make_vert_morph(pmx, name, items, True)
	calc_one_eye_X(eyeL, "vrm.hitomiX-small-left")
	calc_one_eye_X(eyeR, "vrm.hitomiX-small-right")
	calc_one_eye_Y(eyeL, "vrm.hitomiY-small-left")
	calc_one_eye_Y(eyeR, "vrm.hitomiY-small-right")
############################
def run__vrcMorphs(pmx, input_file_name):
	from kkpmx_core import end
	from kkpmx_morphs import OPT_sort_useVRC, OPT_sort_delVMorph
	prepare_for_export(pmx, False)

	flag_pruneVMorphs = util.ask_yes_no("-- Delete Morph-Components? [Allows assembling custom expressions, but heavy]")
	_optSort = {
		OPT_sort_useVRC: False,
		OPT_sort_delVMorph: flag_pruneVMorphs
	}
	sort_morphs(pmx, _optSort)
	return end(pmx if True else None, input_file_name, "_baked", ["Baked Expression Morphs", f"Sorted Morphs: {_optSort}"])
run__vrcMorphs.__doc__ = """

Bakes ALL group morphs into singular vertex morphs.
Remark: In contrast to VRC-Converter, this one does NOT delete non-Vertex morphs.

[Options] (at the end):
-- Asks if pre-baking Group-VertexMorphs should be deleted or kept

To be specific, selecting "Yes" deletes all VertexMorphs except if
- name_jp contains CN, JP, or KR characters
- name_jp starts with "[x]", x being any of a-zA-Z0-9_
- the morph is part of the "AuxMorphs" Displayframe

Please keep an unbaked backup until you are certain all morphs behave as needed

[Output]: PMX file '[modelname]_baked.pmx'
"""