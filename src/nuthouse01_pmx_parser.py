# Nuthouse01 - 1/24/2021 - v5.06
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################


# MASSIVE thanks to FelixJones on Github for already exporing & documenting the PMX file structure!
# https://gist.github.com/felixjones/f8a06bd48f9da9a4539f


# this file fully parses a PMX file and returns all of the data it contained, structured as a list of lists
# first, system imports
from typing import List
import math

# second, wrap custom imports with a try-except to catch it if files are missing
try:
	# these imports work if running from GUI
	from . import nuthouse01_core as core
	from . import nuthouse01_pmx_struct as pmxstruct
except ImportError as eee:
	try:
		# these imports work if running from double-click on THIS script
		import nuthouse01_core as core
		import nuthouse01_pmx_struct as pmxstruct
	except ImportError as eee:
		print(eee.__class__.__name__, eee)
		print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
		print("...press ENTER to exit...")
		input()
		exit()
		core = pmxstruct = None



# when debug=True, disable the catchall try-except block. this means the full stack trace gets printed when it crashes,
# but if launched in a new window it exits immediately so you can't read it.
DEBUG = False

# by default encode files with utf-16
# utf-8 might make files very slightly smaller but i haven't tested it
ENCODE_WITH_UTF8 = False

# parsing progress printouts: depend on the actual number of bytes processed, very accurate & linear
# encoding progress printouts: these vars estimate how long one item of each type will take to complete (relatively)
ENCODE_FACTOR_VERT = 1
ENCODE_FACTOR_FACE = .25
ENCODE_FACTOR_MORPH = .5
# dont touch these
ENCODE_PERCENT_VERT = 0
ENCODE_PERCENT_FACE = 0
ENCODE_PERCENT_VERTFACE = 0
ENCODE_PERCENT_MORPH = 0

# flag to indicate whether more info is desired or not
PMX_MOREINFO = False


# how many extra vec4s each vertex has with it
ADDL_VERTEX_VEC4 = 0
# type used to store an index for each thing, these are concatenated to dynamically make format strings
IDX_VERT = "x"
IDX_TEX = "x"
IDX_MAT = "x"
IDX_BONE = "x"
IDX_MORPH = "x"
IDX_RB = "x"

"""
more info about "indexes":
vertex: if <=255, use ubyte = B = type 1
        if <=65535 use ushort = H = type 2
        if <=2147483647 use int = i = type 4
        else crash
others: if <=127, use byte = b = type 1
        if <=32767 use short = h = type 2
        if <=2147483647 use int = i = type 4
        else crash
TODO: for non-vertex, value of -1 means N/A
for vertex, N/A is not possible
"""



# return conventions: to handle fields that may or may not exist, many things are lists that don't strictly need to be
# if the data doesn't exist, it is an empty list
# that way the indices of other return fields stay the same even when a sometimes-field is missing

########################################################################################################################

def parse_pmx_header(raw: bytearray) -> pmxstruct.PmxHeader:
	##################################################################
	# HEADER INFO PARSING
	# collects some returnable data, mostly just sets globals
	# returnable: ver, name_jp, name_en, comment_jp, comment_en
	
	expectedmagic = bytearray([0x50, 0x4D, 0x58, 0x20])
	fmt_magic = "4s f b"
	(magic, ver, numglobal) = core.my_unpack(fmt_magic, raw)
	if magic != expectedmagic:
		core.MY_PRINT_FUNC("Warning: this file does not begin with the correct magic bytes. Maybe it was locked? Locks wont stop me!")
		if PMX_MOREINFO: core.MY_PRINT_FUNC("Expected '%s' but found '%s'" % (expectedmagic.hex(), magic.hex()))
	
	# only first 8 bytes have known uses
	# more bytes have no known purpose but need to be accounted for anyway
	if numglobal != 8:
		core.MY_PRINT_FUNC("WARNING: this PMX has '%d' global variables, more than I know how to support!!!" % numglobal)
	fmt_globals = str(numglobal) + "b"
	globalflags = core.my_unpack(fmt_globals, raw)	# this actually returns a tuple of ints, which works just fine, dont touch it
	# print(globalflags)
	# byte 0: encoding
	if globalflags[0] == 0:
		core.set_encoding("utf_16_le")
	elif globalflags[0] == 1:
		core.set_encoding("utf_8")
	else:
		core.MY_PRINT_FUNC("unsupported encoding value", globalflags[0])
	# byte 1: additional vec4 per vertex
	global ADDL_VERTEX_VEC4
	ADDL_VERTEX_VEC4 = globalflags[1]
	# bytes 2-7: data size to use for index references
	global IDX_VERT, IDX_TEX, IDX_MAT, IDX_BONE, IDX_MORPH, IDX_RB
	vert_conv = {1:"B", 2:"H", 4:"i"}
	conv =      {1:"b", 2:"h", 4:"i"}
	IDX_VERT  = vert_conv[globalflags[2]]
	IDX_TEX   = conv[globalflags[3]]
	IDX_MAT   = conv[globalflags[4]]
	IDX_BONE  = conv[globalflags[5]]
	IDX_MORPH = conv[globalflags[6]]
	IDX_RB    = conv[globalflags[7]]
	# finally handle the model names & comments
	(name_jp, name_en, comment_jp, comment_en) = core.my_unpack("t t t t", raw)
	
	# assemble all the info into a struct for returning
	return pmxstruct.PmxHeader(ver=ver,
								name_jp=name_jp, name_en=name_en,
								comment_jp=comment_jp, comment_en=comment_en)
	# return retme

def parse_pmx_vertices(raw: bytearray) -> List[pmxstruct.PmxVertex]:
	# first item is int, how many vertices
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of verts            =", i)
	retme = []
	bdef1_fmt = IDX_BONE
	bdef2_fmt = "2%s f" % IDX_BONE
	bdef4_fmt = "4%s 4f" % IDX_BONE
	sdef_fmt =  "2%s 10f" % IDX_BONE
	qdef_fmt =  bdef4_fmt
	for d in range(i):
		# first, basic stuff
		(posX, posY, posZ, normX, normY, normZ, u, v) = core.my_unpack("8f", raw)
		# then, some number of vec4s (probably none)
		addl_vec4s = []
		for z in range(ADDL_VERTEX_VEC4):
			this_vec4 = core.my_unpack("4f", raw) # already returns as a list of 4 floats, no need to unpack then repack
			addl_vec4s.append(this_vec4)
		weighttype = core.my_unpack("b", raw)
		weights = []
		weight_sdef = []
		if weighttype == 0:
			# BDEF1
			b1 = core.my_unpack(bdef1_fmt, raw)
			weights = [b1]
		elif weighttype == 1:
			# BDEF2
			#(b1, b2, b1w) # already returns as a list of floats, no need to unpack then repack
			weights = core.my_unpack(bdef2_fmt, raw)
		elif weighttype == 2:
			# BDEF4
			#(b1, b2, b3, b4, b1w, b2w, b3w, b4w) # already returns as a list of floats, no need to unpack then repack
			weights = core.my_unpack(bdef4_fmt, raw)
		elif weighttype == 3:
			# SDEF
			#(b1, b2, b1w, c1, c2, c3, r01, r02, r03, r11, r12, r13)
			(b1, b2, b1w, c1, c2, c3, r01, r02, r03, r11, r12, r13) = core.my_unpack(sdef_fmt, raw)
			weights = [b1, b2, b1w]
			weight_sdef = [[c1, c2, c3], [r01, r02, r03], [r11, r12, r13]]
		elif weighttype == 4:
			# it must be using QDEF, a type only for PMX v2.1 which I dont need to support so idgaf
			# (b1, b2, b3, b4, b1w, b2w, b3w, b4w)
			weights = core.my_unpack(qdef_fmt, raw)
		else:
			core.MY_PRINT_FUNC("invalid weight type for vertex", weighttype)
		# then there is one final float after the weight crap
		edgescale = core.my_unpack("f", raw)

		# display progress printouts
		core.print_progress_oneline(core.get_readfrom_byte() / len(raw))
		# assemble all the info into a struct for returning
		thisvert = pmxstruct.PmxVertex(pos=[posX, posY, posZ], norm=[normX, normY, normZ], uv=[u, v],
									   weighttype=weighttype, weight=weights, weight_sdef=weight_sdef,
									   edgescale=edgescale, addl_vec4s=addl_vec4s)
		
		retme.append(thisvert)
	return retme

def parse_pmx_surfaces(raw: bytearray) -> List[List[int]]:
	# surfaces is just another name for faces
	# first item is int, how many vertex indices there are, NOT the actual number of faces
	# each face is 3 vertex indices, so "i" will always be a multiple of 3
	i = core.my_unpack("i", raw)
	retme = []
	i = int(i / 3)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of faces            =", i)
	for d in range(i):
		# each entry is a group of 3 vertex indeces that make a face
		thisface = core.my_unpack("3" + IDX_VERT, raw)
		# display progress printouts
		core.print_progress_oneline(core.get_readfrom_byte() / len(raw))
		retme.append(thisface)
	return retme

def parse_pmx_textures(raw: bytearray) -> List[str]:
	# first item is int, how many textures
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of textures         =", i)
	retme = []
	for d in range(i):
		filepath = core.my_unpack("t", raw)
		# print(filepath)
		retme.append(filepath)
	return retme

def parse_pmx_materials(raw: bytearray) -> List[pmxstruct.PmxMaterial]:
	# first item is int, how many materials
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of materials        =", i)
	retme = []
	for d in range(i):
		(name_jp, name_en, diffR, diffG, diffB, diffA, specR, specG, specB, specpower) = core.my_unpack("t t 4f 4f", raw)
		# print(name_jp, name_en)
		(ambR, ambG, ambB, flags, edgeR, edgeG, edgeB, edgeA, edgescale, tex_idx) = core.my_unpack("3f B 5f" + IDX_TEX, raw)
		no_backface_culling = bool(flags & (1<<0)) # does this mean it is 2-sided?
		cast_ground_shadow  = bool(flags & (1<<1))
		cast_shadow         = bool(flags & (1<<2))
		receive_shadow      = bool(flags & (1<<3))
		use_edge            = bool(flags & (1<<4))
		vertex_color        = bool(flags & (1<<5)) # v2.1 only
		draw_as_points      = bool(flags & (1<<6)) # v2.1 only
		draw_as_lines       = bool(flags & (1<<7)) # v2.1 only
		# assemble all the info into a list
		flaglist = [no_backface_culling, cast_ground_shadow, cast_shadow, receive_shadow, use_edge, vertex_color,
					draw_as_points, draw_as_lines]
		(sph_idx, sph_mode, toon_mode) = core.my_unpack(IDX_TEX + "b b", raw)
		if toon_mode == 0:
			# toon is using a texture reference
			toon_idx = core.my_unpack(IDX_TEX, raw)
		else:
			# toon is using one of the builtin toons, toon01.bmp thru toon10.bmp (values 0-9)
			toon_idx = core.my_unpack("b", raw)
		(comment, surface_ct) = core.my_unpack("t i", raw)
		# note: i structure the faces list into groups of 3 vertex indices, this is divided by 3 to match
		faces_ct = int(surface_ct / 3)
		
		# assemble all the data into a struct for returning
		thismat = pmxstruct.PmxMaterial(name_jp=name_jp, name_en=name_en,
										diffRGB=[diffR, diffG, diffB], specRGB=[specR, specG, specB],
										ambRGB=[ambR, ambG, ambB], alpha=diffA, specpower=specpower,
										edgeRGB=[edgeR, edgeG, edgeB], edgealpha=edgeA, edgesize=edgescale,
										tex_idx=tex_idx, sph_idx=sph_idx, toon_idx=toon_idx,
										sph_mode=sph_mode, toon_mode=toon_mode, comment=comment, faces_ct=faces_ct,
										flaglist=flaglist)
		
		retme.append(thismat)
	return retme

def parse_pmx_bones(raw: bytearray) -> List[pmxstruct.PmxBone]:
	# first item is int, how many bones
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of bones            =", i)
	retme = []
	for d in range(i):
		(name_jp, name_en, posX, posY, posZ, parent_idx, deform_layer, flags1, flags2) = core.my_unpack("t t 3f" + IDX_BONE + "i 2B", raw)
		# print(name_jp, name_en)
		tail_usebonelink =       bool(flags1 & (1<<0))
		rotateable =             bool(flags1 & (1<<1))
		translateable =          bool(flags1 & (1<<2))
		visible =                bool(flags1 & (1<<3))
		enabled =                bool(flags1 & (1<<4))
		ik =                     bool(flags1 & (1<<5))
		inherit_rot =            bool(flags2 & (1<<0))
		inherit_trans =          bool(flags2 & (1<<1))
		has_fixedaxis =          bool(flags2 & (1<<2))
		has_localaxis =          bool(flags2 & (1<<3))
		deform_after_phys =      bool(flags2 & (1<<4))
		has_external_parent =    bool(flags2 & (1<<5))
		# important for structure: tail type, inherit, fixed axis, local axis, ext parent, IK
		external_parent = None
		inherit_parent = inherit_influence = None
		fixedaxis = None
		local_axis_x_xyz = local_axis_z_xyz = None
		ik_target = ik_loops = ik_anglelimit = ik_links = None
		if tail_usebonelink:  # use index for bone its pointing at
			tail = core.my_unpack(IDX_BONE, raw)
		else:  # use offset
			tail = core.my_unpack("3f", raw)
		if inherit_rot or inherit_trans:
			(inherit_parent, inherit_influence) = core.my_unpack(IDX_BONE + "f", raw)
		if has_fixedaxis:
			# format is xyz obviously
			fixedaxis = core.my_unpack("3f", raw)
		if has_localaxis:
			(xx, xy, xz, zx, zy, zz) = core.my_unpack("3f 3f", raw)
			local_axis_x_xyz = [xx, xy, xz]
			local_axis_z_xyz = [zx, zy, zz]
		if has_external_parent:
			external_parent = core.my_unpack("i", raw)
		if ik:
			(ik_target, ik_loops, ik_anglelimit, num_ik_links) = core.my_unpack(IDX_BONE + "i f i", raw)
			# note: ik angle comes in as radians, i want to represent it as degrees
			ik_anglelimit = math.degrees(ik_anglelimit)
			ik_links = []
			for z in range(num_ik_links):
				(ik_link_idx, use_link_limits) = core.my_unpack(IDX_BONE + "b", raw)
				if use_link_limits:
					(minX, minY, minZ, maxX, maxY, maxZ) = core.my_unpack("3f 3f", raw)
					# note: these vals come in as XYZXYZ radians! must convert to degrees
					link = pmxstruct.PmxBoneIkLink(idx=ik_link_idx,
												   limit_min=[math.degrees(minX), math.degrees(minY), math.degrees(minZ)],
												   limit_max=[math.degrees(maxX), math.degrees(maxY), math.degrees(maxZ)])
				else:
					link = pmxstruct.PmxBoneIkLink(idx=ik_link_idx)
				ik_links.append(link)
				
		# assemble all the info into a struct for returning
		thisbone = pmxstruct.PmxBone(
			name_jp=name_jp, name_en=name_en, pos=[posX, posY, posZ], parent_idx=parent_idx,
			deform_layer=deform_layer, deform_after_phys=deform_after_phys,
			has_rotate=rotateable, has_translate=translateable, has_visible=visible, has_enabled=enabled,
			# all ik stuff
			has_ik=ik, ik_target_idx=ik_target, ik_numloops=ik_loops, ik_angle=ik_anglelimit, ik_links=ik_links,
			# all tail stuff
			tail_usebonelink=tail_usebonelink, tail=tail,
			# all partial-inherit stuff
			inherit_rot=inherit_rot, inherit_trans=inherit_trans, inherit_ratio=inherit_influence, inherit_parent_idx=inherit_parent,
			# all fixed-axis stuff
			has_fixedaxis=has_fixedaxis, fixedaxis=fixedaxis,
			# all local-axis stuff
			has_localaxis=has_localaxis, localaxis_x=local_axis_x_xyz, localaxis_z=local_axis_z_xyz,
			# all external parent stuff
			has_externalparent=has_external_parent, externalparent=external_parent)
		
		retme.append(thisbone)
	return retme

def parse_pmx_morphs(raw: bytearray) -> List[pmxstruct.PmxMorph]:
	# first item is int, how many morphs
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of morphs           =", i)
	retme = []
	for d in range(i):
		(name_jp, name_en, panel, morphtype, itemcount) = core.my_unpack("t t b b i", raw)
		# print(name_jp, name_en)
		these_items = []
		# what to unpack varies on morph type, 9 possibilities + some for v2.1
		if morphtype == 0:
			# group
			for z in range(itemcount):
				(morph_idx, influence) = core.my_unpack(IDX_MORPH + "f", raw)
				item = pmxstruct.PmxMorphItemGroup(morph_idx=morph_idx, value=influence)
				these_items.append(item)
		elif morphtype == 1:
			# vertex
			for z in range(itemcount):
				(vert_idx, transX, transY, transZ) = core.my_unpack(IDX_VERT + "3f", raw)
				item = pmxstruct.PmxMorphItemVertex(vert_idx=vert_idx, move=[transX, transY, transZ])
				these_items.append(item)
		elif morphtype == 2:
			# bone
			for z in range(itemcount):
				(bone_idx, transX, transY, transZ, rotqX, rotqY, rotqZ, rotqW) = core.my_unpack(IDX_BONE + "3f 4f", raw)
				rotX, rotY, rotZ = core.quaternion_to_euler([rotqW, rotqX, rotqY, rotqZ])
				item = pmxstruct.PmxMorphItemBone(bone_idx=bone_idx, move=[transX, transY, transZ], rot=[rotX, rotY, rotZ])
				these_items.append(item)
		elif 3 <= morphtype <= 7:
			# UV
			# what these values do depends on the UV layer they are affecting, but the docs dont say what...
			# oh well, i dont need to use them so i dont care :)
			for z in range(itemcount):
				(vert_idx, A, B, C, D) = core.my_unpack(IDX_VERT + "4f", raw)
				item = pmxstruct.PmxMorphItemUV(vert_idx=vert_idx, move=[A,B,C,D])
				these_items.append(item)
		elif morphtype == 8:
			# material
			# this_item = core.my_unpack(IDX_MAT + "b 4f 3f    f 3f 4f f    4f 4f 4f", raw)
			for z in range(itemcount):
				(mat_idx, is_add, diffR, diffG, diffB, diffA, specR, specG, specB) = core.my_unpack(IDX_MAT+"b 4f 3f", raw)
				(specpower, ambR, ambG, ambB, edgeR, edgeG, edgeB, edgeA, edgesize) = core.my_unpack("f 3f 4f f", raw)
				(texR, texG, texB, texA, sphR, sphG, sphB, sphA, toonR, toonG, toonB, toonA) = core.my_unpack("4f 4f 4f", raw)
				item = pmxstruct.PmxMorphItemMaterial(
					mat_idx=mat_idx, is_add=is_add, alpha=diffA, specpower=specpower,
					diffRGB=[diffR, diffG, diffB], specRGB=[specR, specG, specB], ambRGB=[ambR, ambG, ambB],
					edgeRGB=[edgeR, edgeG, edgeB], edgealpha=edgeA, edgesize=edgesize,
					texRGBA=[texR, texG, texB, texA], sphRGBA=[sphR, sphG, sphB, sphA], toonRGBA=[toonR, toonG, toonB, toonA]
				)
				these_items.append(item)
		elif morphtype == 9:
			# (2.1 only) flip
			for z in range(itemcount):
				(morph_idx, influence) = core.my_unpack(IDX_MORPH + "f", raw)
				item = pmxstruct.PmxMorphItemFlip(morph_idx=morph_idx, value=influence)
				these_items.append(item)
		elif morphtype == 10:
			# (2.1 only) impulse
			for z in range(itemcount):
				(rb_idx, is_local, movX, movY, movZ, rotX, rotY, rotZ) = core.my_unpack(IDX_RB + "b 3f 3f", raw)
				item = pmxstruct.PmxMorphItemImpulse(rb_idx=rb_idx, is_local=is_local,
													 move=[movX, movY, movZ], rot=[rotX, rotY, rotZ])
				these_items.append(item)
		else:
			raise RuntimeError("unsupported morph type value", morphtype)
		
		# display progress printouts
		core.print_progress_oneline(core.get_readfrom_byte() / len(raw))
		# assemble the data into struct for returning
		thismorph = pmxstruct.PmxMorph(name_jp=name_jp, name_en=name_en, panel=panel, morphtype=morphtype, items=these_items)
		retme.append(thismorph)
	return retme

def parse_pmx_dispframes(raw: bytearray) -> List[pmxstruct.PmxFrame]:
	# first item is int, how many dispframes
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of dispframes       =", i)
	retme = []
	for d in range(i):
		(name_jp, name_en, is_special, itemcount) = core.my_unpack("t t b i", raw)
		# print(name_jp, name_en)
		these_items = []
		for z in range(itemcount):
			is_morph = core.my_unpack("b", raw)
			if is_morph:
				morph_idx = core.my_unpack(IDX_MORPH, raw)
				this_item = [is_morph, morph_idx]
			else:
				bone_idx = core.my_unpack(IDX_BONE, raw)
				this_item = [is_morph, bone_idx]
			these_items.append(this_item)
		# assemble the data into struct for returning
		thisframe = pmxstruct.PmxFrame(name_jp=name_jp, name_en=name_en, is_special=is_special, items=these_items)
		retme.append(thisframe)
	return retme

def parse_pmx_rigidbodies(raw: bytearray) -> List[pmxstruct.PmxRigidBody]:
	# first item is int, how many rigidbodies
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of rigidbodies      =", i)
	retme = []
	for d in range(i):
		(name_jp, name_en, bone_idx, group, nocollide_mask, shape) = core.my_unpack("t t" + IDX_BONE + "b H b", raw)
		# print(name_jp, name_en)
		# shape: 0=sphere, 1=box, 2=capsule
		(sizeX, sizeY, sizeZ, posX, posY, posZ, rotX, rotY, rotZ) = core.my_unpack("3f 3f 3f", raw)
		(mass, move_damp, rot_damp, repel, friction, physmode) = core.my_unpack("5f b", raw)
		# physmode: 0=follow bone, 1=physics, 2=physics rotate only (pivot on bone)
		
		# note: rotation comes in as XYZ radians, must convert to degrees for my struct
		rot = [math.degrees(rotX), math.degrees(rotY), math.degrees(rotZ)]
		
		# display progress printouts
		core.print_progress_oneline(core.get_readfrom_byte() / len(raw))
		# assemble the data into struct for returning
		thisbody = pmxstruct.PmxRigidBody(name_jp=name_jp, name_en=name_en, bone_idx=bone_idx,
			pos=[posX, posY, posZ], rot=rot, size=[sizeX, sizeY, sizeZ], shape=shape, group=group,
			nocollide_mask=nocollide_mask, phys_mode=physmode, phys_mass=mass, phys_move_damp=move_damp,
			phys_rot_damp=rot_damp, phys_repel=repel, phys_friction=friction
		)
		retme.append(thisbody)
	return retme

def parse_pmx_joints(raw: bytearray) -> List[pmxstruct.PmxJoint]:
	# first item is int, how many joints
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of joints           =", i)
	retme = []
	for d in range(i):
		(name_jp, name_en, jointtype, rb1_idx, rb2_idx, posX, posY, posZ) = core.my_unpack("t t b 2" + IDX_RB + "3f", raw)
		# jointtype: 0=spring6DOF, all others are v2.1 only!!!! 1=6dof, 2=p2p, 3=conetwist, 4=slider, 5=hinge
		# print(name_jp, name_en)
		(rotX, rotY, rotZ, posminX, posminY, posminZ, posmaxX, posmaxY, posmaxZ) = core.my_unpack("3f 3f 3f", raw)
		(rotminX, rotminY, rotminZ, rotmaxX, rotmaxY, rotmaxZ) = core.my_unpack("3f 3f", raw)
		(springposX, springposY, springposZ, springrotX, springrotY, springrotZ) = core.my_unpack("3f 3f", raw)
		
		# note: rot/rotmin/rotmax all come in as XYZ radians, must convert to degrees for my struct
		rot = [math.degrees(rotX), math.degrees(rotY), math.degrees(rotZ)]
		rotmin = [math.degrees(rotminX), math.degrees(rotminY), math.degrees(rotminZ)]
		rotmax = [math.degrees(rotmaxX), math.degrees(rotmaxY), math.degrees(rotmaxZ)]
		
		# display progress printouts
		core.print_progress_oneline(core.get_readfrom_byte() / len(raw))
		# assemble the data into list for returning
		thisjoint = pmxstruct.PmxJoint(name_jp=name_jp, name_en=name_en, jointtype=jointtype,
			rb1_idx=rb1_idx, rb2_idx=rb2_idx, pos=[posX, posY, posZ], rot=rot,
			movemin=[posminX, posminY, posminZ], movemax=[posmaxX, posmaxY, posmaxZ],
			movespring=[springposX, springposY, springposZ], rotmin=rotmin,
			rotmax=rotmax, rotspring=[springrotX, springrotY, springrotZ]
			)
		retme.append(thisjoint)
	return retme

def parse_pmx_softbodies(raw: bytearray) -> List[pmxstruct.PmxSoftBody]:
	# i don't plan to support v2.1 so I'm not gonna try to hard to understand the meaning of these data fields
	# this is mostly to consume the data so there are no bytes left over when done parsing a file to trigger warnings
	# note: this is also untested because i dont care about it lol
	i = core.my_unpack("i", raw)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of softbodies       =", i)
	retme = []
	for d in range(i):
		(name_jp, name_en, shape, idx_mat, group, nocollide_mask, flags) = core.my_unpack("t t b" + IDX_MAT + "b H b", raw)
		# i should upack the flags here but idgaf
		(b_link_create_dist, num_clusters, total_mass, collision_marign, aerodynamics_model) = core.my_unpack("iiffi", raw)
		(vcf, dp, dg, lf, pr, vc, df, mt, rch, kch, sch, ah) = core.my_unpack("12f", raw)
		(srhr_cl, skhr_cl, sshr_cl, sr_splt_cl, sk_splt_cl, ss_splt_cl) = core.my_unpack("6f", raw)
		(v_it, p_it, d_it, c_it, mat_lst, mat_ast, mat_vst, num_anchors) = core.my_unpack("8i", raw)
		anchors_list = []
		for z in range(num_anchors):
			# (idx_rb, idx_vert, near_mode)
			this_anchor = core.my_unpack(IDX_RB + IDX_VERT + "b", raw)
			anchors_list.append(this_anchor)
		num_vertex_pin = core.my_unpack("i", raw)
		vertex_pin_list = []
		for z in range(num_vertex_pin):
			vertex_pin = core.my_unpack(IDX_VERT, raw)
			vertex_pin_list.append(vertex_pin)

		# assemble the data into struct for returning
		thissoft = pmxstruct.PmxSoftBody(
			name_jp, name_en, shape, idx_mat, group, nocollide_mask, flags,
			b_link_create_dist, num_clusters, total_mass, collision_marign, aerodynamics_model,
			vcf, dp, dg, lf, pr, vc, df, mt, rch, kch, sch, ah,
			srhr_cl, skhr_cl, sshr_cl, sr_splt_cl, sk_splt_cl, ss_splt_cl,
			v_it, p_it, d_it, c_it, mat_lst, mat_ast, mat_vst, anchors_list, vertex_pin_list
		)
		retme.append(thissoft)
	return retme

########################################################################################################################

def encode_pmx_lookahead(thispmx: pmxstruct.Pmx) -> tuple:
	# takes the ENTIRE pmx list-form as its input, not juse one section
	# need to do some lookahead scanning before I can properly begin with the header and whatnot
	# specifically i need to get the "addl vec4 per vertex" and count the # of each type of thing
	addl_vec4s = max(len(v.addl_vec4s) for v in thispmx.verts)
	num_verts = len(thispmx.verts)
	num_tex = len(thispmx.textures)
	num_mat = len(thispmx.materials)
	num_bone = len(thispmx.bones)
	num_morph = len(thispmx.morphs)
	num_rb = len(thispmx.rigidbodies)
	num_joint = len(thispmx.joints)
	retme = (addl_vec4s, num_verts, num_tex, num_mat, num_bone, num_morph, num_rb, num_joint)
	return retme

def encode_pmx_header(nice: pmxstruct.PmxHeader, lookahead: tuple) -> bytearray:
	expectedmagic = bytearray([0x50, 0x4D, 0x58, 0x20])
	fmt_magic = "4s f b"
	# note: hardcoding number of globals as 8 when the format is technically flexible
	numglobal = 8
	out = core.my_pack(fmt_magic, (expectedmagic, nice.ver, numglobal))
	
	# now build the list of 8 global flags
	fmt_globals = str(numglobal) + "b"
	globalflags = [-1] * 8
	# byte 0: encoding
	if ENCODE_WITH_UTF8:
		core.set_encoding("utf_8")
		globalflags[0] = 1
	else:
		core.set_encoding("utf_16_le")
		globalflags[0] = 0
	# byte 1: additional vec4 per vertex
	global ADDL_VERTEX_VEC4
	ADDL_VERTEX_VEC4 = lookahead[0]
	globalflags[1] = lookahead[0]
	# bytes 2-7: data size to use for index references
	vertex_categorize = lambda x: 1 if x <= 255 else (2 if x <= 65535 else (4 if x <= 2147483647 else 0))
	other_categorize =  lambda x: 1 if x <= 127 else (2 if x <= 32767 else (4 if x <= 2147483647 else 0))
	globalflags[2] = vertex_categorize(lookahead[1])
	for i in range(3, 8):
		globalflags[i] = other_categorize(lookahead[i - 1])
	global IDX_VERT, IDX_TEX, IDX_MAT, IDX_BONE, IDX_MORPH, IDX_RB
	vert_conv = {1: "B", 2: "H", 4: "i"}
	conv = {1: "b", 2: "h", 4: "i"}
	IDX_VERT =  vert_conv[globalflags[2]]
	IDX_TEX =   conv[globalflags[3]]
	IDX_MAT =   conv[globalflags[4]]
	IDX_BONE =  conv[globalflags[5]]
	IDX_MORPH = conv[globalflags[6]]
	IDX_RB =    conv[globalflags[7]]
	out += core.my_pack(fmt_globals, globalflags)
	# finally handle the model names & comments
	# (name_jp, name_en, comment_jp, comment_en)
	out += core.my_pack("t t t t", [nice.name_jp, nice.name_en, nice.comment_jp, nice.comment_en])
	return out

def encode_pmx_vertices(nice: List[pmxstruct.PmxVertex]) -> bytearray:
	# first item is int, how many vertices
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of verts            =", i)
	# [posX, posY, posZ, normX, normY, normZ, u, v, addl_vec4s, weighttype, weights, edgescale]
	bdef1_fmt = IDX_BONE
	bdef2_fmt = "2%s f" % IDX_BONE
	bdef4_fmt = "4%s 4f" % IDX_BONE
	sdef_fmt =  "2%s 10f" % IDX_BONE
	qdef_fmt =  bdef4_fmt
	for d, vert in enumerate(nice):
		# first, basic stuff
		packme = vert.pos + vert.norm + vert.uv  # concat these
		out += core.my_pack("8f", packme)
		# then, some number of vec4s (probably none)
		# structure it like this so even if a user modifies the vec4s incorrectly it will still write fine
		for z in range(ADDL_VERTEX_VEC4):
			try:				out += core.my_pack("4f", vert.addl_vec4s[z])
			except IndexError:	out += core.my_pack("4f", [0, 0, 0, 0])
		
		out += core.my_pack("b", vert.weighttype)
		# weights = vert[10]
		# 0 = BDEF1 = [b1]
		# 1 = BDEF2 = [b1, b2, b1w]
		# 2 = BDEF4 = [b1, b2, b3, b4, b1w, b2w, b3w, b4w]
		# 3 = sdef =  [b1, b2, b1w] + weight_sdef = [[c1, c2, c3], [r01, r02, r03], [r11, r12, r13]]
		# 4 = qdef =  [b1, b2, b3, b4, b1w, b2w, b3w, b4w]  (only in pmx v2.1)

		if vert.weighttype == 0:
			# BDEF1
			out += core.my_pack(bdef1_fmt, vert.weight)
		elif vert.weighttype == 1:
			# BDEF2
			# (b1, b2, b1w)
			out += core.my_pack(bdef2_fmt, vert.weight)
		elif vert.weighttype == 2:
			# BDEF4
			# (b1, b2, b3, b4, b1w, b2w, b3w, b4w)
			out += core.my_pack(bdef4_fmt, vert.weight)
		elif vert.weighttype == 3:
			# SDEF
			# ([b1, b2, b1w], [c1, c2, c3], [r01, r02, r03], [r11, r12, r13])
			packme = vert.weight + core.flatten(vert.weight_sdef)
			out += core.my_pack(sdef_fmt, packme)
		elif vert.weighttype == 4:
			# it must be using QDEF, a type only for PMX v2.1 which I dont need to support so idgaf
			# (b1, b2, b3, b4, b1w, b2w, b3w, b4w)
			out += core.my_pack(qdef_fmt, vert.weight)
		else:
			core.MY_PRINT_FUNC("invalid weight type for vertex", vert.weighttype)
			
		# then there is one final float after the weight crap
		out += core.my_pack("f", vert.edgescale)
		# display progress printouts
		core.print_progress_oneline(ENCODE_PERCENT_VERT * d / i)
	return out

def encode_pmx_surfaces(nice: list) -> bytearray:
	# surfaces is just another name for faces
	# first item is int, how many !vertex indices! there are, NOT the actual number of faces
	# each face is 3 vertex indices
	i = len(nice)
	out = core.my_pack("i", i * 3)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of faces            =", i)
	for d, face in enumerate(nice):
		# each entry is a group of 3 vertex indeces that make a face
		out += core.my_pack("3" + IDX_VERT, face)
		# display progress printouts
		core.print_progress_oneline(ENCODE_PERCENT_VERT + (ENCODE_PERCENT_FACE * d / i))
	return out

def encode_pmx_textures(nice: list) -> bytearray:
	# first item is int, how many textures
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of textures         =", i)
	for d, filepath in enumerate(nice):
		out += core.my_pack("t", filepath)
	return out

def encode_pmx_materials(nice: List[pmxstruct.PmxMaterial]) -> bytearray:
	# first item is int, how many materials
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of materials        =", i)
	# this fmt is when the toon is using a texture reference
	mat_fmtA = "t t 4f 4f 3f B 5f 2%s b b %s t i" % (IDX_TEX, IDX_TEX)
	# this fmt is when the toon is using a builtin toon, toon01.bmp thru toon10.bmp (values 0-9)
	mat_fmtB = "t t 4f 4f 3f B 5f 2%s b b b  t i" % IDX_TEX
	for d, mat in enumerate(nice):
		flagsum = 0
		for pos, flag in enumerate(mat.flaglist):
			# reassemble the bits into a byte
			flagsum += 1 << pos if bool(flag) else 0
		# note: i structure the faces list into groups of 3 vertex indices, this is divided by 3 to match, so now i need to undivide
		verts_ct = 3 * mat.faces_ct
		packme = [mat.name_jp, mat.name_en, *mat.diffRGB, mat.alpha, *mat.specRGB, mat.specpower, *mat.ambRGB,
				  flagsum, *mat.edgeRGB, mat.edgealpha, mat.edgesize, mat.tex_idx, mat.sph_idx, mat.sph_mode,
				  mat.toon_mode, mat.toon_idx, mat.comment, verts_ct]
		# the size for packing of the "toon_idx" arg depends on the "toon_mode" arg, but the number and order is the same
		if mat.toon_mode:
			# toon is using one of the builtin toons, toon01.bmp thru toon10.bmp (values 0-9)
			out += core.my_pack(mat_fmtB, packme)
		else:
			# toon is using a texture reference
			out += core.my_pack(mat_fmtA, packme)
	
	return out

def encode_pmx_bones(nice: List[pmxstruct.PmxBone]) -> bytearray:
	# first item is int, how many bones
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of bones            =", i)
	fmt_bone = "t t 3f %s i 2B" % IDX_BONE
	fmt_bone_inherit = "%s f" % IDX_BONE
	fmt_bone_ik = "%s i f i" % IDX_BONE
	fmt_bone_ik_linkA = "%s b" % IDX_BONE
	fmt_bone_ik_linkB = "%s b 6f" % IDX_BONE
	for d, bone in enumerate(nice):
		# (name_jp, name_en, posX, posY, posZ, parent_idx, deform_layer)
		packme = [bone.name_jp, bone.name_en, *bone.pos, bone.parent_idx, bone.deform_layer]
		# next are the two flag-bytes (flags1, flags2)
		# reassemble the bits into a byte
		flagsum1 = 0
		flagsum1 += (1 << 0) if bool(bone.tail_usebonelink) else 0
		flagsum1 += (1 << 1) if bool(bone.has_rotate) else 0
		flagsum1 += (1 << 2) if bool(bone.has_translate) else 0
		flagsum1 += (1 << 3) if bool(bone.has_visible) else 0
		flagsum1 += (1 << 4) if bool(bone.has_enabled) else 0
		flagsum1 += (1 << 5) if bool(bone.has_ik) else 0
		flagsum2 = 0
		flagsum2 += (1 << 0) if bool(bone.inherit_rot) else 0
		flagsum2 += (1 << 1) if bool(bone.inherit_trans) else 0
		flagsum2 += (1 << 2) if bool(bone.has_fixedaxis) else 0
		flagsum2 += (1 << 3) if bool(bone.has_localaxis) else 0
		flagsum2 += (1 << 4) if bool(bone.deform_after_phys) else 0
		flagsum2 += (1 << 5) if bool(bone.has_externalparent) else 0
		packme += [flagsum1, flagsum2]
		out += core.my_pack(fmt_bone, packme)
		
		# tail will always exist but type will vary
		if bone.tail_usebonelink:  # use index for bone its pointing at
			out += core.my_pack(IDX_BONE, bone.tail)
		else:  # use offset
			out += core.my_pack("3f", bone.tail)

		# then is all the "might or might not exist" stuff
		if bone.inherit_rot or bone.inherit_trans:
			out += core.my_pack(fmt_bone_inherit, [bone.inherit_parent_idx, bone.inherit_ratio])
		if bone.has_fixedaxis:
			out += core.my_pack("3f", bone.fixedaxis)  # format is xyz obviously
		if bone.has_localaxis:
			out += core.my_pack("6f", [*bone.localaxis_x, *bone.localaxis_z])  # (xx, xy, xz, zx, zy, zz)
		if bone.has_externalparent:
			out += core.my_pack("i", bone.externalparent)
		
		if bone.has_ik:  # ik:
			# (ik_target, ik_loops, ik_anglelimit, ik_numlinks)
			# note: my struct holds ik_angle as degrees, file spec holds it as radians
			out += core.my_pack(fmt_bone_ik, [bone.ik_target_idx, bone.ik_numloops,
											  math.radians(bone.ik_angle), len(bone.ik_links)])
			for iklink in bone.ik_links:
				# bool(list) means "is the list non-empty and also not None"
				if iklink.limit_min and iklink.limit_max:
					# note: my struct holds limit_min/max as degrees, file spec holds it as radians
					limitminmax = []
					for lim in iklink.limit_min:
						limitminmax.append(math.radians(lim))
					for lim in iklink.limit_max:
						limitminmax.append(math.radians(lim))
					out += core.my_pack(fmt_bone_ik_linkB, [iklink.idx, True, *limitminmax])
				else:
					out += core.my_pack(fmt_bone_ik_linkA, [iklink.idx, False])
	return out

def encode_pmx_morphs(nice: List[pmxstruct.PmxMorph]) -> bytearray:
	# first item is int, how many morphs
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of morphs           =", i)
	fmt_morph = "t t b b i"
	fmt_morph_group = "%s f" % IDX_MORPH
	fmt_morph_flip = fmt_morph_group
	fmt_morph_vert = "%s 3f" % IDX_VERT
	fmt_morph_bone = "%s 3f 4f" % IDX_BONE
	fmt_morph_uv = "%s 4f" % IDX_VERT
	fmt_morph_mat = "%s b 4f 3f    f 3f 4f f    4f 4f 4f" % IDX_MAT
	fmt_morph_impulse = "%s b 3f 3f" % IDX_RB
	for d, morph in enumerate(nice):
		# (name_jp, name_en, panel, morphtype, itemcount)
		out += core.my_pack(fmt_morph, [morph.name_jp, morph.name_en, morph.panel, morph.morphtype, len(morph.items)])
		
		for z in morph.items:
			# for each morph in the group morph, or vertex in the vertex morph, or bone in the bone morph....
			# what to unpack varies on morph type, 9 possibilities + some for v2.1
			if morph.morphtype == 0:  # group
				z: pmxstruct.PmxMorphItemGroup
				out += core.my_pack(fmt_morph_group, [z.morph_idx, z.value])
			elif morph.morphtype == 1:  # vertex
				z: pmxstruct.PmxMorphItemVertex
				out += core.my_pack(fmt_morph_vert, [z.vert_idx, *z.move])
			elif morph.morphtype == 2:  # bone
				z: pmxstruct.PmxMorphItemBone
				(rotqW, rotqX, rotqY, rotqZ) = core.euler_to_quaternion(z.rot)
				# (bone_idx, transX, transY, transZ, rotqX, rotqY, rotqZ, rotqW)
				out += core.my_pack(fmt_morph_bone, [z.bone_idx, *z.move, rotqX, rotqY, rotqZ, rotqW])
			elif 3 <= morph.morphtype <= 7:  # UV
				z: pmxstruct.PmxMorphItemUV
				# what these values do depends on the UV layer they are affecting, but the docs dont say what...
				# oh well, i dont need to use them so i dont care :)
				out += core.my_pack(fmt_morph_uv, [z.vert_idx, *z.move])
			elif morph.morphtype == 8:  # material
				z: pmxstruct.PmxMorphItemMaterial
				# (mat_idx, is_add, diffR, diffG, diffB, diffA, specR, specG, specB) = core.unpack(IDX_MAT+"b 4f 3f", raw)
				# (specpower, ambR, ambG, ambB, edgeR, edgeG, edgeB, edgeA, edgesize) = core.unpack("f 3f 4f f", raw)
				# (texR, texG, texB, texA, sphR, sphG, sphB, sphA, toonR, toonG, toonB, toonA) = core.unpack("4f 4f 4f", raw)
				packme = [z.mat_idx, z.is_add, *z.diffRGB, z.alpha, *z.specRGB, z.specpower, *z.ambRGB, *z.edgeRGB,
						  z.edgealpha, z.edgesize, *z.texRGBA, *z.sphRGBA, *z.toonRGBA]
				out += core.my_pack(fmt_morph_mat, packme)
			elif morph.morphtype == 9:  # (2.1 only) flip
				z: pmxstruct.PmxMorphItemFlip
				out += core.my_pack(fmt_morph_flip, [z.morph_idx, z.value])
			elif morph.morphtype == 10:  # (2.1 only) impulse
				z: pmxstruct.PmxMorphItemImpulse
				# (rb_idx, is_local, movX, movY, movZ, rotX, rotY, rotZ)
				out += core.my_pack(fmt_morph_impulse, [z.rb_idx, z.is_local, *z.move, *z.rot])
			else:
				core.MY_PRINT_FUNC("unsupported morph type value", morph.morphtype)
		
		# display progress printouts
		core.print_progress_oneline(ENCODE_PERCENT_VERTFACE + (ENCODE_PERCENT_MORPH * d / i))
	return out

def encode_pmx_dispframes(nice: List[pmxstruct.PmxFrame]) -> bytearray:
	# first item is int, how many dispframes
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of dispframes       =", i)
	fmt_frame = "t t b i"
	fmt_frame_item_morph = "b %s" % IDX_MORPH
	fmt_frame_item_bone =  "b %s" % IDX_BONE
	for d, frame in enumerate(nice):
		# (name_jp, name_en, is_special, itemcount)
		out += core.my_pack(fmt_frame, [frame.name_jp, frame.name_en, frame.is_special, len(frame.items)])
		
		for entry in frame.items:
			if entry[0]:  # entry[0] means is_morph
				out += core.my_pack(fmt_frame_item_morph, entry)
			else:
				out += core.my_pack(fmt_frame_item_bone, entry)
	return out

def encode_pmx_rigidbodies(nice: List[pmxstruct.PmxRigidBody]) -> bytearray:
	# first item is int, how many rigidbodies
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of rigidbodies      =", i)
	fmt_rbody = "t t %s b H b 3f 3f 3f 5f b" % IDX_BONE
	for d, b in enumerate(nice):
		# note: my struct holds rotation as XYZ degrees, must convert to radians for file
		rot = [math.radians(r) for r in b.rot]
		
		packme = [b.name_jp, b.name_en, b.bone_idx, b.group, b.nocollide_mask, b.shape, *b.size, *b.pos, *rot,
				  b.phys_mass, b.phys_move_damp, b.phys_rot_damp, b.phys_repel, b.phys_friction, b.phys_mode]
		out += core.my_pack(fmt_rbody, packme)
	
	return out

def encode_pmx_joints(nice: List[pmxstruct.PmxJoint]) -> bytearray:
	# first item is int, how many joints
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of joints           =", i)
	fmt_joint = "t t b 2%s 3f 3f 3f 3f 3f 3f 3f 3f" % IDX_RB
	for d, j in enumerate(nice):
		# note: my struct holds rot/rotmin/rotmax as XYZ degrees, must convert to radians for file
		rot = [math.radians(r) for r in j.rot]
		rotmin = [math.radians(r) for r in j.rotmin]
		rotmax = [math.radians(r) for r in j.rotmax]
		
		packme = [j.name_jp, j.name_en, j.jointtype, j.rb1_idx, j.rb2_idx, *j.pos, *rot, *j.movemin,
				  *j.movemax, *rotmin, *rotmax, *j.movespring, *j.rotspring]
		out += core.my_pack(fmt_joint, packme)
	return out

def encode_pmx_softbodies(nice: List[pmxstruct.PmxSoftBody]) -> bytearray:
	# i don't plan to support v2.1 so I'm not gonna try to hard to understand the meaning of these data fields
	# this is mostly to consume the data so there are no bytes left over when done parsing a file to trigger warnings
	# note: this is also untested because i dont care about it lol
	i = len(nice)
	out = core.my_pack("i", i)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...# of softbodies       =", i)
	fmt_sb = "t t b %s b H b iiffi 12f 6f 7i" % IDX_MAT
	fmt_sb_anchor = "%s %s b" % (IDX_RB, IDX_VERT)
	for d, s in enumerate(nice):
		# (name_jp, name_en, shape, idx_mat, group, nocollide_mask, flags) = core.my_unpack("t t b" + IDX_MAT + "b H b", raw)
		# (b_link_create_dist, num_clusters, total_mass, collision_marign, aerodynamics_model) = core.my_unpack("iiffi", raw)
		# (vcf, dp, dg, lf, pr, vc, df, mt, rch, kch, sch, ah) = core.my_unpack("12f", raw)
		# (srhr_cl, skhr_cl, sshr_cl, sr_splt_cl, sk_splt_cl, ss_splt_cl) = core.my_unpack("6f", raw)
		# (v_it, p_it, d_it, c_it, mat_lst, mat_ast, mat_vst) = core.my_unpack("7i", raw)
		packme = [
			s.name_jp, s.name_en, s.shape, s.idx_mat, s.group, s.nocollide_mask, s.flags,
			s.b_link_create_dist, s.num_clusters, s.total_mass, s.collision_margin, s.aerodynamics_model,
			s.vcf, s.dp, s.dg, s.lf, s.pr, s.vc, s.df, s.mt, s.rch, s.kch, s.sch, s.ah,
			s.srhr_cl, s.skhr_cl, s.sshr_cl, s.sr_splt_cl, s.sk_splt_cl, s.ss_splt_cl,
			s.v_it, s.p_it, s.d_it, s.c_it, s.mat_lst, s.mat_ast, s.mat_vst, s.anchors_list, s.vertex_pin_list
		]
		out += core.my_pack(fmt_sb, packme)
		
		# (num_anchors)
		out += core.my_pack("i", len(s.anchors_list))
		for anchor in s.anchors_list:
			# (idx_rb, idx_vert, near_mode)
			out += core.my_pack(fmt_sb_anchor, anchor)
			
		# (num_pins)
		out += core.my_pack("i", len(s.vertex_pin_list))
		for pin in s.vertex_pin_list:
			out += core.my_pack(IDX_VERT, pin)
	
	return out


########################################################################################################################

def read_pmx(pmx_filename: str, moreinfo=False) -> pmxstruct.Pmx:
	global PMX_MOREINFO
	PMX_MOREINFO = moreinfo
	pmx_filename_clean = core.get_clean_basename(pmx_filename) + ".pmx"
	# assumes the calling function already verified correct file extension
	core.MY_PRINT_FUNC("Begin reading PMX file '%s'" % pmx_filename_clean)
	pmx_bytes = core.read_binfile_to_bytes(pmx_filename)
	core.MY_PRINT_FUNC("...total size   = %s" % core.prettyprint_file_size(len(pmx_bytes)))
	core.MY_PRINT_FUNC("Begin parsing PMX file '%s'" % pmx_filename_clean)
	core.reset_unpack()
	core.print_progress_oneline(0)
	A = parse_pmx_header(pmx_bytes)
	if PMX_MOREINFO: core.MY_PRINT_FUNC("...PMX version  = v%s" % str(A.ver))
	core.MY_PRINT_FUNC("...model name   = JP:'%s' / EN:'%s'" % (A.name_jp, A.name_en))
	B = parse_pmx_vertices(pmx_bytes)
	C = parse_pmx_surfaces(pmx_bytes)
	D = parse_pmx_textures(pmx_bytes)
	E = parse_pmx_materials(pmx_bytes)
	F = parse_pmx_bones(pmx_bytes)
	G = parse_pmx_morphs(pmx_bytes)
	H = parse_pmx_dispframes(pmx_bytes)
	I = parse_pmx_rigidbodies(pmx_bytes)
	J = parse_pmx_joints(pmx_bytes)
	if A.ver == 2.1:
		# if version==2.1, parse soft bodies
		K = parse_pmx_softbodies(pmx_bytes)
	else:
		# otherwise, dont
		K = []
	
	bytes_remain = len(pmx_bytes) - core.get_readfrom_byte()
	if bytes_remain != 0:
		core.MY_PRINT_FUNC("Warning: finished parsing but %d bytes are left over at the tail!" % bytes_remain)
		core.MY_PRINT_FUNC("The file may be corrupt or maybe it contains unknown/unsupported data formats")
		core.MY_PRINT_FUNC(pmx_bytes[core.get_readfrom_byte():])
	core.MY_PRINT_FUNC("Done parsing PMX file '%s'" % pmx_filename_clean)
	retme = pmxstruct.Pmx(header=A,
						  verts=B,
						  faces=C,
						  texes=D,
						  mats=E,
						  bones=F,
						  morphs=G,
						  frames=H,
						  rbodies=I,
						  joints=J,
						  sbodies=K)
	return retme


def write_pmx(pmx_filename: str, pmx: pmxstruct.Pmx, moreinfo=False) -> None:
	global PMX_MOREINFO
	PMX_MOREINFO = moreinfo
	pmx_filename_clean = core.get_clean_basename(pmx_filename) + ".pmx"
	# recives object 	(......)
	# assumes the calling function already verified correct file extension
	core.MY_PRINT_FUNC("Begin encoding PMX file '%s'" % pmx_filename_clean)

	if PMX_MOREINFO: core.MY_PRINT_FUNC("...PMX version  = v%s" % str(pmx.header.ver))
	core.MY_PRINT_FUNC("...model name   = JP:'%s' / EN:'%s'" % (pmx.header.name_jp, pmx.header.name_en))
	
	# arg "pmx" is the same structure created by "read_pmx()"
	# assume the object is perfect, no sanity-checking needed
	output_bytes = bytearray()
	global ENCODE_PERCENT_VERT
	global ENCODE_PERCENT_FACE
	global ENCODE_PERCENT_VERTFACE
	global ENCODE_PERCENT_MORPH
	
	# total progress = verts + faces/4 + sum of morphs/2
	total_vert = len(pmx.verts) * ENCODE_FACTOR_VERT
	total_face = len(pmx.faces) * ENCODE_FACTOR_FACE
	total_morph = sum([len(m.items) for m in pmx.morphs]) * ENCODE_FACTOR_MORPH
	ALLPROGRESSIZE = total_vert + total_face + total_morph
	ENCODE_PERCENT_VERT = total_vert / ALLPROGRESSIZE
	ENCODE_PERCENT_FACE = total_face / ALLPROGRESSIZE
	ENCODE_PERCENT_VERTFACE = ENCODE_PERCENT_VERT + ENCODE_PERCENT_FACE
	ENCODE_PERCENT_MORPH = total_morph / ALLPROGRESSIZE
	
	core.print_progress_oneline(0)
	lookahead = encode_pmx_lookahead(pmx)
	output_bytes += encode_pmx_header(pmx.header, lookahead)
	output_bytes += encode_pmx_vertices(pmx.verts)
	output_bytes += encode_pmx_surfaces(pmx.faces)
	output_bytes += encode_pmx_textures(pmx.textures)
	output_bytes += encode_pmx_materials(pmx.materials)
	output_bytes += encode_pmx_bones(pmx.bones)
	output_bytes += encode_pmx_morphs(pmx.morphs)
	output_bytes += encode_pmx_dispframes(pmx.frames)
	output_bytes += encode_pmx_rigidbodies(pmx.rigidbodies)
	output_bytes += encode_pmx_joints(pmx.joints)
	if pmx.header == 2.1:
		# if version==2.1, parse soft bodies
		output_bytes += encode_pmx_softbodies(pmx.softbodies)

	# done encoding!!

	core.MY_PRINT_FUNC("Begin writing PMX file '%s'" % pmx_filename_clean)
	core.MY_PRINT_FUNC("...total size   = %s" % core.prettyprint_file_size(len(output_bytes)))
	core.write_bytes_to_binfile(pmx_filename, output_bytes)
	core.MY_PRINT_FUNC("Done writing PMX file '%s'" % pmx_filename_clean)
	# done with everything!
	return None


########################################################################################################################
def main():
	core.MY_PRINT_FUNC("Specify a PMX file to attempt parsing and writeback")
	input_filename = core.prompt_user_filename(".pmx")
	# input_filename = "pmxtest.pmx"
	Z = read_pmx(input_filename, moreinfo=True)
	write_pmx("____pmxparser_selftest_DELETEME.pmx", Z, moreinfo=True)
	ZZ = read_pmx("____pmxparser_selftest_DELETEME.pmx", moreinfo=True)
	core.MY_PRINT_FUNC("")
	bb = core.read_binfile_to_bytes(input_filename)
	bb2 = core.read_binfile_to_bytes("____pmxparser_selftest_DELETEME.pmx")
	core.MY_PRINT_FUNC("Is the binary EXACTLY identical to original?", bb == bb2)
	exact_result = Z == ZZ
	core.MY_PRINT_FUNC("Is the readback EXACTLY identical to original?", exact_result)
	if not exact_result:
		fuzzy_result = core.recursively_compare(Z, ZZ)
		core.MY_PRINT_FUNC("Is the readback ALMOST identical to the original?", not fuzzy_result)
		core.MY_PRINT_FUNC("Max difference between two floats:", core.MAXDIFFERENCE)
		core.MY_PRINT_FUNC("Number of floats that exceed reasonable threshold 0.0005:", fuzzy_result)
	core.pause_and_quit("Parsed without error")

########################################################################################################################
# after all the funtions are defined, actually execute main()
if __name__ == '__main__':
	core.MY_PRINT_FUNC("Nuthouse01 - 1/24/2021 - v5.06")
	if DEBUG:
		main()
	else:
		try:
			main()
		except (KeyboardInterrupt, SystemExit):
			# this is normal and expected, do nothing and die normally
			pass
		except Exception as ee:
			# if an unexpected error occurs, catch it and print it and call core.pause_and_quit so the window stays open for a bit
			core.MY_PRINT_FUNC(ee.__class__.__name__, ee)
			core.pause_and_quit("ERROR: something truly strange and unexpected has occurred, sorry, good luck figuring out what tho")
