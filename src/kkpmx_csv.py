# Cazoo - 2021-05-29
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
from typing import List
import re
import os
import copy


try:
	# these imports work if running from double-click on THIS script
	import nuthouse01_core as core
	import nuthouse01_pmx_parser as pmxlib
	import nuthouse01_pmx_struct as pmxstruct
	import _prune_unused_bones as bonelib
	#import _translate_to_english
	import _translation_tools as tlTools
	import morph_scale
	import kkpmx_core as kklib
except ImportError as eee:
	print(eee.__class__.__name__, eee)
	print("ERROR: Failed to import some of the necessary files, all scripts must be together in the same folder!")
	print("...press ENTER to exit...")
	input()
	exit()
	core = pmxlib = pmxstruct = morph_scale = bonelib = None

####################
### CSV Printers ###
####################

def csv__print_all_of(pmx, input_filename_pmx):
	pass

def csv__from_bones(pmx, input_filename_pmx): ### [01]
	"""
Print all bones of the model into a locale invariant CSV representation, incl. IKLink

Output: PMX file '[modelname]_parentTails.pmx'
	"""
	myarr=[]

	__write_header(myarr, "h__bone")
#Bone,"センター","center",0,0,0,6.707446,0,1,1,0,1,0,"全ての親",1,"センター先",0,0,0,0,0,0,1,"",0,0,0,0,0,1,0,0,0,0,1,0,0,"",0,57.29578
	for (idx,bone) in enumerate(pmx.bones):
	#def csv__from_bone(pmx, myarr, bone_idx):
		#	## make array if not array
		#	if (isinstance(bone_idx, list)): bone_arr = bone_idx
		#	else: bone_arr = [bone_idx]
		#core.MY_PRINT_FUNC(bone)
		if idx == 1: break
		tail_name = ""
		ik_target_name = ""
		parent_name = ""
		inherit_parent_name = ""
		if bone.fixedaxis is None:          bone.fixedaxis = [0,0,0]
		if bone.localaxis_x is None:        bone.localaxis_x = [0,0,0]
		if bone.localaxis_z is None:        bone.localaxis_z = [0,0,0]
		if bone.parent_idx != -1:
			parent_name         = '"' + pmx.bones[bone.parent_idx].name_jp + '"'
		if bone.tail_usebonelink               and bone.tail               != -1:
			tail_name           = '"' + pmx.bones[bone.tail].name_jp + '"'
		if bone.ik_target_idx      is not None and bone.ik_target_idx      != -1:
			ik_target_name      = '"' + pmx.bones[bone.ik_target_idx].name_jp + '"'
		if bone.inherit_parent_idx is not None and bone.inherit_parent_idx != -1:
			inherit_parent_name = '"' + pmx.bones[bone.inherit_parent_idx].name_jp + '"'
		###
		
		#;Bone
		#,ボーン名,ボーン名(英)
		arr = [bone.name_jp, bone.name_en]
		#,変形階層,物理後(0/1) \\ Deform hierarchy
		arr.append(bone.deform_layer)
		arr.append(bone.deform_after_phys)
		#,位置_x,位置_y,位置_z \\ position
		arr.append(bone.pos)
		#,回転(0/1),移動(0/1),IK(0/1),表示(0/1),操作(0/1)
		arr.append(bone.has_rotate)
		arr.append(bone.has_translate)
		arr.append(bone.has_ik)
		arr.append(bone.has_visible)
		arr.append(bone.has_enabled)
		#,親ボーン名,表示先(0:オフセット/1:ボーン),表示先ボーン名
		arr.append(parent_name)
		arr.append(bone.tail_usebonelink)
		arr.append(tail_name)
		#,オフセット_x,オフセット_y,オフセット_z
		arr.append([0,0,0] if bone.tail_usebonelink else bone.tail)
		#,ローカル付与(0/1),回転付与(0/1),移動付与(0/1)
		arr.append(bone.inherit_parent_idx is not None)
		arr.append(bone.inherit_rot)
		arr.append(bone.inherit_trans)
		#,付与率,付与親名
		arr.append(get_value_or_default(bone.inherit_ratio, 1))
		arr.append(inherit_parent_name)
		#,軸制限(0/1)#,制限軸_x,制限軸_y,制限軸_z
		arr.append(bone.has_fixedaxis)
		arr.append(bone.fixedaxis)
		#,ローカル軸(0/1),  ローカルX軸_x,ローカルX軸_y,ローカルX軸_z,  ローカルZ軸_x,ローカルZ軸_y,ローカルZ軸_z
		arr.append(bone.has_localaxis)
		arr.append(bone.localaxis_x) ## default = [1,0,0]
		arr.append(bone.localaxis_z) ## default = [0,0,1]
		#,外部親(0/1),外部親Key
		arr.append(bone.has_externalparent)
		arr.append(bone.externalparent if bone.has_externalparent else 0)
		#,IKTarget名,IKLoop,IK単位角[deg]
		arr.append(ik_target_name)
		if bone.has_ik:
			arr.append(bone.ik_numloops) ### "" instead of 0
			arr.append(bone.ik_angle) ### "" instead of value
		else: arr.append([0,0])
		
		myarr.append( __stringify_array_for_csv("Bone,", arr))
	### ;IKLink	親ボーン名	Linkボーン名	角度制限(0/1)	XL[deg]	XH[deg]	YL[deg]	YH[deg]	ZL[deg]	ZH[deg]
	### IKLink	右手先IK	右手首S	0	0	0	0	0	0	0
	### self.idx, self.limit_min, self.limit_max ## (either both None or both not)
		if (bone.ik_links is not None):
		#	myarr.append("IK:" + str([[pmx.bones[i.idx].name_jp,i.limit_min,i.limit_max] for i in bone.ik_links]) + " # from ["+bone.name_jp+"]")
			myarr.append("IKLink," + str([core.flatten([pmx.bones[i.idx].name_jp,i.limit_min,i.limit_max]) for i in bone.ik_links]) + " # from ["+bone.name_jp+"]")
		#core.MY_PRINT_FUNC(mystr)
	core.write_list_to_txtfile(input_filename_pmx+"_bones.txt", myarr)

# /(\*)?self.(\w+) = \w+/ --> /arr.append\((?{1}mat.\2:[mat.\2])\)/
### True & False to 1&0 \\ tex.idx \\ float
## ^(VertexMorph,"[\w\.]+",\d+),(0|-?\d,[\dE\-]+),(0|-?\d,[\dE\-]+),(0|-?\d,[\dE\-]+)$  --> \1,"\2","\3","\4"
def csv__from_mat(pmx, myarr, mat_idx, newName = None):
	##;Material
	## Material,'cf_m_body', 'cf_m_body', 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0, -1, 1, 0, 1, '', 1505, True, True, True, True, True, False, False, False
	mat = pmx.materials[mat_idx]
	if newName == None: newName = mat.name_jp
	
	##,材質名,材質名(英)
	arr = [newName, mat.name_en]
	##,拡散色_R,拡散色_G,拡散色_B,拡散色_A(非透過度)
	arr.append(mat.diffRGB)
	arr.append(mat.alpha)
	##,反射色_R,反射色_G,反射色_B,反射強度
	arr.append(mat.specRGB)
	arr.append(mat.specpower)
	##,環境色_R,環境色_G,環境色_B
	arr.append(mat.ambRGB)
	##,両面描画(0/1),地面影(0/1),セルフ影マップ(0/1),セルフ影(0/1),頂点色(0/1),描画(0:Tri/1:Point/2:Line),エッジ(0/1)
	fl = [int(i) for i in mat.flaglist] ## 0:Two sided, 1:Ground Shadow, 2:Self Shadow Map, 3:Self Shadow, 5:Top Color, 6+7:Drawing Mode(0,1,2), 4:Show Edge
	arr.append([fl[0], fl[1], fl[2], fl[3], fl[5]])
	arr.append([1 if fl[6] == 1 else 2 if fl[7] == 1 else 0])
	arr.append(fl[4])
	##,エッジサイズ,エッジ色_R,エッジ色_G,エッジ色_B,エッジ色_A
	arr.append(mat.edgesize)
	arr.append(mat.edgeRGB)
	arr.append(mat.edgealpha)
	##,テクスチャパス,スフィアテクスチャパス
	arr.append(get_name_or_default(pmx.textures, mat.tex_idx, "", True))
	arr.append(get_name_or_default(pmx.textures, mat.sph_idx, "", True))
	##,スフィアモード(0:無効/1:乗算/2:加算/3:サブテクスチャ)
	arr.append(mat.sph_mode)
	##,Toonテクスチャパス,メモ
	if mat.toon_mode == 0:
		arr.append(get_name_or_default(pmx.textures, mat.toon_idx, "", True))
	else:
		arr.append("toon{:02d}.bmp".format(mat.toon_idx+1))
	arr.append(mat.comment)
	##arr.append(mat.faces_ct) -- Calculated by number of faces that reference this texture
	
	#####
	myarr.append(__stringify_array_for_csv("Material,", arr))

def csv__from_vertex(pmx,myarr,vert_idx,offset=0):
	## make array if not array
	if (isinstance(vert_idx,list)): vert_arr = vert_idx
	else: vert_arr = [vert_idx]
	
	## Print
	__write_header(myarr, "h__verx")
	for (i,idx) in enumerate(vert_arr):
		v = pmx.verts[idx]
		#;Vertex,頂点Index, [位置_x,位置_y,位置_z], [法線_x,法線_y,法線_z], エッジ倍率, [UV_u,UV_v]
		arr = [offset+i, v.pos,  v.norm,  v.edgescale,  v.uv]
		#,追加UV1_x,追加UV1_y,追加UV1_z,追加UV1_w
		arr.append([0,0,0,0])
		#,追加UV2_x,追加UV2_y,追加UV2_z,追加UV2_w
		arr.append([0,0,0,0])
		#,追加UV3_x,追加UV3_y,追加UV3_z,追加UV3_w
		arr.append([0,0,0,0])
		#,追加UV4_x,追加UV4_y,追加UV4_z,追加UV4_w
		arr.append([0,0,0,0])
		#,ウェイト変形タイプ(0:BDEF1/1:BDEF2/2:BDEF4/3:SDEF/4:QDEF)
		arr.append(v.weighttype)
		#,ウェイト1_ボーン名,ウェイト1_ウェイト値,ウェイト2_ボーン名,ウェイト2_ウェイト値
		#,ウェイト3_ボーン名,ウェイト3_ウェイト値,ウェイト4_ボーン名,ウェイト4_ウェイト値
		w = v.weight
		if (v.weighttype == 0):   ## BDEF1/1
			arr.append([pmx.bones[w[0]].name_jp,1])
			arr.append(["",0])
			arr.append(["",0])
			arr.append(["",0])
		elif (v.weighttype == 1): ## BDEF2/2
			arr.append([pmx.bones[w[0]].name_jp,w[2]])
			arr.append([pmx.bones[w[1]].name_jp,1-w[2]])
			arr.append(["",0])
			arr.append(["",0])
		elif (v.weighttype == 2): ## BDEF4/3
			arr.append([pmx.bones[w[0]].name_jp,w[4]])
			arr.append([pmx.bones[w[1]].name_jp,w[5]])
			arr.append([pmx.bones[w[2]].name_jp,w[6]])
			arr.append([pmx.bones[w[3]].name_jp,w[7]])
		else:
			print("Found unknown weighttype '" + str(v.weighttype) + "'")
			arr.append(str(v.list()))
		#,C_x,C_y,C_z,R0_x,R0_y,R0_z,R1_x,R1_y,R1_z
		if v.weight_sdef is not None and len(v.weight_sdef) > 0:
			print("idx " + str(idx) + " had weight_sdef")
		if v.addl_vec4s is not None and len(v.addl_vec4s) > 0:
			print("idx " + str(idx) + " had addl_vec4s")
		arr.append([0,0,0  ,0,0,0  ,0,0,0])
		
		myarr.append(__stringify_array_for_csv("Vertex,", arr))

##################
### Generators ###
##################

### Takes Material and writes all faces and their vertices, with a given offset
def export_material_surface(pmx, input_filename_pmx): ### [06]
	"""
Input: STDIN -> Material ID or name, default = cf_m_body <br/>
Input: STDIN -> Offset to shift vertices (updates ref in faces) <br/>

Export a material with all faces and vertices as *.csv. <br/>
The default operation of the editor only writes the material + faces but leaves out the vertices.
This may be helpful in case you don't want to merge bones (but still want the material to reuse existing ones)
-- Reason: 'Add 2nd Model' works by simply appending each list of objects.
-- -- The 'Merge Bones' option then simply merges all bones who have the same name (incl. pre-existing ones)

An optional offset can be used to allow re-importing it later without overriding vertices.
- Note: Vertices are imported first, and will be adjusted by the editor to start at the first free index
-- -- Which will mess up the references in the faces, so make sure the first vertex index is correct.
-- -- For the same reason, it sometimes does not import everything. Just import the file again in that case
- You usually want the next free vertex of your target model, which is the number above the list in the vertex tab.

Output: CSV file '[modelname]_[mat.name_jp].csv'
"""
	myarr = []
	
	### Get Material
	mat = kklib.ask_for_material(pmx)
	name = mat.name_jp
	
	def __valid_check2(s): return s.isdigit()
	offset = int(core.MY_GENERAL_INPUT_FUNC(__valid_check2, "Enter offset (Type 0 for 'no change'): "))
	
	newName = core.MY_GENERAL_INPUT_FUNC(lambda x: True, "New material name (Leave empty for 'no change'): ")
	if not newName: newName = name
	
	mat_idx = find_mat(pmx, mat.name_jp)
	### Print Material
	__write_header(myarr, "h__mats")
	csv__from_mat(pmx, myarr, mat_idx, newName)
	
	### Find Faces
	faces = kklib.from_material_get_faces(pmx, mat_idx)
	
	### Collect Vertex
	vert_idx = list(set(core.flatten(faces)))
	vert_idx.sort()
	first = vert_idx[0]
	### Print Vertex
	csv__from_vertex(pmx, myarr, vert_idx, offset)
	
	### Print Faces (Vertices must exist before Faces can use them, so they are added afterwards)
	#offset2 = first - offset
	__write_header(myarr, "h__face")
	for idx,face in enumerate(faces):
		faceArr = [face[0]-first+offset,face[1]-first+offset,face[2]-first+offset]
		myarr.append('Face,"' + newName + '",' + str(idx) + "," + str(faceArr)[1:-1])
	
	from kkpmx_utils import slugify
	core.write_list_to_txtfile(input_filename_pmx[0:-4]+"_"+slugify(name)+".csv", myarr)

###############
### Helpers ###
###############

def find_bone(pmx,name,e=True): return morph_scale.get_idx_in_pmxsublist(name, pmx.bones, e)
def find_mat(pmx,name,e=True):  return morph_scale.get_idx_in_pmxsublist(name, pmx.materials, e)
def find_disp(pmx,name,e=True): return morph_scale.get_idx_in_pmxsublist(name, pmx.frames, e)

def translate_name(name_jp, name_en):
	if not(name_en is None or name_en == ""):   return name_en
	if not tlTools.needs_translate(name_jp):    return name_jp
	return tlTools.local_translate(name_jp)
def get_name_or_default(pmxArr, idx, default="", noField=False):
	"""
	:param pmxArr: The PMX list to read from
	:param idx: The index to access
	:param default: Value to use on error or if not found
	:param noField: True to not use '.name_jp'
	"""

	if idx is not None and idx != -1:
		try:
			if noField:
				return pmxArr[idx]
			return pmxArr[idx].name_jp
		except: pass
	return default
def get_value_or_default(value,default): return value if value is not None else default

### Add the True \ False replace ++ str()[1:-1] as well
#def __stringify_array(arr): return ','.join(['"' + str(x) + "'" from x in core.flatten(arr)])

def __write_header(myarr, type):
	
	##core: z__pmxe_X_csv_header: material, vertex, bone, morph, rigidbody, face
	headers = {
		"h__mats": core.pmxe_material_csv_header,
		"h__verx": core.pmxe_vertex_csv_header,
		"h__bone": core.pmxe_bone_csv_header,
		"h__face": core.pmxe_face_csv_header,
	}
	# [A]: print(', '.join(names))
	# [B]: print(*names, sep=", ") ## unpack list and print with separator
	# [C]: print str(names)[1:-1]  ## 'A', 'B', 'C'
	text = ','.join(headers[type])
	myarr.append(text)

def __stringify_array_for_csv(prefix, arr):
	#strarr = '"' + ','.join(['"' + str(x) + '"' for x in core.flatten(arr)]) + '"'
	strarr = ','.join(['"' + str(x) + '"' for x in core.flatten(arr)])
	strarr = re.sub(r'True','1',strarr)
	strarr = re.sub(r'False','0',strarr)
	#strarr = re.sub(r'None','',strarr)
	strarr = re.sub(r'"(-?\d+)\.0"',r'\1',strarr)
	strarr = re.sub(r'"(-?[\d\.]+(e[+\-]?\d+)?)"',r'\1',strarr)
	return prefix + strarr