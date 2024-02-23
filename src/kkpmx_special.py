# Cazoo - 2022-12-17
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

#### Special Morphing

def chooser():
	## Choose between the options
	pass



######################
### Morph Body
######################

def scan_for_special(pmx):
	add_chest_morph(pmx)
	add_nether_morph(pmx)
	######
	pass##


def add_chest_morph(pmx):
	from kkpmx_core import __append_bonemorph
	nameOut = "chikubi_out"
	nameIn = "chikubi_in"
	arrZero  = [  0,   0,   0]
	
	if find_bone(pmx, "cf_j_bnip02root_L", False) == -1: return
	
	#####
	## Create Morph
	arrIN = []; arrOUT = []
	def createMorph(sfx, arrIN, arrOUT):
		rootIdx = find_bone(pmx, "cf_j_bnip02root_" + sfx)
		idxPeak = find_bone(pmx, "cf_j_bnip02_" + sfx)
		idxAreo = find_bone(pmx, "cf_s_bnip025_" + sfx)
		idxArea = find_bone(pmx, "cf_s_bnip01_" + sfx)
		posRoot = pmx.bones[rootIdx].pos
		posPeak = pmx.bones[idxPeak].pos
		posAreo = pmx.bones[idxAreo].pos
		posArea = pmx.bones[idxArea].pos
		
		# Tip - Root: for expand \\ inv(that): for retract
		# idxAreo * 0.07 of that... but was based on x5
		movOUT  = util.arrSub(posPeak, posRoot)
		movIN   = util.arrInvert(movOUT)
		movINA = util.arrMul(movIN, 0.075*5)
		movOUA = util.arrMul(movOUT, 0.075*5)
		
		__append_bonemorph(arrIN, idxPeak, movIN, arrZero)
		__append_bonemorph(arrIN, idxAreo, movINA, arrZero)
		__append_bonemorph(arrIN, idxArea, movIN, arrZero)
		
		__append_bonemorph(arrOUT, idxPeak, movOUT, arrZero)
		__append_bonemorph(arrOUT, idxAreo, movOUA, arrZero)
		__append_bonemorph(arrOUT, idxArea, movOUT, arrZero)
	##--------
	createMorph("L", arrIN, arrOUT); createMorph("R", arrIN, arrOUT)
	__append_bonemorph(pmx, idx=find_morph(pmx, nameIn, False), name=nameIn, arr=arrIN)
	__append_bonemorph(pmx, idx=find_morph(pmx, nameOut, False), name=nameOut, arr=arrOUT)

def alt_chest_bounce(): pass ## Impl. that other bounce system

## Insert Nether bones myself if missing ?

def add_nether_morph(pmx):
	name = "OwO Morph"
	if find_morph(pmx, name, False) == -1:
		if find_bone(pmx, "cf_J_Vagina_L.001", False) == -1: return
		pmx.morphs.append(pmxstruct.PmxMorph(name, name, 4, 2, [
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_F",     False), [ 0.00,0,0], [-45,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_L.001", False), [ 0.15,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_L.002", False), [ 0.15,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_L.003", False), [ 0.10,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_L.004", False), [ 0.05,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_L.005", False), [ 0.05,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_R.005", False), [-0.05,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_R.004", False), [-0.05,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_R.003", False), [-0.10,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_R.002", False), [-0.15,0,0], [  0,0,0]),
			pmxstruct.PmxMorphItemBone(find_bone(pmx, "cf_J_Vagina_R.001", False), [-0.15,0,0], [  0,0,0]),
		]))

## Super Simplifier
def simplify_armature(pmx, input_file_name, _opt = { }):
	from kkpmx_core import end
	from kkpmx_rigging import get_children_map, patch_bone_array, cleanup_free_things
	weightMap = {}          # Dict[int, int]: Replace all X with Y in vertex weights
	persistList = []        # List[int]: Actually does nothing?
	checkSlot = []          # List[int]: Parse Bone Tree from X downwards and only keep those with weights
	### Replace influence from Y if X is major bone
	vertReplacer_List = []  # List[int]: if first bone is in this list, apply rules
	vertReplacer_Rules = [] # List[Tuple[int, int]]: Arguments for process_weight_if_major
	## start at cf_s_head
	##  - keep cf_J_CheekUp_s_L & cf_J_CheekUp_s_R (both child of cf_J_CheekUpBase)
	## -  Keep Mouth Vertices separate (cf_J_MouthBase_ty) completely // but idk if they can be used, visemes are better
	## -  Keep Chin bones separate, but merge into one		// Seems to have Mouth vertices too, clean up
	## (def RemoveFromOrg): set WeightMap to self, add to [persistList]	### reference the initial map
	verbose = util.is_verbose() or _opt.get(util.OPT_INFO, False)
	def RemoveFromOrg(bones, opt=None):
		if verbose:
			if opt: print(f"Update {opt} to keep:\n{bones}")
			else:   print(f"Update these to stay:\n{bones}")
		for idx in bones:
			if idx == -1: continue
			weightMap[idx] = idx
			persistList.append(idx)
	## (def RemoveAndMerg): set WeightMap to first Bone, add first to [persistList] with optional extra name
	def RemoveAndMerg(bones, keepIdx=-1):
		if not bones and keepIdx == -1: return
		first = bones[0] if keepIdx == -1 else keepIdx
		if verbose: print(f"Update these to be first:\n[{first}]: {bones[1:] if keepIdx == -1 else bones}")
		for idx in bones:
			weightMap[idx] = first
		persistList.append(first)
	##-------
	if util.is_auto():
		flag_SFW = False
		flag_all = True
	else:
		flag_SFW = util.ask_yes_no("Merge certain Bones for SFW export", "n")
		flag_all = util.is_allYes() or util.ask_yes_no("Simplify everything", "n")
	##-------
	## Collect all bones under [start]
	fullMap = get_children_map(pmx, None, False, True)
	
	headMap = fullMap["cf_s_head"]
	headIdx = headMap[0]
	## Iterate list of bones
	for boneIdx in headMap:
	##-- Set in WeightMap to start
		if boneIdx in weightMap: continue
		weightMap[boneIdx] = headIdx
		newParent   = headIdx
		bone        = pmx.bones[boneIdx]
		boneName    = bone.name_jp
		processBone = False
	##-- RemoveAndMerg: if name == cf_J_FaceLow_sx, remove SubTree & add as MergeBlock
		if boneName =="cf_J_FaceLow_sx" or boneName == "cf_J_LowerFace":
	##-- RemoveFromOrg: Remove the two Cheek bones & take out from MergeBlock
			bone.parent_idx = headIdx
			RemoveAndMerg(fullMap[boneName])
			bone.name_jp = "cf_J_LowerFace"
			bone.name_en = "cf_J_LowerFace"
			bone  = util.find_bone(pmx, "cf_J_CheekUp_s_L")
			bone2 = util.find_bone(pmx, "cf_J_CheekUp_s_R")
			#---- Keep the cheek separate since it looks a bit more natural I guess?
			pmx.bones[bone].parent_idx  = headIdx
			pmx.bones[bone2].parent_idx = headIdx
			RemoveFromOrg([bone, bone2])
			continue
		elif boneName == "cf_J_MouthBase_ty": processBone = True
		elif boneName.startswith("a_n_"):    bone.parent_idx = headIdx
		elif boneName.startswith("ca_slot"): processBone = True; newParent = bone.parent_idx; checkSlot.append(boneIdx)
		elif boneName.startswith("ct_hair"): processBone = True
		elif boneName == "左目": processBone = True
		elif boneName == "右目": processBone = True
		elif boneName == "cf_J_Mayu_ty": bone.parent_idx = headIdx; ## Keep this as common parent instead of reassign each brow
		elif boneName in ["cf_J_Mayumoto_L", "cf_J_Mayumoto_R"]: RemoveAndMerg(fullMap[boneName]); continue
		if processBone: bone.parent_idx = newParent; RemoveFromOrg(fullMap[boneName], boneName); continue
	##--------
	## Add extra parts (that might as well be elsewhere but are here for now out of convenience)
	##-- Just in case these already exist to begin with
	if util.find_bone(pmx, "cf_j_toes_L"):
		bones = util.find_bones(pmx, ["右足首D", "右足先EX", "cf_j_toes_R", "左足首D", "左足先EX", "cf_j_toes_L"], False)
		if bones[1] != -1:
			if bones[0] != -1: weightMap[bones[1]] = bones[0] ## Cleanup weird side piece not being added
			if bones[2] != -1: weightMap[bones[2]] = bones[1] ## Move Toes to D-Bone Toes
		if bones[4] != -1: 
			if bones[3] != -1: weightMap[bones[4]] = bones[3] ## Cleanup weird side piece not being added
			if bones[5] != -1: weightMap[bones[5]] = bones[4] ## Move Toes to D-Bone Toes
	# Find vertices with dominant "右足首D" and remove influence of cf_s_leg01_L for the same reason
	_bones = util.find_bones(pmx, ["右足首D", "cf_s_leg01_L", "左足首D", "cf_s_leg01_R"], False)
	vertReplacer_List += [_bones[0], _bones[2]]
	vertReplacer_Rules.append((_bones[0], _bones[1])); vertReplacer_Rules.append((_bones[2], _bones[3]))
	
	#--##--#
	boneIdx = find_bone(pmx, "cf_s_waist02")
	flagWaist = False
	if flag_SFW:
		RemoveAndMerg(fullMap["cf_d_bust00"])                         ## Chest
		RemoveAndMerg(fullMap.get("cf_J_Vagina_root", []), boneIdx)   ## Nether (true child of cf_s_waist02)
	if flag_SFW or flag_all or util.ask_yes_no("Simplify waist area", "n"):
		## Nether (actually children of cf_j_waist02 but that is no vertex bone) -- will also merge nether Slots
		RemoveAndMerg(fullMap.get("cf_d_ana",         []), boneIdx)   ## Butt
		RemoveAndMerg(fullMap.get("cf_d_kokan",       []), boneIdx)   ## Groin
		## Simplify Butt
		checkSlot.append(find_bone(pmx, "cf_d_siri_L"))
		checkSlot.append(find_bone(pmx, "cf_d_siri_R"))
		flagWaist = True
	
	#""" - "Merge Knee bones": Merge extra knee bones into the leg"""
	#if !flag_all or util.ask_yes_no("Merge Knee bones", "n"):
	#	bones = util.find_bones(pmx, ["cf_s_leg01_L", "cf_s_kneeB_L", "cf_d_kneeF_L",], False)
	#	if bones[0] != -1: weightMap[bones[1]] = bones[0]; weightMap[bones[2]] = bones[0]
	#	bones = util.find_bones(pmx, ["cf_s_leg01_R", "cf_s_kneeB_R", "cf_d_kneeF_R",], False)
	#	if bones[0] != -1: weightMap[bones[1]] = bones[0]; weightMap[bones[2]] = bones[0]
	
	if flag_all or util.ask_yes_no("Merge Toe Bones", "n"):
		RemoveAndMerg(fullMap["cf_j_toes_L"])
		RemoveAndMerg(fullMap["cf_j_toes_R"])
		flagToes = True
	
	#--##--#
	if flag_all or util.ask_yes_no("Simplify non-head slots too", "y"):
		for boneIdx in range(len(pmx.bones)):
			if boneIdx in weightMap: continue
			bone        = pmx.bones[boneIdx]
			boneName    = bone.name_jp
			processBone = False
	
			if boneName.startswith("ca_slot"): processBone = True; newParent = bone.parent_idx; checkSlot.append(boneIdx)
			if processBone:
				if verbose: print(f">> Handle slot {boneName}...")
				weightMap[boneIdx] = boneIdx
				bone.parent_idx = newParent;
				RemoveFromOrg(fullMap[boneName]);
	#--##--#
	## Iterate Weights:
	##-- check each weight and replace each bone with the respective from WeightMap
	usedBones = []
	checkVerts = []
	def weightFunc(x):
		usedBones.append(x)
		return weightMap.get(x, x)
	for vert in pmx.verts:
		util.process_weight(vert, weightFunc)
		if vert.weight[0] in vertReplacer_List: checkVerts.append(vert)
	for rule in vertReplacer_Rules:
		util.process_weight_if_major(checkVerts, rule[0], rule[1])
	
	###############
	### Do the actual cleanup magic
	###############
	### Prep some functions
	def checkDiff(name):
		parList = fullMap.get(name, [])
		if len(parList) <= 1: return (-1, []) ## Always min 1 bc adding own
		firstName = pmx.bones[parList[1]].name_jp
		childMap  = fullMap.get(firstName, [])
		return (len(parList) - len(childMap), childMap)
	######
	def reduceSlots(_arr, _idx):
		_RB = [x for x in _arr if x.bone_idx == _idx]  ## Use the current bone, since we want to clean that up
		if len(_RB) > 0: return (True, _RB[0])
		return (False, None)
	######
	keepSlotRoot   = False
	enableMulti    = True                 ## TestFlag: Fix chains where the nothing is used till a split
	enableMultiRec = enableMulti and True ## TestFlag: Append Splits as new individual chains
	enableFixSolo  = True
	_superLoc  = None; _superLoc = [item for item in locals().keys()]
	multiList  = [] # Keep track of subtree indices added to checkSlot
	multiSlot  = {} # For unique splitnames, keep track how many subchains of this slot have been processed
	multiMap   = {} # Based on the [multiList] Idx, return the original slot & boneName (in case it was replaced)
	soloFixMap = {} # Map for additional edits of chains only using the last bone
	for idx in checkSlot:
		slotName  = pmx.bones[idx].name_jp ## The original Slot Name for Physics
		slotRB    = util.find_all_in_sublist(slotName, pmx.rigidbodies, False)[1:] ## Skip the _r one
		parIdx    = idx
		resetName = False
		myMap     = fullMap[slotName]
		##-- Add the ca_slot into usedBones for now
		orgPar  = idx if parIdx in multiList else -1
		orgName = slotName
		doPrint = False#"ca_slot16" in slotName or "ca_slot14" in slotName # or orgPar != -1
		if orgPar != -1: ### If we are in a nested Split, make the bone name reference it correctly
			(multName, oldName) = multiMap[orgPar]
			multIdx  = multiSlot[multName]
			if doPrint: print(f"\n:>>A {idx}=[{slotName}] = {myMap}")
			slotName = f"{multName}.{multIdx}"
			multiSlot[multName] = multiSlot[multName] + 1
			usedBones.append(idx) ## Important else it will be reset to OrgParent (citation-needed)
			## Repair things
			myMap    = fullMap[oldName] ## use the correct Map
			slotRB   = util.find_all_in_sublist(oldName, pmx.rigidbodies, False)
			####
		doPrint = False
		
		if doPrint: print(f":--- Start {idx}: {slotName} (in multiList: {orgPar != -1})")
		###--- [A] Keep ca_slot (use this for Tails ?)
		if keepSlotRoot: usedBones.append(idx)
		###--- [B] Treat it as any other
		elif idx not in usedBones:
			parIdx = pmx.bones[idx].parent_idx
			resetName = True
		
		newParent        = False # Set True if the next used bone should set a new parent
		hadOneUsedParent = False # Set true if next should reconnect to previously existing rigid
		storedRbkID      = -1    # Store the RigidBody in question
		locIdx           = 0     # Only used for debugging
		if doPrint: print(f":>>B {idx}=[{slotName}] = {myMap}")
		for boneIdx in myMap:
			bone     = pmx.bones[boneIdx] ## [Current bone]: Check if this bone is used -- Root of RigidBody
			boneName = bone.name_jp
			isMulti  = False
			processSplit = False
			(diff, cMap) = checkDiff(boneName)
			locIdx = locIdx + 1
			
			#TODO: Missing CASE: Solo Chain of used, then unused, and then Tail Bone
			# Tail is reparented to grandparent, but parent stays because of existing rigid (and also keeps them as they are)
			
			#-- We reached a Leaf end (aka no branching nodes) ==> [CASE]: >onto> TailBone
			if diff < 1:
				if doPrint: print(f": Check {boneIdx}: {boneName} with delta={diff} >> {cMap} (SoleNode={newParent})")
				## ==> [CASE]: UnusedChain >onto> used TailBone
				#:: ParIdx = "a_n_", Idx = "ca_slot"=slotName, boneIdx = TailBone==bone
				if enableFixSolo and newParent: #==> [CASE]: UnusedChain >onto> used TailBone
					(rootIdx, tailIdx) = (idx, boneIdx)
					if doPrint: print(f":> Add Mapping to reduce {tailIdx}({bone.name_jp}) back to {rootIdx}({slotName})")
					soloFixMap[tailIdx] = rootIdx
					usedBones.append(rootIdx)
					if tailIdx in usedBones: usedBones.remove(tailIdx)
				elif newParent: ## If we do not keep the Slot Root, rename Tail into first
					if resetName: bone.name_jp = slotName
					bone.parent_idx = parIdx
				break
			#-- if sole child, and this was unused, keep parent & go to next
			#-- -OR- if we reach a split without ever reducing, then set that new root & stop ==> [CASE]: UnusedChain >onto> any SplitBone
			if (diff == 1) or (enableMulti and (diff > 1 and newParent)):
				if doPrint: print(f": Check {boneIdx}/{boneName} used: {boneIdx in usedBones} -- cIdx={cMap[0]} with Is Parent({parIdx}, {newParent} > {not boneIdx in usedBones})")
				cIdx = cMap[0] ## [child index]: First child since Parent that is used -- Target of RigidBody (will have FULL own subtree)
				isMulti = (diff > 1)
				
				(flag, editRB) = reduceSlots(slotRB, boneIdx)  ## Use the current bone, since we want to clean that up
				#[CASE] :: UnusedBone <after< UsedBone >followed-by> TailBone
				#> [Issue]: There is simply no "next bone" to reconnect onto since Tails are handled differently
				if (newParent == False) and (not boneIdx in usedBones) == True:
					if len(cMap) == 1: usedBones.append(boneIdx) ##[TEMP] Since it is not marked as used, patch it as such for now
				
				## A SplitBone is always considered used (all completely unused chains are already gone (citation-needed))
				if (enableMulti and isMulti): usedBones.append(boneIdx)
				## If this is unused, skip it and go to next ==> [CASE]: UnusedBone <after< UsedBone or UnusedBone
				if not boneIdx in usedBones: newParent = True
				## Else if used but at least one parent was not, rebind ==> [CASE]: UsedBone <after< UnusedBone
				elif newParent:
					newParent = False
					bone.parent_idx = parIdx
					### Rebind the Rigging if any
					##-Since this usually only happens on the first couple bones, this at least ensures it is clean....  (which sometimes is not the case)
					def doMagic(parIdx, boneIdx, cIdx, hadOneUsedParent, storedRbkID):
						## Make a chain between new parent and current bone -- Add child that marks it as used 
						if doPrint: print(f":: Edit RigidBody {editRB.name_jp} to be adjusted to the one from Current -> Child")
						
						patch_bone_array(pmx, None, [parIdx, boneIdx, cIdx], slotName + f"__XPBC_{cIdx}", editRB.group, False)
						newRB = pmx.rigidbodies[-2]
						editRB.pos   = newRB.pos
						editRB.rot   = newRB.rot
						editRB.size  = newRB.size
						editRB.shape = newRB.shape
						del pmx.rigidbodies[-4] ## the _root           -- Will be a Round Root Body
						del pmx.rigidbodies[-3] ## the parent          -- Will connect new Parent and Current
						del pmx.rigidbodies[-2] ## the main on boneIdx -- Will connect Current and Child (on most accs this was the weird one)
						del pmx.rigidbodies[-1] ## the tail on cIdx    -- Will be a Round Tail Body
						del pmx.joints[-1] ## Joints
						del pmx.joints[-1] ## Joints
						
						breakVar = 0
						#### if already had a used parent but then an unused inbetween, store the previous new rigidbody for that situation
						if not hadOneUsedParent: storedRbkID = find_rigid(pmx, editRB.name_jp)
						## on the child in question, get the joint that used this bone's rigid as rb2 and replace the first with said rigid above.
						if hadOneUsedParent:
							curRBId = find_rigid(pmx, editRB.name_jp)
							joints = [x for x in pmx.joints if x.rb2_idx == curRBId]
							if doPrint: print([x.name_jp for x in joints])
							if len(joints) == 0:
								print(f".... Uh, found no joints on {editRB.name_jp} to fix, so stop processing ")
								return (hadOneUsedParent, storedRbkID, -1)
							joints[0].rb1_idx = storedRbkID
							storedRbkID = -2
						## -OR- we are a split preparing for such a situation, so just treat like Fresh Multi
						elif (hadOneUsedParent == False and isMulti): ## [CASE]: UnusedChain >onto> SplitBone
							breakVar = 1
						
						hadOneUsedParent = True
						return (hadOneUsedParent, storedRbkID, breakVar)
					if flag:
						if not enableMulti:
							(hadOneUsedParent, storedRbkID, isBreak) = doMagic(parIdx, boneIdx, cIdx, hadOneUsedParent, storedRbkID)
							if isBreak == -1: break
						else:
							isBreak = 0
							for cIdx in cMap:
								(hadOneUsedParent, storedRbkID, isBreak) = doMagic(parIdx, boneIdx, cIdx, hadOneUsedParent, storedRbkID)
								if isBreak == -1 or (not isMulti): break ## Panic exit to avoid breaking more
								if storedRbkID == -2: break ## Unimplemented if empty bones happen inbetween multiple times, so just stop processing
								if isBreak != 0: break; ## Idk what I thought, but it works for now.
							if isBreak == -1: break;
					### Reset ParIdx since this is used
					if resetName:## If we do not keep the Slot Root, rename the first into it ==> [CASE]: >from> UnusedChain
						bone.name_jp = slotName
						resetName = False
					parIdx = boneIdx
					if enableMulti and isMulti: ## Set flag to share code between "from UsedBone" and "from UnusedChain"
						processSplit = True
				## Else if used and parent was too, push index ==> [CASE]: UsedBone >onto> UsedBone
				else: parIdx = boneIdx
			#-- If we reach a split, just stop and go to next slot. ==> [CASE]: UsedBone >onto> any SplitBone
			else:
				if doPrint: print(f": Check {boneIdx}: Push for nested Children of {slotName}")
				processSplit = True
			##----- [CASE]: Any >onto> SplitBone
			if processSplit:
				if enableMultiRec:
					if doPrint: print(f":> Evaluate {boneIdx} with {diff} subnodes for nested processing...")
					multiSlot[slotName] = 0
					for __idx in myMap: ## Actually add the children instead of redoing the SplitBone
						__tmp = pmx.bones[__idx]
						if doPrint: print(f":>>> Testing {__idx} = {__tmp.name_jp} with parent {__tmp.parent_idx}")
						if __tmp.parent_idx != boneIdx: continue
						extraIdx = __idx
						if doPrint: print(f":>>>> Pushing {extraIdx}")
						multiMap[extraIdx] = (slotName, __tmp.name_jp) ## Provide the original name to get the correct Map
						multiList.append(extraIdx)
						checkSlot.append(extraIdx)
				break
		##-- End Loop "for idx in fullMap[pmx.bones[idx].name_jp]"
		#: Set parent variables : newParent, hadOneUsedParent, storedRbkID
		#:    Scoped vars : cIdx, flag, editRB \\ newRB, breakVar
	##-- End Loop "for idx in checkSlot"
	#########
	
	from kkpmx_utils import process_weight
	## Feet: Some armatures have a certain patch on the other foot
	## Toes: Just for completion sake
	fb = lambda x: find_bone(pmx, x, True)
	fbx = lambda x: find_bone(pmx, x, False)
	idxArr = [fb("左足首"), fb("左つま先"), fb("右足首"), fb("右つま先")]
	## Leg: Has that same patch but correct side (but should be in foot)
	idxArr.append(fbx("cf_s_leg01_L"))
	idxArr.append(fbx("cf_s_leg01_R"))
	## Also move the KK Toes into proper Toes to allow D-Bones (if merged, else keep)
	if fbx("cf_j_toes0_R") == -1 or flagToes:
		toe = fbx("cf_j_toes_L")
		if toe != -1 and toe in usedBones: soloFixMap[toe] = idxArr[1]; usedBones.remove(toe)
		toe = fbx("cf_j_toes_R")
		if toe != -1 and toe in usedBones: soloFixMap[toe] = idxArr[3]; usedBones.remove(toe)
	
	(idx_LF,idx_LT,idx_RF,idx_RT,idx_LL,idx_RL) = idxArr
	threshold = pmx.bones[fb("右足ＩＫ")].pos[1]
	def replLeft(weight):
		if weight == idx_RF: return idx_LF
		if weight == idx_RT: return idx_LT
		if weight == idx_LL: return idx_LF
		return weight
	def replReight(weight):
		if weight == idx_LF: return idx_RF
		if weight == idx_LT: return idx_RT
		if weight == idx_RL: return idx_RF
		return weight
	for vert in pmx.verts:
		process_weight(vert, lambda x: soloFixMap.get(x, x))
		##--- Cleanup some messy feet vertices that happen now and then
		# Ignore if too high
		if vert.pos[1] > threshold: continue
		if vert.pos[0] > 0: process_weight(vert, replLeft)
		else:               process_weight(vert, replReight)
	
	#################
	##### Clean up some other Body Nodes
	print("------------")
	
	## Reduce Body Nodes (Remove all between Center & Hips, but keep Groove if it exists)
	idxCenter = fbx("グルーブ")
	if idxCenter == -1: idxCenter = fb("センター")
	idxHips = fbx("cf_j_hips")
	if (idxHips != -1): pmx.bones[idxHips].parent_idx = idxCenter
	
	### Reduce Twists
	if fbx("cf_d_arm01_L") != -1:
		replace_with_parent = lambda x: util.replace_with_parent(pmx, x)
		def rename_bone(txt_EN, txt_JP):
			def __rename_bone(pre_JP, sfx_EN):
				idx = fbx(txt_EN + sfx_EN)
				if idx != -1:
					pmx.bones[idx].name_jp = pre_JP + txt_JP
					pmx.bones[idx].name_en = txt_EN + sfx_EN
			__rename_bone("左", "L"); __rename_bone("右", "R")
		## Arm Twist
		replace_with_parent("cf_s_arm01_L")    ;replace_with_parent("cf_s_arm01_R")
		replace_with_parent("cf_s_arm02_L")    ;replace_with_parent("cf_s_arm02_R")
		replace_with_parent("cf_s_arm03_L")    ;replace_with_parent("cf_s_arm03_R")
		## Wrist Twist                         ;
		#replace_with_parent("cf_s_arm01_L")   ;#replace_with_parent("cf_s_arm01_R")
		replace_with_parent("cf_s_forearm02_L");replace_with_parent("cf_s_forearm02_R")
		replace_with_parent("cf_s_wrist_L")    ;replace_with_parent("cf_s_wrist_R")
		
		rename_bone("cf_s_arm01_", "腕捩1"); rename_bone("cf_s_forearm01_", "手捩1")
		rename_bone("cf_s_arm02_", "腕捩2"); rename_bone("cf_s_forearm02_", "手捩2")
		rename_bone("cf_s_arm03_", "腕捩3"); rename_bone("cf_s_wrist_",     "手捩3")
		
		## Leg Twist
		#replace_with_parent("cf_s_leg01_L")   ;replace_with_parent("cf_s_leg01_R")
		replace_with_parent("cf_s_leg02_L")    ;replace_with_parent("cf_s_leg02_R")
		replace_with_parent("cf_s_leg03_L")    ;replace_with_parent("cf_s_leg03_R")
		## Thigh Twist                         ;
		replace_with_parent("cf_s_thigh01_L")  ;replace_with_parent("cf_s_thigh01_R")
		replace_with_parent("cf_s_thigh02_L")  ;replace_with_parent("cf_s_thigh02_R")
		replace_with_parent("cf_s_thigh03_L")  ;replace_with_parent("cf_s_thigh03_R")
	
	for bone in pmx.bones:
		if bone.name_jp.startswith("cf_hit"):
			bone.has_visible = False
	
	if flag_SFW:
		idx = fbx("cf_d_bust00")
		if idx != -1: pmx.bones[idx].name_en = "Chest Root"
	
	### Remove weird Pivot Bones because idk what you need them for
	if not flag_SFW:
		rgxV = re.compile("Pivot|_root")
		for idx in fullMap.get("cf_J_Vagina_root", []):
			bone = pmx.bones[idx]
			if rgxV.search(bone.name_jp): continue
			grandparent = pmx.bones[bone.parent_idx].parent_idx
			bone.parent_idx = grandparent
	
	#--##--#
	import model_overall_cleanup
	model_overall_cleanup.__main(pmx, input_file_name, False, False)
	_opt["fullClean"] = _opt.get("fullClean", flag_all)
	cleanup_free_things(pmx, _opt)
	if _opt.get("soloMode", True):
		return end(pmx if True else None, input_file_name, "_reduced", ["Simplified Face Vertices"])
	########################
	pass ## Scroll Mark
simplify_armature.__doc__ = """
Attempts to simplify the bone structure
 - Simplify Accessories by removing empty bones
 - Reduce Body parts by merging bones serving no purpose outside the game

[All in One-Mode]:
 - Selecting "Ignore all options" does everything except removing NSFW bones
 - Selecting "Use default options" will only ask if NSFW should be kept

User Choices:
 - "SFW-Mode": Merges Chest into one Bone, as well as Groin and Butt Bones into Waist
 - "Everything": Skip the below options with "Yes"
 - "Simplify waist": Simplify Butt
 - "Merge Toe bones": If individual toe bones exist, merge into default toe bone.
 - "Simplify non-head Slots": Simplify non-head Accessories (Head is always done)

[Output]:
 - PMX file '[modelname]_better2.pmx' when called through "All-in-one"
 - PMX file '[modelname]_reduced.pmx' when called on its own
  - If unhappy with the result, call this again using [modelname]_better.pmx
"""

