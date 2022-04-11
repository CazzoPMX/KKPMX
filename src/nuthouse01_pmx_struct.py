# Nuthouse01 - 10/10/2020 - v5.03
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################


# first, system imports
from typing import List, Union
from abc import ABC, abstractmethod

# second, wrap custom imports with a try-except to catch it if files are missing
try:
	# these imports work if running from GUI
	from . import nuthouse01_core as core
except ImportError as eee:
	try:
		# these imports work if running from double-click on THIS script
		import nuthouse01_core as core
	except ImportError as eee:
		print(eee.__class__.__name__, eee)
		print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
		print("...press ENTER to exit...")
		input()
		exit()
		core = None


############################################################################################
######## IMPORTANT NOTES ###################################################################
# pos = position = xyz
# there are NO quaternions in any of these structs, all angles are XYZ degrees
# all RGB or RGBA color stuff is floats [0.0-1.0] (below 0.0 or above 1.0 are both allowed tho, i just mean 0-255 == 0.0-1.0)
# the "list" members are just for viewing/debugging
# i STRONGLY suggest you use all keyword arguments when creating any of these objects, even if it makes things messy &
#    ugly it also makes them unambiguous and clear at a glance
# i also suggest you omit any "optional" or conditionally needed args that aren't relevant and let them default to
#    None instead of explicitly setting them to None
############################################################################################
############################################################################################


# this is an abstract base class that all the PMX classes inherit
# this lets them all get the __str__ method and forces them all to implement list()
# it also lets me detect any of them by isinstance(x, _BasePmx)
# this also defines an "==" method so my structs can be compared
# this also defines "idx_within" so if you forget the idx of a thing but still have its reference you can find its index again
class _BasePmx(ABC):
	@abstractmethod
	def list(self) -> list: pass
	def __str__(self) -> str: return str(self.list())
	def __eq__(self, other) -> bool:
		if type(self) != type(other): return False
		return self.list() == other.list()
	def idx_within(self, L: List) -> Union[int, None]:
		for d, thing in enumerate(L):
			if self is thing: return d
		return None


class PmxHeader(_BasePmx):
	# [ver, name_jp, name_en, comment_jp, comment_en]
	def __init__(self, 
				 ver: float, 
				 name_jp: str,
				 name_en: str,
				 comment_jp: str,
				 comment_en: str):
		self.ver = ver
		self.name_jp = name_jp
		self.name_en = name_en
		self.comment_jp = comment_jp
		self.comment_en = comment_en
	def list(self):
		return [self.ver, self.name_jp, self.name_en, self.comment_jp, self.comment_en]


class PmxVertex(_BasePmx):
	# note: this block is the order of args in the old system, does not represent order of args in .list() member
	# [posX, posY, posZ, normX, normY, normZ, u, v, addl_vec4s, weighttype, weights, edgescale]
	def __init__(self,
				 pos: List[float],
				 norm: List[float],
				 uv: List[float],
				 edgescale: float,
				 weighttype: int,
				 weight: List[float],
				 # optional/conditional
				 weight_sdef: List[List[float]]=None,
				 addl_vec4s: List[List[float]]=None,
				 ):
		assert len(pos) == 3
		assert len(norm) == 3
		assert len(uv) == 2
		if weighttype == 3 and weight_sdef is not None:
			# weight_sdef doesn't need to exist now, but because weighttype == 3 it DOES need to exist and be valid before write-time
			assert len(weight_sdef) == 3  # 3 sublists,
			for rc in weight_sdef:
				assert len(rc) == 3  # each sublist is 3 floats
		if addl_vec4s is None: addl_vec4s = []
		for av in addl_vec4s:
			assert len(av) == 4
		self.pos = pos
		self.norm = norm
		self.uv = uv
		self.edgescale = edgescale
		# weighttype:
		# 0 = BDEF1 = [b1]
		# 1 = BDEF2 = [b1, b2, b1w]
		# 2 = BDEF4 = [b1, b2, b3, b4, b1w, b2w, b3w, b4w]
		# 3 = sdef =  [b1, b2, b1w] + weight_sdef = [[c1, c2, c3], [r01, r02, r03], [r11, r12, r13]]
		# 4 = qdef =  [b1, b2, b3, b4, b1w, b2w, b3w, b4w]  (only in pmx v2.1)
		self.weighttype = weighttype
		self.weight = weight
		self.weight_sdef = weight_sdef
		self.addl_vec4s = addl_vec4s
	def list(self) -> list:
		return [self.pos, self.norm, self.uv, self.edgescale,
				self.weighttype, self.weight, self.weight_sdef, self.addl_vec4s]

# face is just a list of ints, no struct needed

# tex is just a string, no struct needed

class PmxMaterial(_BasePmx):
	def __init__(self,
				 name_jp: str, name_en: str,
				 diffRGB: List[float],
				 specRGB: List[float],
				 ambRGB: List[float],
				 alpha: float, specpower: float,
				 edgeRGB: List[float], edgealpha: float, edgesize: float,
				 tex_idx: int,
				 sph_idx: int, sph_mode: int,
				 toon_idx: int, toon_mode: int,
				 comment: str,
				 faces_ct: int,
				 flaglist: List[bool],
				 ):
		assert len(diffRGB) == 3
		assert len(specRGB) == 3
		assert len(ambRGB) == 3
		assert len(edgeRGB) == 3
		assert len(flaglist) == 8
		self.name_jp = name_jp
		self.name_en = name_en
		self.diffRGB = diffRGB
		self.specRGB = specRGB
		self.ambRGB = ambRGB
		self.alpha = alpha
		self.specpower = specpower
		self.edgeRGB = edgeRGB
		self.edgealpha = edgealpha
		self.edgesize = edgesize
		self.tex_idx = tex_idx
		self.sph_idx = sph_idx
		# TODO: sph mode explain
		self.sph_mode = sph_mode
		self.toon_idx = toon_idx
		# toon_mode: 0 = tex reference, 1 = one of the builtin toons, toon01.bmp thru toon10.bmp (values 0-9)
		self.toon_mode = toon_mode
		self.comment = comment
		self.faces_ct = faces_ct
		# this order is accurate
		# flaglist = [no_backface_culling, cast_ground_shadow, cast_shadow, receive_shadow, use_edge, vertex_color,
		# 			draw_as_points, draw_as_lines]
		self.flaglist = flaglist
	def list(self) -> list:
		return [self.name_jp, self.name_en, self.diffRGB, self.specRGB, self.ambRGB, self.alpha, self.specpower,
				self.edgeRGB, self.edgealpha, self.edgesize,
				self.tex_idx, self.sph_idx, self.sph_mode, self.toon_idx, self.toon_mode,
				self.comment, self.faces_ct, self.flaglist,
				]

class PmxBoneIkLink(_BasePmx):
	# NOTE: to represent "no limits", the min and max should be None or omitted
	def __init__(self,
				 idx: int,
				 # optional/conditional
				 limit_min: List[float]=None,
				 limit_max: List[float]=None,
				 ):
		if limit_min is not None or limit_max is not None: # either both should be present, or neither
			assert len(limit_min) == 3
			assert len(limit_max) == 3
		self.idx = idx
		self.limit_min = limit_min
		self.limit_max = limit_max
	def list(self) -> list:
		return [self.idx, self.limit_min, self.limit_max]

class PmxBone(_BasePmx):
	# note: this block is the order of args in the old system, does not represent order of args in .list() member
	# thisbone = [name_jp, name_en, posX, posY, posZ, parent_idx, deform_layer, deform_after_phys,  # 0-7
	# 			rotateable, translateable, visible, enabled,  # 8-11
	# 			tail_usebonelink, maybe_tail, inherit_rot, inherit_trans, maybe_inherit, fixed_axis, maybe_fixed_axis,  # 12-18
	# 			local_axis, maybe_local_axis, external_parent, maybe_external_parent, ik, maybe_ik]  # 19-24
	def __init__(self,
				 name_jp: str, name_en: str,
				 pos: List[float],
				 parent_idx: int,
				 deform_layer: int,
				 deform_after_phys: bool,
				 has_rotate: bool,
				 has_translate: bool,
				 has_visible: bool,
				 has_enabled: bool,
				 has_ik: bool,
				 tail_usebonelink: bool,
				 tail: Union[int, List[float]],  # NOTE: either int or list of 3 float, but always exists, never None
				 inherit_rot: bool,
				 inherit_trans: bool,
				 has_fixedaxis: bool,
				 has_localaxis: bool,
				 has_externalparent: bool,
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
				 ik_links: List[PmxBoneIkLink]=None,
				 ):
		assert len(pos) == 3
		if tail_usebonelink:
			assert isinstance(tail, int)
		else:
			assert len(tail) == 3
		if has_fixedaxis and fixedaxis is not None:
			# fixedaxis doesn't need to exist now, but because has_fixedaxis == True it DOES need to exist and be valid before write-time
			assert len(fixedaxis) == 3
		if has_localaxis:
			if localaxis_x is not None:
				# localaxis_x doesn't need to exist now, but because has_localaxis == True it DOES need to exist and be valid before write-time
				assert len(localaxis_x) == 3
			if localaxis_z is not None:
				# localaxis_z doesn't need to exist now, but because has_localaxis == True it DOES need to exist and be valid before write-time
				assert len(localaxis_z) == 3
		self.name_jp = name_jp
		self.name_en = name_en
		self.pos = pos
		self.parent_idx = parent_idx
		self.deform_layer = deform_layer
		self.deform_after_phys = deform_after_phys
		self.has_rotate = has_rotate
		self.has_translate = has_translate
		self.has_visible = has_visible
		self.has_enabled = has_enabled
		self.has_ik = has_ik
		# tail_usebonelink: true = point-at mode, false = offset mode
		self.tail_usebonelink = tail_usebonelink
		self.tail = tail
		self.inherit_rot = inherit_rot
		self.inherit_trans = inherit_trans
		self.has_fixedaxis = has_fixedaxis
		self.has_localaxis = has_localaxis
		self.has_externalparent = has_externalparent
		
		self.inherit_parent_idx = inherit_parent_idx
		self.inherit_ratio = inherit_ratio
		self.fixedaxis = fixedaxis
		self.localaxis_x = localaxis_x
		self.localaxis_z = localaxis_z
		self.externalparent = externalparent
		self.ik_target_idx = ik_target_idx
		self.ik_numloops = ik_numloops
		self.ik_angle = ik_angle
		self.ik_links = ik_links
	def list(self) -> list:
		return [self.name_jp, self.name_en, self.pos, self.parent_idx, self.deform_layer, self.deform_after_phys,
				self.has_rotate, self.has_translate, self.has_visible, self.has_enabled,
				self.tail_usebonelink, self.tail,
				self.inherit_rot, self.inherit_trans, self.inherit_parent_idx, self.inherit_ratio,
				self.has_fixedaxis, self.fixedaxis,
				self.has_localaxis, self.localaxis_x, self.localaxis_z,
				self.has_externalparent, self.externalparent,
				self.has_ik, self.ik_target_idx, self.ik_numloops, self.ik_angle,
				None if self.ik_links is None else [i.list() for i in self.ik_links],
				]


class PmxMorphItemGroup(_BasePmx):
	def __init__(self, morph_idx: int, value: float):
		self.morph_idx = morph_idx
		self.value = value
	def list(self) -> list:
		return [self.morph_idx, self.value]
	
class PmxMorphItemVertex(_BasePmx):
	def __init__(self, vert_idx: int, move: List[float]):
		assert len(move) == 3
		self.vert_idx = vert_idx
		self.move = move
	def list(self) -> list:
		return [self.vert_idx, self.move]
	
class PmxMorphItemBone(_BasePmx):
	def __init__(self, bone_idx: int, move: List[float], rot: List[float]):
		assert len(move) == 3
		assert len(rot) == 3
		self.bone_idx = bone_idx
		self.move = move
		self.rot = rot
	def list(self) -> list:
		return [self.bone_idx, self.move, self.rot]


class PmxMorphItemUV(_BasePmx):
	def __init__(self, vert_idx: int, move: List[float]):
		assert len(move) == 4
		self.vert_idx = vert_idx
		self.move = move
	def list(self) -> list:
		return [self.vert_idx, self.move]


class PmxMorphItemMaterial(_BasePmx):
	def __init__(self, mat_idx: int, is_add: int,
				 diffRGB: List[float],
				 specRGB: List[float],
				 ambRGB: List[float],
				 alpha: float,
				 specpower: float,
				 edgeRGB: List[float],
				 edgealpha: float,
				 edgesize: float,
				 texRGBA: List[float],
				 sphRGBA: List[float],
				 toonRGBA: List[float],
				 ):
		assert len(diffRGB) == 3
		assert len(specRGB) == 3
		assert len(ambRGB) == 3
		assert len(edgeRGB) == 3
		assert len(texRGBA) == 4
		assert len(sphRGBA) == 4
		assert len(toonRGBA) == 4
		self.mat_idx = mat_idx
		self.is_add = is_add
		self.diffRGB = diffRGB
		self.specRGB = specRGB
		self.ambRGB = ambRGB
		self.alpha = alpha
		self.specpower = specpower
		self.edgeRGB = edgeRGB
		self.edgealpha = edgealpha
		self.edgesize = edgesize
		self.texRGBA = texRGBA
		self.sphRGBA = sphRGBA
		self.toonRGBA = toonRGBA
		# note: this order of args matches the current .list() order, except that it's grouped into sublists
		# (mat_idx, is_add, diffR, diffG, diffB, diffA, specR, specG, specB) = core.unpack(IDX_MAT+"b 4f 3f", raw)
		# (specpower, ambR, ambG, ambB, edgeR, edgeG, edgeB, edgeA, edgesize) = core.unpack("f 3f 4f f", raw)
		# (texR, texG, texB, texA, sphR, sphG, sphB, sphA, toonR, toonG, toonB, toonA) = core.unpack("4f 4f 4f", raw)
	def list(self) -> list:
		return [self.mat_idx, self.is_add,
				self.diffRGB, self.specRGB, self.ambRGB, self.alpha, self.specpower,
				self.edgeRGB, self.edgealpha, self.edgesize,
				self.texRGBA, self.sphRGBA, self.toonRGBA,
				]


class PmxMorphItemFlip(_BasePmx):
	def __init__(self, morph_idx: int, value: float):
		self.morph_idx = morph_idx
		self.value = value
	def list(self) -> list:
		return [self.morph_idx, self.value]


class PmxMorphItemImpulse(_BasePmx):
	def __init__(self, rb_idx: int, is_local: bool, move: List[float], rot: List[float]):
		assert len(move) == 3
		assert len(rot) == 3
		self.rb_idx = rb_idx
		self.is_local = is_local
		self.move = move
		self.rot = rot
	def list(self) -> list:
		return [self.rb_idx, self.is_local, self.move, self.rot]


class PmxMorph(_BasePmx):
	# thismorph = [name_jp, name_en, panel, morphtype, these_items]
	def __init__(self,
				 name_jp: str, name_en: str,
				 panel: int,
				 morphtype: int,
				 items: Union[List[PmxMorphItemGroup],
							  List[PmxMorphItemVertex],
							  List[PmxMorphItemBone],
							  List[PmxMorphItemUV],
							  List[PmxMorphItemMaterial],
							  List[PmxMorphItemFlip],
							  List[PmxMorphItemImpulse], ],
				 ):
		self.name_jp = name_jp
		self.name_en = name_en
		self.panel = panel
		# morphtype
		# 0 = group = (morph_idx, influence)
		# 1 = vertex = (vert_idx, transX, transY, transZ)
		# 2 = bone = (bone_idx, transX, transY, transZ, rotX, rotY, rotZ, rotW)
		# 3/4/5/6/7 = uv = (vert_idx, A, B, C, D)
		# 8 = material =
		# (mat_idx, is_add, diffR, diffG, diffB, diffA, specR, specG, specB) = core.unpack(IDX_MAT+"b 4f 3f", raw)
		# (specpower, ambR, ambG, ambB, edgeR, edgeG, edgeB, edgeA, edgesize) = core.unpack("f 3f 4f f", raw)
		# (texR, texG, texB, texA, sphR, sphG, sphB, sphA, toonR, toonG, toonB, toonA) = core.unpack("4f 4f 4f", raw)
		# 9 = flip = (morph_idx, influence)  (pmx v2.1 only)
		# 10 = impulse = (rb_idx, is_local, movX, movY, movZ, rotX, rotY, rotZ)   (pmx v2.1 only)
		self.morphtype = morphtype
		self.items = items
	def list(self) -> list:
		return [self.name_jp, self.name_en, self.panel, self.morphtype,
				[i.list() for i in self.items],
				]


class PmxFrame(_BasePmx):
	# thisframe = [name_jp, name_en, is_special, these_items]
	def __init__(self, 
				 name_jp: str, name_en: str, 
				 is_special: bool, 
				 items: List[List[int]],
				 ):
		self.name_jp = name_jp
		self.name_en = name_en
		# "special" frames are root and facials. name/position cannot be edited in PMXE, but they're otherwise ordinary frames.
		self.is_special = is_special
		# each "item" in the list of items is [is_morph, idx]
		# TODO: make simply "FrameItem" object just so it's objects all the way down
		self.items = items
	def list(self) -> list:
		return [self.name_jp, self.name_en, self.is_special, self.items]
		
class PmxRigidBody(_BasePmx):
	# note: this block is the order of args in the old system, does not represent order of args in .list() member
	# thisbody = [name_jp, name_en, bone_idx, group, nocollide_mask, shape, sizeX, sizeY, sizeZ, posX, posY, posZ,
	# 			rotX, rotY, rotZ, mass, move_damp, rot_damp, repel, friction, physmode]
	def __init__(self, 
				 name_jp: str, name_en: str, 
				 bone_idx: int, 
				 pos: List[float],
				 rot: List[float],
				 size: List[float],
				 shape: int,
				 group: int, 
				 nocollide_mask: int, 
				 phys_mode: int,
				 phys_mass: float=1.0,
				 phys_move_damp: float=0.0,
				 phys_rot_damp: float=0.0,
				 phys_repel: float=0.0,
				 phys_friction: float=0.0,
				 ):
		assert len(pos) == 3
		assert len(rot) == 3
		assert len(size) == 3
		self.name_jp = name_jp
		self.name_en = name_en
		self.bone_idx = bone_idx
		self.pos = pos
		self.rot = rot
		self.size = size
		# shape: 0=sphere, 1=box, 2=capsule
		self.shape = shape
		self.group = group
		self.nocollide_mask = nocollide_mask
		# phys_mode: 0=follow bone, 1=physics, 2=physics rotate only (pivot on bone)
		self.phys_mode = phys_mode
		self.phys_mass = phys_mass
		self.phys_move_damp = phys_move_damp
		self.phys_rot_damp = phys_rot_damp
		self.phys_repel = phys_repel
		self.phys_friction = phys_friction
		
	def list(self) -> list:
		return [self.name_jp, self.name_en, self.bone_idx, 
				self.pos, self.rot, self.size, self.shape,
				self.group, self.nocollide_mask, self.phys_mode,
				self.phys_mass, self.phys_move_damp, self.phys_rot_damp, self.phys_repel, self.phys_friction,
				]


class PmxJoint(_BasePmx):
	# note: this block is the order of args in the old system, does not represent order of args in .list() member
	# thisjoint = [name_jp, name_en, jointtype, rb1_idx, rb2_idx, posX, posY, posZ,
	# 			 rotX, rotY, rotZ, posminX, posminY, posminZ, posmaxX, posmaxY, posmaxZ,
	# 			 rotminX, rotminY, rotminZ, rotmaxX, rotmaxY, rotmaxZ,
	# 			 springposX, springposY, springposZ, springrotX, springrotY, springrotZ]
	def __init__(self,
				 name_jp: str, name_en: str,
				 jointtype: int, rb1_idx: int, rb2_idx: int,
				 pos: List[float],
				 rot: List[float],
				 movemin: List[float],
				 movemax: List[float],
				 movespring: List[float],
				 rotmin: List[float],
				 rotmax: List[float],
				 rotspring: List[float],
				 ):
		assert len(pos) == 3
		assert len(rot) == 3
		assert len(movemin) == 3
		assert len(movemax) == 3
		assert len(movespring) == 3
		assert len(rotmin) == 3
		assert len(rotmax) == 3
		assert len(rotspring) == 3
		self.name_jp = name_jp
		self.name_en = name_en
		# jointtype: 0=spring6DOF, all others are v2.1 only!!!! 1=6dof, 2=p2p, 3=conetwist, 4=slider, 5=hinge
		self.jointtype = jointtype
		self.rb1_idx = rb1_idx
		self.rb2_idx = rb2_idx
		self.pos = pos
		self.rot = rot
		self.movemin = movemin
		self.movemax = movemax
		self.movespring = movespring
		self.rotmin = rotmin
		self.rotmax = rotmax
		self.rotspring = rotspring
		
	def list(self) -> list:
		return [self.name_jp, self.name_en, self.jointtype, self.rb1_idx, self.rb2_idx,
				self.pos, self.rot,
				self.movemin, self.movemax, self.movespring,
				self.rotmin, self.rotmax, self.rotspring,
				]

class PmxSoftBody(_BasePmx):
	# i don't plan to support v2.1 so I'm not gonna try to hard to understand the meaning of these data fields
	# this is mostly to consume the data so there are no bytes left over when done parsing a file to trigger warnings
	# note: this is also untested because i dont care about it lol
	# note: this block is the order of args in the old system, does not represent order of args in .list() member
	# thissoft = [name_jp, name_en, shape, idx_mat, group, nocollide_mask, flags,
	# 			b_link_create_dist, num_clusters, total_mass, collision_marign, aerodynamics_model,
	# 			vcf, dp, dg, lf, pr, vc, df, mt, rch, kch, sch, ah,
	# 			srhr_cl, skhr_cl, sshr_cl, sr_splt_cl, sk_splt_cl, ss_splt_cl,
	# 			v_it, p_it, d_it, c_it, mat_lst, mat_ast, mat_vst, anchors_list, vertex_pin_list]
	def __init__(self, name_jp, name_en, shape, idx_mat, group, nocollide_mask, flags,
				 b_link_create_dist, num_clusters, total_mass, collision_margin, aerodynamics_model,
				 vcf, dp, dg, lf, pr, vc, df, mt, rch, kch, sch, ah,
				 srhr_cl, skhr_cl, sshr_cl, sr_splt_cl, sk_splt_cl, ss_splt_cl,
				 v_it, p_it, d_it, c_it, mat_lst, mat_ast, mat_vst,
				 anchors_list: List[List[int]], vertex_pin_list: List[int]):
		self.name_jp = name_jp
		self.name_en = name_en
		self.shape = shape
		self.idx_mat = idx_mat
		self.group = group
		self.nocollide_mask = nocollide_mask
		self.flags = flags
		self.b_link_create_dist = b_link_create_dist
		self.num_clusters = num_clusters
		self.total_mass = total_mass
		self.collision_margin = collision_margin
		self.aerodynamics_model = aerodynamics_model
		self.vcf = vcf
		self.dp = dp
		self.dg = dg
		self.lf = lf
		self.pr = pr
		self.vc = vc
		self.df = df
		self.mt = mt
		self.rch = rch
		self.kch = kch
		self.sch = sch
		self.ah = ah
		self.srhr_cl = srhr_cl
		self.skhr_cl = skhr_cl
		self.sshr_cl = sshr_cl
		self.sr_splt_cl = sr_splt_cl
		self.sk_splt_cl = sk_splt_cl
		self.ss_splt_cl = ss_splt_cl
		self.v_it = v_it
		self.p_it = p_it
		self.d_it = d_it
		self.c_it = c_it
		self.mat_lst = mat_lst
		self.mat_ast = mat_ast
		self.mat_vst = mat_vst
		self.anchors_list = anchors_list
		self.vertex_pin_list = vertex_pin_list
	def list(self) -> list:
		return [self.name_jp, self.name_en, self.shape, self.idx_mat, self.group, self.nocollide_mask, self.flags,
				self.b_link_create_dist, self.num_clusters, self.total_mass, self.collision_margin,
				self.aerodynamics_model, self.vcf, self.dp, self.dg, self.lf, self.pr, self.vc, self.df, self.mt,
				self.rch, self.kch, self.sch, self.ah,
				self.srhr_cl, self.skhr_cl, self.sshr_cl, self.sr_splt_cl, self.sk_splt_cl, self.ss_splt_cl,
				self.v_it, self.p_it, self.d_it, self.c_it,
				self.mat_lst, self.mat_ast, self.mat_vst,
				self.anchors_list, self.vertex_pin_list]


class Pmx(_BasePmx):
	# [A, B, C, D, E, F, G, H, I, J, K]
	def __init__(self,
				 header: PmxHeader,
				 verts: List[PmxVertex],
				 faces: List[List[int]],
				 texes: List[str],
				 mats: List[PmxMaterial],
				 bones: List[PmxBone],
				 morphs: List[PmxMorph],
				 frames: List[PmxFrame],
				 rbodies: List[PmxRigidBody],
				 joints: List[PmxJoint],
				 sbodies: List[PmxSoftBody]=None
				 ):
		if sbodies is None:
			assert header.ver == 2.0
			sbodies = []
		self.header = header
		self.verts = verts
		self.faces = faces
		self.textures = texes
		self.materials = mats
		self.bones = bones
		self.morphs = morphs
		self.frames = frames
		self.rigidbodies = rbodies
		self.joints = joints
		self.softbodies = sbodies
	def list(self) -> list:
		return [self.header.list(),						#0
				[i.list() for i in self.verts],			#1
				self.faces,								#2
				self.textures,							#3
				[i.list() for i in self.materials],		#4
				[i.list() for i in self.bones],			#5
				[i.list() for i in self.morphs],		#6
				[i.list() for i in self.frames],		#7
				[i.list() for i in self.rigidbodies],	#8
				[i.list() for i in self.joints],		#9
				[i.list() for i in self.softbodies],	#10
				]


		
if __name__ == '__main__':
	core.MY_PRINT_FUNC("Nuthouse01 - 10/10/2020 - v5.03")
	core.pause_and_quit("you are not supposed to directly run this file haha")


