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
import nuthouse01_pmx_struct as struct
import morph_scale
import kkpmx_utils as util
from kkpmx_utils import find_bone, find_mat, find_disp, find_morph, find_rigid

def run(pmx, input_filename_pmx, moreinfo=False, write_model=True):
	"""
Rigging Helpers for KK.
- Adjust Body Physics (so far only adjusts the Rear RigidBody)
- Transform Skirt Grid from Cubicle to Rectangles
- Rig Hair Joints
-  - Since KKExport loves to merge vertex meshes if they are bound to bones sharing the same name, this also corrects the bone weights
-  - The "normal" rigging can also be reproduced by selecting a linked bone range, and opening [Edit]>[Bone]>[Create Rigid/Linked Joint]
-  - Sometimes needs minor optimizations, but also allows a bit of customization (by changing the Rigid Type of the chain segments)
"""
	import kkpmx_core as kkcore
	adjust_body_physics(pmx)
	transform_skirt(pmx)
	rig_hair_joints(pmx)
	return kkcore.end(pmx if write_model else None, input_filename_pmx, "_rigged", "Modified Rigging")

###############
### Riggers ###
###############

def rig__fox_tail(pmx,_): ## If there are multiple, they are all merged together and anchored to the same bones
	## Connect Bone Tails
	## Add Hidden End Bone with 0,-1,0
	## Foreach Bone 'joint'+0-3
	### Create new RigidBody
	### Add Joint
	pass

def pre_rig_all_joint_bones(pmx, _):
	## Go through every slot and fetch the full tree
	## If not(the tree contains joint0, joint1, ...) continue
	## add '下半身' to bodyArr
	## add joint0 to jointArr
	## for each pair(jointX,jointX+1)
	## ## add bone_tail from A to B
	## ## add RigidBody(A) from A to B ++ to bodyArr
	## ## add B to jointArr
	## Add Hidden End Bone with 0,-1,0 ## but not to jointArr
	## Add add RigidBody(jointArr[-1]) from x to End ++ to bodyArr
	## for each idx,X in jointArr
	## ## create PmxJoint
	## ## -- between bodyArr[idx] and bodyArr[idx+1]
	## ## -- at Position jointArr[idx]
	##-- Need to tell that vertices still need to be weighted to them (?)
	pass

def adjust_body_physics(pmx):
	## Butt collision
	if find_bone(pmx, "cf_j_waist02", False):
		posX = pmx.bones[find_bone(pmx, "cf_j_waist02")].pos[0]
		posY = pmx.bones[find_bone(pmx, "cf_d_thigh01_L")].pos[1]
		posZ = pmx.bones[find_bone(pmx, "cf_s_siri_L")].pos[2]
		rigid = find_rigid(pmx, "下半身")
		pmx.rigidbodies[rigid].pos = [posX, posY, posZ]
		pmx.rigidbodies[rigid].size[0] = 0.8
		pmx.rigidbodies[rigid].nocollide_mask = 65534 # == [1] is 2^16-1
		pmx.rigidbodies[rigid].phys_move_damp = 0.99
		pmx.rigidbodies[rigid].phys_rot_damp = 0.99
		pmx.rigidbodies[rigid].phys_repel = 0
		pmx.rigidbodies[rigid].phys_friction = 0.5

def transform_skirt(pmx):
	sizer = [0,0,0]
	for rigid in pmx.rigidbodies:
		## Change width of all but [05] to XX (start at 0.6)
		if not re.match(r"cf_j_sk", rigid.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_05", rigid.name_jp): continue
		## Change mode to 1 & set depth to 0.02
		rigid.shape = 1
		rigid.size[0] = 0.6
		rigid.size[2] = 0.02
	## Move Side Joints to sides (X + width / 2, Y + height / 2)
	for joint in pmx.joints:
		if not re.match(r"cf_j_sk", joint.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_05", joint.name_jp): continue
		if re.match(r"cf_j_sk_\d\d_\d\d\[side\]", joint.name_jp):
			rigid = pmx.rigidbodies[joint.rb1_idx]
			## X pos requires using triangulation, maybe later
			joint.pos[1] = rigid.pos[1] + rigid.size[1] / 2
			joint.pos[2] = rigid.pos[2] + rigid.size[2] / 2
	
		## Add more Pos-Move into the lower joints (?)
		## -- [Front]: 7,0,1
		## -- [Right]:   2
		## -- [Back]:  3,4,5
		## -- [Left]:    6
		##-- Allow [side] Joints extended movement between these groups
		##-- Allow [main] Joints more +Y Rotation
##########
	pass# To keep trailing comments inside

def rig_hair_joints(pmx):
	### Add a Head Rigid for the Hair to anchor onto -- return if none
	head = find_bone(pmx, "a_n_headflont")
	if head is None: return
	head_bone = pmx.bones[head]
	head_body = add_rigid(pmx, name_jp="a_n_headfront", pos=head_bone.pos, bone_idx=head, size=[1,1,1], 
			phys_move_damp=1.0, phys_rot_damp=1.0)
			
	## Get reference point for discard
	try: limit = pmx.bones[find_bone(pmx, "胸親", False)].pos[1]
	except: limit = 0.0

	first_chain = None
	chain_matched = False
	bones = [i for (i,b) in enumerate(pmx.bones) if b.name_jp.startswith("joint1")]
	for bone in bones:
		## Ignore the groups not anchored to the head
		if pmx.bones[bone].pos[1] < limit: continue
		## Get name from containing slot
		b = bone
		while (b and not pmx.bones[b].name_jp.startswith("ca_slot")): b = pmx.bones[b].parent_idx
		name = pmx.bones[b].name_jp
		
		## Collect bone chain
		arr = []
		while pmx.bones[bone].name_jp.startswith("joint"):
			arr.append(bone)
			bone += 1
		##
		if first_chain is None: first_chain = copy.deepcopy(arr)
		bind_bones(pmx, arr, True)
		if not reweight_hair_bones(pmx, first_chain, arr, int(re.search(r"ca_slot(\d+)", name)[1])):
			if not chain_matched: first_chain = None
		else: chain_matched = True
		
		### Only do the last three segments
		arr = arr[-3:]
		grp = 16
		
		## Create a root
		root = add_rigid(pmx, name_jp=name+"_r", bone_idx=arr[0], shape=0, size=[0.2, 0, 0], pos = pmx.bones[arr[0]].pos,
			group=grp-1, nocollide_mask=2**grp-1, phys_move_damp=1, phys_rot_damp=1)
		
		## Create Physics chain
		num_bodies = len(pmx.rigidbodies)
		num_joints = len(pmx.joints)
		AddBaseBodyWithJoint(pmx, arr, 1, 0.0, True, name=name, group=grp)
		new_bodies = len(pmx.rigidbodies) - num_bodies
		new_joints = len(pmx.joints) - num_joints
		
		## Connect with head rigid
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
		#body.phys_mode = 0
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
		continue
		
		if new_joints > 1:
			# Make joints allow more rotation away from head
			for jointX in pmx.joints[num_joints:]:
				#jointX.rotmin[0] = -10.0 if jointX.pos[0] <= 0 else -1.0
				#jointX.rotmax[0] =   1.0 if jointX.pos[0] <= 0 else 10.0
				jointX.rotmin[1] =  -1.0
				jointX.rotmax[1] =   0.0
				#jointX.rotmin[2] =  -5.0 if jointX.pos[2] <= 0 else  1.0
				#jointX.rotmax[2] =   1.0 if jointX.pos[2] <= 0 else  5.0
		
		
		########### If using longer chains
		## Make first body static
		body = pmx.rigidbodies[num_bodies]
		body.phys_mode = 1
		body.phys_move_damp = 1
		body.phys_rot_damp  = 1
		
		if new_bodies < 2: continue
		## Make 2nd body static
		body = pmx.rigidbodies[num_bodies+1]
		#body.phys_mode = 0
		body.phys_move_damp = 1
		body.phys_rot_damp  = 1
		### Adjust the subsequent bodies (use len(arr))
		# Add a bit of sideway rotation to joint (based on pos.x is pos / neg)
		if new_joints > 1:
			# First two joints have no Y
			for jointX in pmx.joints[num_joints:][:2]:
				jointX.rotmin[1] = 0.0
				jointX.rotmax[1] = 0.0
			
			# Make joints allow more rotation away from head
			for jointX in pmx.joints[num_joints+1:]:
				jointX.rotmin[0] = -10.0 if jointX.pos[0] <= 0 else -5.0
				jointX.rotmax[0] =   5.0 if jointX.pos[0] <= 0 else 10.0
			
##########
	pass# To keep trailing comments inside

def reweight_hair_bones(pmx, src, dst, slot):
	import kkpmx_core as kkcore
	bone_map = { src[i]: dst[min(i, len(dst)-1)] for i in range(len(src)) }
	mat_idx = -1
	
	for (i,m) in enumerate(pmx.materials):
		if re.search("\[:AccId:\] (\d+)", m.comment):
			tmp = int(re.search("\[:AccId:\] (\d+)", m.comment)[1])
			if slot == tmp:
				mat_idx = i
				break
	if mat_idx == -1:
		print(f"Unable to find matching material for Slot {slot}")
		return
	faces = kkcore.from_material_get_faces(pmx, mat_idx, returnIdx=False)
	vertices = kkcore.from_faces_get_vertices(pmx, faces, returnIdx=True)
	bones = kkcore.from_vertices_get_bones(pmx, vertices, returnIdx=True)
	for idx in list(bone_map.keys())[:len(dst)]:
		if idx not in bones: return False
	
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

########
## Riggers Util
########

from kkpmx_utils import Vector3, Matrix
def AddBaseBodyWithJoint(pmx, boneIndex: List[int], mode: int, r: float, uvFlag: bool, name, group):
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

def AddBaseBody(pmx, boneIndices: List[int], mode: int, r: float, uvFlag: bool, name, group):
	if group in range(1,17):
		if group == 16: mask = 2**15 - 1
		elif group == 1: mask = 1
		else: mask = sum([2**(i-1) for i in range(16, group, -1)], 2**(group - 1) - 1)
		#print(mask)
		group = group - 1 ## Because actually [0 - 15]
	else:
		group = 1
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
			### Actually still in [if flag]
			body.shape = 2 #PmxBody.BoxKind.Capsule;
			x: float = r
			if (r <= 0.0): x = num3 * 0.2
			body.size = Vector3(x, num3, 0.0).ToList()
			body.pos = zero.ToList()
			m: Matrix = GetPoseMatrix_Bone(pmx, idx)
			body.rot = MatrixToEuler_ZXY(m).ToDegree().ToList()
		else:
			body = pmx.rigidbodies[add_rigid(pmx)]
			body.shape = 0 #PmxBody.BoxKind.Sphere
			x2: float = r
			if (r <= 0.0): x2 = 0.2#1.0
			body.size = [x2, 0.0, 0.0]
			body.pos = pos.ToList()
		#### -- end of [if]
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
		#if (m.M22 < 0.0): zero.Z = float(math.pi) - zero.Z
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
	if last_link: pmx.bones[arr[-1]].tail = [0, 0, -0.1]

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
	pmx.bones.append(struct.PmxBone(**args))
	return len(pmx.bones) - 1

def add_rigid(pmx,
			 name_jp: str = "New RigidBody1",
			 name_en: str = "",
			 bone_idx: int = 0,
			 pos: List[float] = [0,0,0],
			 rot: List[float] = [0,0,0],
			 size: List[float] = [2,2,2],
			 shape: int = 0,
			 group: int = 1,
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
	pmx.rigidbodies.append(struct.PmxRigidBody(**args))
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
	pmx.joints.append(struct.PmxJoint(**args))
	return len(pmx.joints) - 1
