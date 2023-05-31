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
from kkpmx_core import __append_bonemorph

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

