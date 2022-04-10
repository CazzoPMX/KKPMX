# Cazoo - 2022-02-10
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
from typing import List
import re
import os
import copy
from datetime import datetime ### used in [end]

import kkpmx_property_parser as PropParser ## parseMatComments
import kkpmx_utils as util
from kkpmx_utils import find_bone, find_mat, find_disp, find_morph, find_rigid
import kkpmx_rigging as kkrig
from kkpmx_handle_overhang import run as runOverhang
from kkpmx_json_generator import GenerateJsonFile
try:
	import nuthouse01_core as core
	import nuthouse01_pmx_parser as pmxlib
	import nuthouse01_pmx_struct as pmxstruct
	import _translation_tools as tlTools
	import morph_scale
	from kkpmx_csv import csv__from_bones, csv__from_mat, csv__from_vertex, export_material_surface
except ImportError as eee:
	print(eee.__class__.__name__, eee)
	print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
	print("...press ENTER to exit...")
	input()
	exit()
	core = pmxlib = pmxstruct = morph_scale = None

## Local "moreinfo"
DEBUG = util.DEBUG or False
## Certain things which are only useful when developing
DEVDEBUG = False

#############
### Start ###
#############

helptext = {
'__do':'''
Separator between Main and Minor Methods. Will exit the program if chosen.
''','print_all_texture':'''=================================================
print_all_texture:

Output: TXT file '[modelname]_texture.txt'
''','list_arm_bones':'''=================================================
list_arm_bones:

Output: TXT file '[modelname]_listing.txt'
''','print_material_face_counts':'''=================================================
print_material_face_counts:

Input: PMX -> list of materials

Output: [0] name_jp / name_en: 0 + 4456 = 4456
''','print_material_bones':'''=================================================
print_material_bones:

Input: STDIN -> Ask for Material ID or name
Action: mat -> faces -> vertices -> bones

Output: STDOUT -> Unique list of used bones (Format: id, sorted)

'''}
def get_choices():
	return [
		("Show help for all",None),
		("Cleanup Model", cleanup_texture),
		("Make Material morphs", make_material_morphs),
		("Scan Plugin File", PropParser.parseMatComments),
		("Isolate protruding surfaces", runOverhang),
		("All-in-one converter", kk_quick_convert), 
		("----------", __do),
		("Parse Result from Plugin", GenerateJsonFile),
		("Export Material to CSV", export_material_surface),
		("Move material weights to new bones", move_weights_to_new_bone),
		("Print material bones", print_material_bones),
		("Slice helper", slice_helper),
		("Run Rigging Helpers", kkrig.run),
		("Draw Shader", PropParser.draw_toon_shader, True),
	]
def main(moreinfo=True):
	# promt choice
	choices = get_choices()
	idx = core.MY_SIMPLECHOICE_FUNC(range(len(choices)), [(str(i)+": "+str(choices[i][0])) for i in range(len(choices))])
	
	# generate helptext
	def print_help(_idx):
		name = choices[_idx][0]
		choice = choices[_idx][1]
		doc = None
		if choice.__doc__ is not None: doc = choice.__doc__
		elif choice.__name__ in helptext: doc = helptext[choice.__name__]
		if doc:
			line = "=================================================\n"
			doc = "{}===({}) {} ({}):\n{}{}".format(line, _idx, name, choice.__name__, "", doc)
		core.MY_PRINT_FUNC(doc if doc is not None else (f"<< no help for '{choices[_idx][0]}' >>"))
	if idx == 0: return [print_help(idx) for idx in range(1,len(choices))]
	elif idx == 6:
		if DEBUG:
			if util.ask_yes_no("Transfer Filenames"): transfer_names();
		exit()
	else: print_help(idx)
	# prompt PMX name
	core.MY_PRINT_FUNC(">> The script can be terminated at any point by pressing Ctrl+C")
	core.MY_PRINT_FUNC("Type the Name of the PMX input file (or drag'n'drop it into the console window)")
	input_filename_pmx = core.MY_FILEPROMPT_FUNC('.pmx')
	print("")
	if len(choices[idx]) == 3: pmx = None
	else: pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=moreinfo)
	print("==--==")
	choices[idx][1](pmx, input_filename_pmx)
	print("==--==")
	core.MY_PRINT_FUNC("Done!")
	return None

###################
### Main Method ###
###################

def cleanup_texture(pmx, input_filename_pmx, write_model=True, opt = {}): ### [01]
	"""
This is one of two main methods to make KK-Models look better.
It does the following things:

- disable "Bonelyfans", "Standard" (+ emblem if no texture)
- Simplify material names (removes "(Instance)" etc)
- After promting user for permission:
-  - if tex_idx != -1: Set diffRGB to [1,1,1] ++ add previous to comment
-  - else:             Set specRGB to [diffRGB] ++ add previous to comment
- If no toon: Set toon_idx = "toon02.bmp"
- Rename certain bones to match standard MMD better
- Only for KK-Models:
-  - Adjust Ankle Bones to avoid twisted feet
- Remove items with idx == -1 from dispframes [<< crashes MMD]
- Fix invalid vertex morphs [<< crashes MMD]

In some cases, this is already enough to make a model look good for simple animations.
Which is why this also standardizes color and toon,

Options (for Automization):
- "colors": bool -- Standardize colors. Asks user if None

Output: PMX File '[filename]_cleaned.pmx'
"""
	###############
	###### ---- materials
	def disable_mat(name_mat, no_tex_only=False):
		mat_idx = name_mat
		if type(name_mat) == str:
			mat_idx = find_mat(pmx, name_mat, False)
			if mat_idx == None: return
		if no_tex_only:
			if pmx.materials[mat_idx].tex_idx != -1:
				return
		pmx.materials[mat_idx].alpha = 0.0
		pmx.materials[mat_idx].edgesize = 0
		pmx.materials[mat_idx].flaglist[4] = False
	#disable_mat("Bonelyfans (Instance)")
	#disable_mat("Bonelyfans")
	#disable_mat("Bonelyfans*1")
	#disable_mat("Standard (Instance) (Instance)") ## Exists with kedama (?)
	#disable_mat("acs_m_kedama (Instance) (Instance)")
	kk_re = re.compile(r" ?\(Instance\)_?(\([-0-9]*\))?")
	flag = opt.get("colors", None)
	if flag is None: flag = util.ask_yes_no("Standardize Colors")
	for mat in pmx.materials:
		mat.name_jp = kk_re.sub("", mat.name_jp)
		mat.name_en = kk_re.sub("", mat.name_en)
		
		### Only if no custom toon registered
		if mat.toon_mode == 0 and mat.toon_idx < 0:
			mat.toon_mode = 1
			mat.toon_idx  = 1 ## toon02.bmp
		
		if not flag: continue
		
		### KK Materials with own texture rarely use the diffuse color
		### So replace it with [1,1,1] to make it fully visible
		skip = ["[0.0, 0.0, 0.0]", "[1.0, 1.0, 1.0]"]
		if (mat.tex_idx != -1):
			if str(mat.diffRGB) not in ["[0.5, 0.5, 0.5]", "[1.0, 1.0, 1.0]"]:
				mat.comment = mat.comment + "\r\n[Old Diffuse]: " + str(mat.diffRGB)
				mat.diffRGB = [1,1,1]
		elif mat.diffRGB != [1,1,1]:
			## Otherwise replicate it into specular to avoid white reflection
			skip_r = skip + [str(mat.diffRGB)]
			if str(mat.specRGB) not in skip_r:
				mat.comment = mat.comment + "\r\n[Old Specular]: " + str(mat.specRGB)
			mat.specRGB = mat.diffRGB
		else:
			if str(mat.specRGB) not in skip:
				mat.comment = mat.comment + "\r\n[Old Specular]: " + str(mat.specRGB)
			mat.specRGB = [0,0,0]
		
	#-------
	disable_mat("cf_m_emblem", no_tex_only=True)
	#-------
	## Make sure that all materials have unique names
	names = []
	for (idx, name) in enumerate([m.name_jp for m in pmx.materials]):
		suffix = 0
		mat = pmx.materials[idx]
		if name.startswith("Bonelyfans"): disable_mat(idx)
		if name.startswith("Standard"): disable_mat(idx)
		if name.startswith("acs_head_hana_botan"):
			pmx.materials[idx].flaglist[4] = False
		if name in names:
			while True:
				suffix += 1
				if ("{}*{}".format(name, suffix)) not in names: break
			pmx.materials[idx].name_jp = "{}*{}".format(mat.name_jp, suffix)
			pmx.materials[idx].name_en = "{}*{}".format(mat.name_en, suffix)
		names.append(mat.name_jp)
	
	## Maybe sort them:
	# [shadowcast], [<<face stuff>>], [<<hair>>], [body, "mm"], [shorts, bra, socks], [shoes,...],
	## [skirt: bot_misya], [shirt: top_inner], [jacket], [ribbon, necktie], [any acs_m_]
	
	###############
	###### ---- bones
	def rename_bone(org, newJP, newEN):
		tmp = find_bone(pmx, org, False)
		if tmp is not None:
			if newJP is not None: pmx.bones[tmp].name_jp = newJP
			if newEN is not None: pmx.bones[tmp].name_en = newEN
	def bind_bone(arr):
		while len(arr) > 1:
			parent = find_bone(pmx, arr[0], False)
			child = find_bone(pmx, arr[1], False)
			if parent is not None and child is not None:
				pmx.bones[parent].tail_usebonelink = True
				pmx.bones[parent].tail = child
			arr.pop(0)
	## rename Eyes: [両目x] to [両目], [左目x] to [左目], [右目x] to [右目]
	rename_bone("両目x", "両目", "both eyes")
	rename_bone("左目x", "左目", "eye L")
	rename_bone("右目x", "右目", "eye R")
	
	bind_bone(["左足", "左ひざ", "左足首", "左つま先"])
	bind_bone(["右足", "右ひざ", "右足首", "右つま先"])
	
	from itertools import product
	fingers = product(["左","右"], ["人指", "小指", "中指", "薬指"])
	for item in fingers: bind_bone([''.join(x) for x in product([''.join(item)], ["1", "2", "3"])])
	bind_bone(["左親指０", "左親指1", "左親指2"])
	bind_bone(["右親指０", "右親指1", "右親指2"])
	
	## Fix Feet
	def tmp(A, B, C):
		ankle = find_bone(pmx, A, False)
		if ankle is not None:
			posY = pmx.bones[ankle].pos[1]
			foot = find_bone(pmx, B, False)
			pmx.bones[foot].pos[1] = posY
			ik = find_bone(pmx, C, False)
			pmx.bones[ik].pos[1] = posY
			pmx.bones[ik].tail = [0, 0, 1.3]
	tmp("cf_d_leg03_L", "左足首", "左足ＩＫ")
	tmp("cf_d_leg03_R", "右足首", "右足ＩＫ")
	## add [グルーブ][groove] at [Y +0.2] between [center] and [BodyTop] :: Add [MVN], [no VIS] head optional
	## add [腰][waist] at ??? between [upper]/[lower] and [cf_j_hips]
		
	###############
	###### ---- morphs
	# Rename the morphs used by the 5 Speech Morphs
	usedMorphs = [
		["eye_face.f00_def_cl",			"face.default.close"],
		["eye_face.f00_egao_cl",		"face.smile.close"],
		["kuti_face.f00_a_l_op",		"mouth.a.open"],
		["kuti_face.f00_i_l_op",		"mouth.i.open"],
		["kuti_face.f00_u_l_op",		"mouth.u.open"],
		["kuti_face.f00_e_l_op",		"mouth.e.open"],
		["kuti_face.f00_o_l_op",		"mouth.o.open"],
		["eye_line_u.elu00_def_cl",		"eyeline_u.default.close"],
		["eye_line_u.elu00_egao_cl",	"eyeline_u.smile.close"],
		["eye_line_l.ell00_def_cl",		"eyeline_l.default.close"],
		["eye_line_l.ell00_egao_cl",	"eyeline_l.smile.close"],
		["kuti_ha.ha00_a_l_op",			"teeth.a.open"],
		["kuti_ha.ha00_i_l_cl",			"teeth.i.close"],
		["kuti_ha.ha00_e_s_op",			"teeth.e.open_s"],
	]
	
	for item in usedMorphs:
		morph = find_morph(pmx, item[0], False)
		if morph == -1: continue
		pmx.morphs[morph].name_jp = item[1]
		pmx.morphs[morph].name_en = item[1]
	
	pmx.morphs.append(pmxstruct.PmxMorph("unbounce", "unbounce", 4, 2, [
		pmxstruct.PmxMorphItemBone(find_bone(pmx, "右腕", False), [0,0,0], [0,0,-35]),
		pmxstruct.PmxMorphItemBone(find_bone(pmx, "左腕", False), [0,0,0], [0,0,35]),
	]))
	
	###############
	###### ---- dispframes
	## add [BodyTop], [両目], [eye_R, eye_L], [breast parent] [cf_j_hips] to new:[TrackAnchors]
	frames = [
		[0, find_bone(pmx, "両目", False)],      #	19.14828 - Over the head
		[0, find_bone(pmx, "左目", False)], [0, find_bone(pmx,"右目", False)],
		[0, find_bone(pmx, "cf_J_Eye_tz", False)],       #	- Between Eyes
		#[0, find_bone(pmx, "cf_J_FaceUp_ty", False)],   #	- Slightly below base of eyes
		#[0, find_bone(pmx, "首", False)],                #	15.45564 - Top of Arms
		[0, find_bone(pmx, "cf_j_spine03", False)],      #	14.10473 - Center of Chestbone
		#[0, find_bone(pmx, "上半身2", False)],            #	13.19746 - Bottom edge of Chestbone
		#[0, find_bone(pmx, "上半身", False)],             #	12.23842 - Slightly above navel
		[0, find_bone(pmx, "cf_j_hips", False)],        #	12.18513 - Navel
		#[0, find_bone(pmx, "下半身", False)],             #	12.13186 - Slightly above navel
		### navel -- 11.96193 < cf_d_sk_top (12.0253)
	]
	rename_bone("両目",          None, "Track Head")
	rename_bone("cf_J_Eye_tz",  None, "Track Eyes")
	rename_bone("cf_j_spine03", None, "Track Chest")
	rename_bone("cf_j_hips",    None, "Track Navel")
	
	if find_disp(pmx, "TrackAnchors", False) == -1:
		pmx.frames.append(pmxstruct.PmxFrame("TrackAnchors", "TrackAnchors", False, frames))
		
	if find_disp(pmx, "ChestGravity", False) == -1:
		src = find_bone(pmx, "cf_d_bust00", False)
		dst = find_bone(pmx, "cf_d_shoulder_L", False)
		if src != -1 and dst != -1:
			frames = [[0,idx] for idx in range(src, dst)]
			pmx.frames.append(pmxstruct.PmxFrame("ChestGravity", "ChestGravity", False, frames))
	
	if find_disp(pmx, "SkirtGravity", False) == -1:
		src = find_bone(pmx, "cf_d_sk_top", False)
		dst = find_bone(pmx, "cf_j_sk_07_05", False)
		if src != -1 and dst != -1:
			frames = [[0,idx] for idx in range(src, dst+1)]
			pmx.frames.append(pmxstruct.PmxFrame("SkirtGravity", "SkirtGravity", False, frames))
	
	def addIfNot(name, bone):
		disp = find_disp(pmx, name, False)
		if disp == -1: return
		if pmx.frames[disp].name_jp == "morebones": return
		_frames = map(lambda x: x[1], pmx.frames[disp].items)
		if type(bone) is not list: bone = [bone]
		for b in bone:
			idx = find_bone(pmx, b, False)
			if idx == -1: continue
			if idx in _frames: continue
			pmx.frames[disp].items.append([0, idx])
	
	addIfNot("体(上)", ["cf_s_spine03", "cf_s_spine02", "cf_s_spine01"]) ## spine to Upper Body
	addIfNot("体(下)", ["腰", "cf_j_waist02"]) ## waist to Lower Body
	
	
	
	
	### Clean up invalid dispframes
	for disp in pmx.frames:
		disp.items = list(filter(lambda x: x[1] not in [-1,None], disp.items))
	
	### Clean up invalid morphs
	vert_len = len(pmx.verts)
	for morph in pmx.morphs:
		if morph.morphtype != 1: continue
		morph.items = [m for (idx,m) in enumerate(morph.items) if m.vert_idx < vert_len]
	
	return end(pmx if write_model else None, input_filename_pmx, "_cleaned", "Performed minimal cleanup for working MMD")

def kk_quick_convert(pmx, input_filename_pmx):
	"""
All-in-one Converter

Assuming a raw, unmodified export straight from KK, this will perform several tasks.
All of which can be done individually through either the above list or the GUI of nuthouse01.
-- [ - ] Creating a backup file with "_org" if none exists
-- [ 1 ] Main cleanup of the model to make it work in MMD
-- [7 3] Asking for the *.json generated by the plugin & parsing it into the model
-- [Gui] Renaming & Sorting of Texture files (== "file_sort_textures.py")
-- [1-2] Apply several rigging improvements
-- [ 2 ] Optional: Adding Material Morphs to toggle them individually
-- [Gui] Running a general cleanup to reduce filesize (== "model_overall_cleanup.py")
-- -- This will also add translations for most untranslated phrases in the model
-- [ - ] If initially requested to not store per-step modifications, the model will be saved at this point.
-- [ 4 ] Optional: Trying to fix bleed-through texture overlaps (within a given bounding box)
-- -- Warning: Depending on the model size and the chosen bounding box, this can take some time.
-- -- -- One can choose between "Scan full material" | "Input manually" | "Restrict to Chest area"
-- -- This will always generate a new model file, in case results are not satisfying enough

There are some additional steps that cannot be done by a script; They will be mentioned again at the end
-- Go to the [TransformView (F9)] -> Search for [bounce] -> Set to 100% -> Menu=[File]: Update Model
-- [Edit(E)] -> Plugin(P) -> User -> Semi-Standard Bone Plugin -> Semi-Standard Bones (PMX) -> default or all (except [Camera Bone])
"""
	def section(msg): print("------\n> "+msg+"\n------")
	## ask if doing new model per step or only one at the end
	write_model = util.ask_yes_no("Store individual steps as own model (will copy into main file regardless)", "y")
	moreinfo = util.ask_yes_no("Display more details in some cases","n")
	all_yes = util.ask_yes_no("Do all yes","y")
	
	## rename input_filename_pmx to "_org"
	orgPath = input_filename_pmx[0:-4] + "_org.pmx"
	if os.path.exists(orgPath):
		section("[-1] Restore to original state")
		if all_yes or util.ask_yes_no("Found a backup, should the model be reset to its original state"):
			util.copy_file(orgPath, input_filename_pmx)
			pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=False)
	else:
		end(None, input_filename_pmx, "_org", "Created Backup file")
		util.copy_file(input_filename_pmx, orgPath)
	#-------------#
	section("[0] Bare minimum cleanup")
	if all_yes or util.ask_yes_no("Convert filenames in local folder","y"):
		ask_to_rename_extra(pmx, input_filename_pmx)
	## run cleanup_texture --- [0] because it renames the materials as well
	path = cleanup_texture(pmx, input_filename_pmx, write_model, {"colors": True})
	if write_model: util.copy_file(path, input_filename_pmx)
	#-------------#
	section("[1] Plugin File")
	## ask for parser file
	if all_yes or util.ask_yes_no("Using data generated by associated JSONGenerator Plugin of KK"):
		if GenerateJsonFile(pmx, input_filename_pmx):
			## run parseMatComments
			#>> <<< ask for base path
			_opt = {"apply": True if all_yes else None}
			path = PropParser.parseMatComments(pmx, input_filename_pmx, write_model, opt=_opt)
			if write_model and path != input_filename_pmx: util.copy_file(path, input_filename_pmx)
	#-------------#
	section("[2] Sort Textures (will make a backup of all files)")
	## run [core] sort textures (which edits in place) --- [2nd] to also sort the property files
	import file_sort_textures
	if not write_model: pmxlib.write_pmx(input_filename_pmx, pmx, moreinfo=moreinfo)
	print(">> Recommended: 2 (No) \\ 2 (only top-level) \\ 1 (Yes) ")
	print("")
	# Tell options: 2(No) \\ 2(only top-level) \\ 1(Yes) <<<<<<<<<<<<<<<<<<<<<<<<<
	file_sort_textures.__main(input_filename_pmx, moreinfo)
	if write_model:
		end(None, input_filename_pmx, "_sorted", "Sorted all texture files")
		path = core.get_unused_file_name(input_filename_pmx[0:-4] + "_sorted.pmx")
		util.copy_file(input_filename_pmx, path)
	print("-- Reparsing sorted model")
	pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=False) # Re-Import *.pmx bc no pmx argument
	#-------------#
	section("[3] Rigging")
	## run cleanup_texture --- after [1] because it utilizes Parser Comments
	path = kkrig.run(pmx, input_filename_pmx, moreinfo=moreinfo, write_model=write_model, _opt={"mode":0})
	if write_model: util.copy_file(path, input_filename_pmx)
	#-------------#
	section("[4] Cleanup & Morphs")	
	## ask to run make_material_morphs --- [3rd] to make use of untranslated names for sorting
	# ++ Clears and fills the [Facials] Frame with own morphs, which is again repopulated by sorting[5]
	if all_yes or util.ask_yes_no("Generate Material Morphs", "y"):
		## -- run make_material_morphs
		_opt = {"body": True if all_yes else None}
		path = make_material_morphs(pmx, input_filename_pmx, write_model, moreinfo=moreinfo, opt=_opt)
		if write_model: util.copy_file(path, input_filename_pmx)
	#-------------#
	section("[5] General Cleanup")
	
	## run [core] general cleanup
	import model_overall_cleanup
	model_overall_cleanup.__main(pmx, input_filename_pmx, moreinfo)
	path = input_filename_pmx[0:-4] + "_better.pmx"
	util.copy_file(path, input_filename_pmx)
	#if not write_model: delete the "_better" file (?)
	
	#-------------#
	section("[6] Fixing material bleed-through")
	print("Warning: Depending on the model size and the chosen bounding box, this can take some time.")
	if util.ask_yes_no("Execute bleed-through scanner(y) or doing it later(n)"):
		print(f"The following changes will be stored in a separate PMX file, so you can terminate at any point by pressing CTRL+C.")
		runOverhang(pmx, input_filename_pmx)
	## Tell to perform [bounce] (with steps)
	print("Do not forget to apply the additional fixes as explained above.")
	print("""
-- Go to the [TransformView (F9)] -> Search for [bounce] -> Set to 100% -> Menu=[File]: Update Model
-- [Edit(E)] -> Plugin(P) -> User -> Semi-Standard Bone Plugin -> Semi-Standard Bones (PMX) -> default or apply all (except [Camera Bone])
	""")
	## -- Tell that bounce will break all morphs if RegionSettings use ',' as separator
	## Tell to run semi-standard bones (PMX)
	## -- Do not add [view center] (or delete it afterwards) --> Model Movement is anchored to bone:0
	## Tell how to re-order materials and why they should do that
	######
	

#################
### Generates ###
#################

arrOne   = [1.0, 1.0, 1.0]
arrZero  = [  0,   0,   0]
arrOne4  = [1.0, 1.0, 1.0, 1.0]
arrOneA  = [1.0, 1.0, 1.0,   0]
arrZero4 = [  0,   0,   0,   0]
arrZeroA = [  0,   0,   0, 1.0]
def __append_itemmorph_mul(items, idx): # Multplies with 0 to hide
	if idx == None: return
	items.append(pmxstruct.PmxMorphItemMaterial(idx, 0, # isadd = False
		arrOne, arrOne, arrOne, 0.0, 1.0, ## Material: Keep color, but hide
		arrOne, 0.0, 1.0, ## Toggle Outline
		arrOne4, arrOne4, arrOne4 ## Keep Texture
	))
def __append_itemmorph_add(items, idx): # Adds 1 to show a hidden material
	if idx == None: return
	items.append(pmxstruct.PmxMorphItemMaterial(idx, 1, # isadd = True
		arrZero, arrZero, arrZero, 1.0, 0.0, ## Material: Keep color, but unhide
		arrZero, 1.0, 0.0, ## Toggle Outline
		arrZero4, arrZero4, arrZero4 ## Keep Texture
	))
def __append_itemmorph_sub(items, idx): # Subtracts 1 to hide a hidden material again
	if idx == None: return
	items.append(pmxstruct.PmxMorphItemMaterial(idx, 1, # isadd = True
		arrZero, arrZero, arrZero, -1.0, 0.0, ## Material: Keep color, but hide again
		arrZero, -1.0, 0.0, ## Toggle Outline
		arrZero4, arrZero4, arrZero4 ## Keep Texture
	))
def __append_bonemorph(items, idx, move, rot, name): ## morphtype: 2
	if idx == None: return
	item = pmxstruct.PmxMorphItemBone(idx, move, rot)
	if name != None:
		items.morphs.append(pmxstruct.PmxMorph(name, name, 4, 2, [ item ]))
	else:
		items.append(item)
def __append_vertexmorph(items, idx, move, name): ## morphtype: 1
	if idx == None: return
	item = pmxstruct.PmxMorphItemVertex(idx, move)
	if name != None:
		items.morphs.append(pmxstruct.PmxMorph(name, name, 4, 1, [ item ]))
	else:
		items.append(item)

#### JP originals
jpMats = ['[上下]半身','耳','頭','顔','体','舌','口内','胴','口元', '口中','後頭部']
# 眼(Eyes), 白目(sirome), 瞳(hitomi), まぶた(eyelids), ハイライト(Highlights), 黒目(kurome=Iris)
jpMats += ['白目','眼','瞳','まぶた','ハイライト','黒目','眉睫毛']
# 顔(Face), 口内+口中(Inside of Mouth), 舌(Tongue), 耳(Ears), 口元(Mouth)
# 頭(Head), 体(Body), [上下]半身(upper / lower body), 肌(Skin), 首(Neck), 胴(Trunk)
jpMats += ['肌', '首', '脚', '手', '歯', '目']
# 脚(Leg)  手(Hand)  歯(Teeth)  目(eye)


jpHair = ['髪', 'もみあげ','まつ毛','まゆ毛','サイドテール','横髪','あほ毛','前髪','後ろ髪','睫毛','後髪']
# もみあげ(Sideburns), 前髪(Forelock), 後ろ髪(Back Hair)
jpAccs = ['グローブ','チョーカー','ブーツ','帽子','頭リボン','ニーハイ', 'ソックス','靴','アクセサリー']
# ソックス(Socks), 靴(Shoes), アクセサリー(Accessories)
#>> 表情(Expression)
#>> パーカー(Parker), スカート(Skirt), パンツ(Pantsu)
#### EN originals
enMats =  ['Head','Face','Teeth','Eyes?','Tng','Tongue','Lash','(^|_)Ears?','Hair','Horns?','Neck']
enMats += ['Skin','Chest','Tummy','Foot','Feet','Body','Tail','breasts?']
enAccs = ['Accessories','Bracelet','Crown','Armband','Scrunchie','Headband','Flowers']
enAccs += ['decor', 'bow', 'Ribbon']
#### KK-Models
## All core mats
baseMats = ['body', 'mm', 'face', 'hair', 'noseline', 'tooth', 'eyeline', 'mayuge', 'sirome', 'hitomi', 'tang']
baseMats += ['expression']
## Aux parts that should always stay
accMatsNoHair = ['tail','acs_m_mimi_','kedama','mermaid','wing','cattail','cat_ear'] ## Hair & Kemomimi
accMatsNoHair += ['aku01_tubasa', 'back_angelwing'] ## Vanilla wings
#>	acs_m_mermaid ++ Fins
#>	acs_m_hair_*  -- Hair decoration
accMats = ['hair','ahoge'] + accMatsNoHair
hairAcc = ['mat_body','kamidome'] ## Common hair accs
## Additional parts that are not main clothing
accOnlyMats = ['socks','shoes','gloves','miku_headset','hood', 'mf_m_primmaterial']
accOnlyMats += ['^\'?cf_m_acs_'] + ['^\'?mf_m_acc'] + ['^\'?acs_(?!m_(' + '|'.join(accMatsNoHair) +  '|mimi))']
####--- 
rgxBase = 'cf_m_(' + '|'.join(baseMats) + ')'
rgxBase += '|' + '|'.join(accMats)
rgxBase += '|\\b(' + '|'.join(jpMats + jpHair) + ')'
rgxBase += '|' + '|'.join(enMats)
rgxBasnt = '|'.join(accOnlyMats)

rgxAcc  = '|'.join(accOnlyMats + jpAccs + enAccs)
rgxSkip = '|'.join(["Bonelyfans","shadowcast","Standard"])
####---
slot_dict = {
	"hair":   ["a_n_hair_pony", "a_n_hair_twin_L", "a_n_hair_twin_R", "a_n_hair_pin", "a_n_hair_pin_R", "a_n_headtop", "a_n_headflont", "a_n_head", "a_n_headside"],
	"face":   ["a_n_megane", "a_n_earrings_L", "a_n_earrings_R", "a_n_nose", "a_n_mouth"],
	"body":   ["a_n_neck", "a_n_bust_f", "a_n_bust", "a_n_nip_L", "a_n_nip_R"],
	"lower":  ["a_n_back", "a_n_back_L", "a_n_back_R", "a_n_waist", "a_n_waist_f", "a_n_waist_b", "a_n_waist_L", "a_n_waist_R", "a_n_leg_L", "a_n_leg_R", "a_n_knee_L", "a_n_knee_R"],
	"foot":   ["a_n_ankle_L", "a_n_ankle_R", "a_n_heel_L", "a_n_heel_R"],
	"upper":  ["a_n_shoulder_L", "a_n_shoulder_R", "a_n_elbo_L", "a_n_elbo_R", "a_n_arm_L", "a_n_arm_R"],
	"hand":   ["a_n_wrist_L", "a_n_wrist_R", "a_n_hand_L", "a_n_hand_R", "a_n_ind_L", "a_n_ind_R", "a_n_mid_L", "a_n_mid_R", "a_n_ring_L", "a_n_ring_R"],
	"nether": ["a_n_dan", "a_n_kokan", "a_n_ana"],
}
slotBody   = ["ct_head", "p_cf_body_00", "cf_J_FaceUp_ty"]
slotAlways = slot_dict["hair"] + slot_dict["face"] + ["ct_hairB", "ct_hairF", "ct_hairS"]
slotMostly = slot_dict["hand"] + slot_dict["foot"] + ["ct_gloves", "ct_socks", "ct_shoes_outer", "ct_shoes_inner"]
slotMed    = slot_dict["body"] + slot_dict["nether"]
slotFull   = slot_dict["lower"] + slot_dict["upper"]
slotCloth  = ["ct_clothesTop", "ct_clothesBot", "ct_bra", "ct_shorts", "ct_panst"] + slotMostly

rgx_filter = r'(eye|kuti)_[a-zLRM_]+\.[a-zLRM]+00\w+|mayuge\.\w+'

def make_material_morphs(pmx, input_filename_pmx, write_model=True, moreinfo=False, opt={}): ## [02]
	"""
Generates a Material Morph for each material to toggle its visibility (hide if visible, show if hidden).
- Note: This works for any model, not just from KK (albeit accuracy might suffer without standard names).

== Names & Bones
- If the materials have only JP names, it attempts to translate them before using as morph name (only standard from local dict).
- Assuming material names have indicative/simple names, also attempts to guess the role of a material
--- (== part of the body, a piece of clothing, an accessory) and generates groups based upon that.
--- Body parts will stay visible, but clothes / accessories can be toggled off as a whole.
- If the model has a standard root bone ('全ての親'), adds a morph to move the model downwards.
--- Can be used as an alternative for moving the body downwards in MMD (e.g. when hiding shoes).
- If the model has a standard center bone ('センター'), adds a morph to move the body downwards.
--- Can be used to test physics better in TransformView.

== Using the Plugin
- If the model has been decorated with Plugin Data, then the following groups will be added as well:
--- Head Acc   :: Accessories attached to hair, head, or face
--- Hand/Foot  :: Accessories attached to wrist, hand, ankle, or foot; incl. gloves, socks, and shoes
--- Neck/Groin :: Accessories attached to the neck, chest, groin, or rear
--- Body Acc   :: Accessories attached to the body in general (arms, shoulder, back, waist, leg)
-- > Tails, if recognized as such, will be considered part of the body and are always visible.

== Combination rules
- The order of operations makes no difference in effect.
- Every material has its own MorphToggle, except if the user declined the inclusion of body parts recognized as such.
- Recognized Body parts are excluded from all "Hide all" and "Show all" morphs.
- If an individual morph makes a material visible again, it can be hidden by the "Hide all" morph.
- If an individual morph hides a material, it can be made visible again with the "Show X" morph.
- If a material has been hidden by any "Hide all X" morph, it can be made visible again with its "Show X" morph.

Mode Interactions:
- Uses [JSONGenerator] Data if available -- "[:Slot:]"
- Overrides morphs if they already exist

Options (for Automization):
- body: bool -- False to skip 'Body part' morphs. Prompts if [None]

Output: PMX file '[modelname]_morphs.pmx' -- only if 'write_model' is True
 """
	moreinfo = moreinfo or DEBUG
	itemsCloth = []
	itemsAcc = []
	itemsSlots = { "always": [], "mostly": [], "med": [], "full": [], "slotMatch": False }
	flag = opt.get("body", None)
	flag2 = opt.get("Full", None)
	if flag is None: flag = util.ask_yes_no("Emit morphs for body-like materials", "n")
	if flag2 is None: flag2 = not util.ask_yes_no("Group by slots", "y")
	frame = []
	dictSlots = {}
	### If both flags, make sure that head+body is first
	if flag and not flag2:
		dictSlots["ct_head"] = []
		dictSlots["cf_J_FaceUp_ty"] = []
		dictSlots["p_cf_body_00"] = []
	
	def addMatMorph(name, arr, disp=None):
		if len(arr) == 0: return
		if type(name) is str: names = [ name, name ]
		else: names = name
		## Shrink prefix since only 13 letters are visible in [Facials] and *.vmd
		names[1] = re.sub(r'^ct_', '_', names[1])
		names[1] = re.sub(r'^a_n_', '__', names[1])
		
		## Replace if already exists
		tmp = find_morph(pmx, names[0], False)
		if tmp in [None,-1]:
			pmx.morphs.append(pmxstruct.PmxMorph(names[0], names[1], 4, 8, arr))
			if disp is not None: disp.append(len(pmx.morphs) - 1)
		else:
			pmx.morphs[tmp] = pmxstruct.PmxMorph(names[0], names[1], 4, 8, arr)
			#if disp is not None: disp.append(tmp)
	
	for idx, mat in enumerate(pmx.materials):
		### Filter out what we do not want
		if re.search(rgxSkip, mat.name_jp): continue
		name_both = f"'{mat.name_jp}'  '{mat.name_jp}'"
		isBody = re.search(rgxBase, name_both, re.I) is not None
		isBody = isBody and (re.search(rgxBasnt, name_both, re.I) is None)
		
		### Check if comments contain Slot names (added by Plugin Parser)
		if re.search(r'\[:Slot:\]', mat.comment):
			itemsSlots["slotMatch"] = True
			m = re.search(r'\[:Slot:\] (\w+)', mat.comment)[1]
			if m in slotBody   : isBody = True
			if m in slotCloth  : isBody = False
			if m is not None and len(m) > 0 and not (not flag and m in slotBody):
				dictSlots[m] = dictSlots.get(m, [])
				appender = __append_itemmorph_mul
				if re.search(r'_delta$', mat.name_jp): appender = __append_itemmorph_sub
				appender(dictSlots[m], idx)
				### Add extra slots for ct_clothesTop
				# ct_clothesTop, ct_top_parts_A, ct_top_parts_B, ct_top_parts_C
				if m == 'ct_clothesTop':
					mm = re.search(r'\[:TopId:\] (\w+)', mat.comment)
					if mm is not None:
						dictSlots[mm[1]] = dictSlots.get(mm[1], [])
						appender(dictSlots[mm[1]], idx)
			if m in slotAlways : __append_itemmorph_add(itemsSlots["always"], idx)
			if m in slotMostly : __append_itemmorph_add(itemsSlots["mostly"], idx)
			if m in slotMed    : __append_itemmorph_add(itemsSlots["med"]   , idx)
			if m in slotFull   : __append_itemmorph_add(itemsSlots["full"]  , idx)
		elif moreinfo and not isBody: print(f"{mat.name_jp} does not contain slot information")
		#>> mayuge, noseline, tooth, eyeline, sirome, hitomi
		
		### Skip the rest if part of Body ddMatMorph
		if isBody:
			# Make sure hidden body-like parts can be made visible
			if mat.alpha == 0: __append_itemmorph_add(itemsCloth, idx)
			if flag == False: continue
		
		items = []
		### if initially hidden, invert slider
		if (mat.alpha == 0): __append_itemmorph_add(items, idx)
		else: __append_itemmorph_mul(items, idx)
		### Make sure the morph has a proper name regardless
		name_en = translate_name(mat.name_jp, mat.name_en)
		
		name_jp = re.sub(r'( \(Instance\))+', '', mat.name_jp)
		name_en = re.sub(r'^cf_m_+|^acs_m_+|( \(Instance\))+', '', name_en)
		if flag2: addMatMorph([name_jp, name_en], items, frame)
		
		## Sort into Body, Accessories, Cloth
		if isBody: continue
		if re.search(rgxAcc, name_both, re.I): __append_itemmorph_mul(itemsAcc, idx)
		else: __append_itemmorph_mul(itemsCloth, idx)
	#############
	
	do_ver3_check(pmx)
	#### Add slot morphs
	# ask first to add, then use name "{slot}" as name
	if not flag2: [addMatMorph(key,  dictSlots[key], frame) for key in dictSlots.keys()]
	
	#### Add extra morphs
	items = []
	if find_morph(pmx, "Move Model downwards", False) == -1:
		__append_bonemorph(pmx, find_bone(pmx,"全ての親",False), [0,-3,0], [0,0,0], "Move Model downwards")
	if find_morph(pmx, "Move Body downwards", False) == -1:
		__append_bonemorph(pmx, find_bone(pmx,"センター",False), [0,-5,0], [0,0,0], "Move Body downwards")
	
	#### Add special morphs
	if itemsSlots.get("slotMatch", False):
		addMatMorph("Show:Head Acc",   itemsSlots["always"], frame)
		addMatMorph("Show:Hand/Foot",  itemsSlots["mostly"], frame)
		addMatMorph("Show:Neck/Groin", itemsSlots["med"]   , frame)
		addMatMorph("Show:Body Acc",   itemsSlots["full"]  , frame)
	addMatMorph("Hide Acc", itemsAcc, frame)
	addMatMorph("Hide Non-Acc", itemsCloth, frame)
	itemsBoth = list(filter(lambda x: x != None, core.flatten([ itemsCloth, itemsAcc ])))
	addMatMorph("BD-Suit", itemsBoth, frame)
	
	log_line = "Added Material Morphs"
	if not flag: log_line += " (without body-like morphs)"
	if len(frame) > 0:
		## Filter out the messy facials if they are added to display (only effective for reruns)
		_tmp = list(filter(lambda x: re.match(rgx_filter, pmx.morphs[x[1]].name_jp) == None, pmx.frames[1].items))
		pmx.frames[1].items = [[1,i] for i in core.flatten(frame)] + _tmp
	
	return end(pmx if write_model else None, input_filename_pmx, "_morphs", log_line)

def do_ver3_check(pmx):
	"""
	Checks for the existence of the naming scheme from a very specific group of models
	"""
	if find_mat(pmx, "【M2】上半身", False) < 0: return
	ver3List = [x.name_jp for x in pmx.materials]
	ver3Dict = { key: idx for (idx, key) in enumerate(ver3List) }
	
	def addMorphs(name, indices=None):
		## get all values
		names = list(filter(lambda x: x.startswith(name), ver3Dict.keys()))
		if len(names) == 0: return
		if indices == None: indices = [ver3Dict[key] for key in names]
		core.MY_PRINT_FUNC(f"-- Trying to add {name} morph...")
		### Add "Toggle On"
		items = []
		for idx in indices: __append_itemmorph_add(items, idx)
		pmx.morphs.append(pmxstruct.PmxMorph(name, f"Toggle {name} (On)", 4, 8, items))
		### Add "Toggle Off"
		items = []
		for idx in indices: __append_itemmorph_sub(items, idx)
		pmx.morphs.append(pmxstruct.PmxMorph(name + "2", f"Toggle {name} (Off)", 4, 8, items))
	#################
	addMorphs("【M1】"); addMorphs("【M2】"); addMorphs("【M3】")
	addMorphs("【C1】"); addMorphs("【C2】"); addMorphs("【C3】")
	##
	last = ver3Dict[list(filter(lambda x: x.startswith("【"), ver3Dict.keys()))[-1]]
	prefix = os.path.commonprefix([pmx.materials[last+1].name_jp, pmx.materials[last+3].name_jp])
	addMorphs(prefix, [ver3Dict[key] for key in ver3List[last+1:]])
	#################
	name = ""
	idx = 0
	core.MY_PRINT_FUNC("-- Trying to add [hadaka] morph...")
	try: ### Add morph to hide all parts
		items = []
		start = len(pmx.materials)-1
		while True:
			name = pmx.materials[start].name_jp
			if (name.startswith("【M2") or name == "生際"): break
			if start == 0: raise Exception("Could not find stop material.")
			start = start - 1
		for idx in range(start+1, len(pmx.materials)):
			__append_itemmorph_mul(items, idx)
		### Add these because some (wc__gym) tend to use custom materials and have these off
		__append_itemmorph_add(items, find_mat(pmx, "【M2】ボディ胸中下着用--------"))
		__append_itemmorph_add(items, find_mat(pmx, "【M2】上半身消し", False))
		__append_itemmorph_add(items, find_mat(pmx, "【M2】上半身"))
		__append_itemmorph_add(items, find_mat(pmx, "【M2】下半身"))
		__append_itemmorph_add(items, find_mat(pmx, "【M2】下半身消し", False))
		__append_itemmorph_add(items, find_mat(pmx, "【M2】"))
		pmx.morphs.append(pmxstruct.PmxMorph("裸", "Toggle [All]", 4, 8, items))
	except Exception as ee:
		print(ee)
		print("idx was " + str(idx) + " with name = " + str(name))
		core.MY_PRINT_FUNC("Could not add [hadaka] morph!")
	
	core.MY_PRINT_FUNC("-- Trying to add [body switch] morph...")
	try: ### Add body toggle if found
		items = []
		if find_mat(pmx, "【M1】") > -1:
			__append_itemmorph_sub(items, find_mat(pmx, "【M2】ボディ胸中下着用--------"))
			__append_itemmorph_add(items, find_mat(pmx, "【M2】上半身消し", False))
			__append_itemmorph_sub(items, find_mat(pmx, "【M2】上半身"))
			__append_itemmorph_sub(items, find_mat(pmx, "【M2】下半身"))
			__append_itemmorph_add(items, find_mat(pmx, "【M2】下半身消し", False))
			__append_itemmorph_sub(items, find_mat(pmx, "【M2】"))
			__append_itemmorph_add(items, find_mat(pmx, "【M1】ボディ胸中下着用--------"))
			__append_itemmorph_add(items, find_mat(pmx, "【M1】上半身"))
			__append_itemmorph_add(items, find_mat(pmx, "【M1】下半身"))
			__append_itemmorph_add(items, find_mat(pmx, "【M1】"))
			pmx.morphs.append(pmxstruct.PmxMorph("ボディ1<>2", "Toggle [Body]", 4, 8, items))
		else:
			core.MY_PRINT_FUNC("No [M1] found to add.")
	except Exception as ee:
		print(ee)
		core.MY_PRINT_FUNC("Could not add [body] morph!")

#### Cuts a surface along given vertices and allows them to be pulled apart at the new gap
def slice_helper(pmx, input_filename_pmx): ## [11]
	"""
Cuts a surface along given vertices and allows them to be pulled apart at the new gap.
It is recommended that the vertices form one continuous line; Use the [Selection Guide] for help.
-- The order of the vertices does not matter, as long as all can be lined up to form one clean cut.
It will generate two morphs to pull the seam apart. For that it will ask which direction is "Up" and which is "forward"
-- In most cases, the angle of the morphs has to be adjusted manually.

Example: To cut a vertical window (== rotated capital H): (aligned to Y-Axis; Rotate the instructions depending on the chosen "Up" Direction)
[1] Lasso-select the vertex path and note the vertices with [Selection Guide]
[2] Perform a cut with 25 (or 24 on the back) -- This is the 'bridge' of the "H"
--  -- This means starting this mode, then using options '2' and ('5' or '4')
[3] Select either head or tail of the line (including the newly added vertex) and add their direct neighbour on the left and right
[4] Perform a cut with 05 (04 on the back) -- 'Old' Morph opens upwards
[5] Repeat [3] for the other tail / head
[6] Perform a cut with 15 (14 on the back) -- 'Old' Morph opens downwards

Note: Unless there is an explicit need to keep them separate, Step [3] and [5] can be combined, as their morphs produce messy results most of the time and can be deleted, keeping only the initial 2 from Step [2].
	"""
	#: INPUT: File containing array of vertices
	text = "Enter a list of vertices to cut along (e.g. [17067,17876,17987]) or a path to a file containing one vertex per line"
	import json
	def checker(x):
		if os.path.exists(x.strip('"')): return True
		try:
			return type(json.loads(x)) == list
		except: return False
	vert_file = core.MY_GENERAL_INPUT_FUNC(checker, text)
	##** Read in file
	vert_arr = []
	if os.path.exists(vert_file):
		with open(vert_file.strip('"')) as f: vert_arr = list([int(x) for x in f])
	else: vert_arr = json.loads(vert_file)
	if DEBUG: print(">> Read-in: " + str(vert_arr) + "\n")
	
	#: INPUT: Material (makes it faster)
	name_mat = core.MY_GENERAL_INPUT_FUNC(lambda x: True, "Enter name for new morphs")
	
	#:: INPUT: Cut direction: UP==Y+,FRONT==Z+ >> from(Y-,Z-)to(Y+,Z+)
	msg = "0/1=X+ X-, 2/3=Y+ Y-. 4/5=Z+ Z- (left/right, up/down, back/front)"
	cut_dir_up = int(core.MY_GENERAL_INPUT_FUNC(lambda x: x.isdigit(), "Upwards Vector: "+msg))
	#:: COMPUTE: View direction: Left=(Z+, Z-, X+, X-), Right=(opposite)
	#:: >> assume View == [X+ >> X-] : def left(vCur,vComp): return vCur.pos[0] < vComp.pos[0] # If X is bigger, its left
	def test(s): return s.isdigit() & (s != cut_dir_up)
	cut_dir_forward = int(core.MY_GENERAL_INPUT_FUNC(test, "Forward Vector: 0/1=X+ X-, 2/3=Y+ Y-. 4/5=Z+ Z-"))
	vector_dict = {# Func is used to determine which direction is "left" of the cut: 
		## 'old': Up=0, Front=-1*sign, remaining is 1 \\ 'new': Front = sign
		## Along Y-Axis: vertically
		20: { 'func': lambda vCur, vComp: vCur.pos[2] < vComp.pos[2], 'old':[ 1, 0,-1], 'new':[ 1, 0, 1] }, ## front vector is X- -> X+ along Y+
		21: { 'func': lambda vCur, vComp: vCur.pos[2] > vComp.pos[2], 'old':[-1, 0, 1], 'new':[-1, 0,-1] }, ## front vector is X+ -> X- along Y+
		24: { 'func': lambda vCur, vComp: vCur.pos[0] < vComp.pos[0], 'old':[ 1, 0, 1], 'new':[-1, 0, 1] }, ## front vector is Z+ -> Z- along Y+
		25: { 'func': lambda vCur, vComp: vCur.pos[0] > vComp.pos[0], 'old':[-1, 0,-1], 'new':[ 1, 0,-1] }, ## front vector is Z- -> Z+ along Y+
		## Along X-Axis: horizontally
		4:  { 'func': lambda vCur, vComp: vCur.pos[1] < vComp.pos[1], 'old':[ 0, 1,-1], 'new':[ 0, 1, 1] }, ## front vector is Z- -> Z+ along X+
		5:  { 'func': lambda vCur, vComp: vCur.pos[1] > vComp.pos[1], 'old':[ 0, 1, 1], 'new':[ 0, 1,-1] }, ## front vector is Z+ -> Z- along X+
		14: { 'func': lambda vCur, vComp: vCur.pos[1] > vComp.pos[1], 'old':[ 0, 1,-1], 'new':[ 0, 1, 1] }, ## front vector is Z+ -> Z- along X-
		15: { 'func': lambda vCur, vComp: vCur.pos[1] < vComp.pos[1], 'old':[ 0, 1, 1], 'new':[ 0, 1,-1] }, ## front vector is Z- -> Z+ along X-
	}
	vector_dict[30] = vector_dict[21]
	vector_dict[31] = vector_dict[20]
	vector_dict[34] = vector_dict[25]
	vector_dict[35] = vector_dict[24]
	#print(vector_dict)
	vector = cut_dir_up * 10 + cut_dir_forward
	if not vector in vector_dict:
		print("[NI] This combination({} {}) is not implemented yet".format(cut_dir_up, cut_dir_forward))
		print("Currently supported are: " + str(list(vector_dict.keys())))
		return
	# print("{} < {}".format(vCur.pos, vComp.pos))
	vector = vector_dict[vector]
	left = vector['func']
	
	items_old = []
	items_new = []
	
	#** Collect all affected faces
	faces = {}
	for idx,face in enumerate(pmx.faces): ## , start='stop'
		tmp = [i for i in face if i in vert_arr]
		if len(tmp) == 0: continue
		if DEBUG: print("[{:4d}]: contains {}".format(idx, tmp))
		#faces[idx] = pmx.verts[tmp[0]] --> Only saves the 'to be replaced' vertices
		#** If selecting a line, only two vertices will ever be affected, so always an free one.
		faces[idx] = pmx.verts[ [i for i in face if i not in vert_arr][0]   ]
	if DEBUG: print("Affected Faces: " + str(list(faces)))
	
	#for each vertex # assume View == [X+ -> X-]
	offset = len(pmx.verts)
	for vert_idx in vert_arr:
		if DEVDEBUG: print("----------------- \n --- " + str(vert_idx))
		vert = pmx.verts[vert_idx]
		#>	Copy into 2nd Vertex at the end // main reason why only in [solo.pmx]
		newIdx = len(pmx.verts)
		pmx.verts.append(copy.deepcopy(vert))
		newVert = pmx.verts[newIdx]
		## Add a little offset to prevent auto-merge
		newVert.pos[2] = newVert.pos[2] + 0.00001
		#>	>	move 2nd slighty towards cut vector ## here: increase Z
		#>	Put into VertexMorph "[matname]_[id]_old" and "[matname]_[id]_new"
		__append_vertexmorph(items_old, vert_idx, vector['old'], None)
		__append_vertexmorph(items_new, newIdx, vector['new'], None)
		#>	for each affected face
		
		for face_idx in faces:
		#>	>	get first vertex not in above list **-- above
		#>	>	if left(current, ^^): keep first **== 
		#>	>	elif right(current, ^^): replace current with 2nd
			if not left(vert, faces[face_idx]):
				face = pmx.faces[face_idx]
				if DEVDEBUG: txt = str(face)
				if face[0] == vert_idx: face[0] = newIdx
				if face[1] == vert_idx: face[1] = newIdx
				if face[2] == vert_idx: face[2] = newIdx
				pmx.faces[face_idx] = face
				if DEVDEBUG: print("[{}]: {} -> {}".format(face_idx, txt,str(face)))
			else:
				if DEVDEBUG: print("[{}]: Skipped".format(face_idx))
	print("Added vertices {} to {}".format(offset, len(pmx.verts)-1))
	oldName = "{}_{}_old".format(name_mat, vert_arr[0])
	pmx.morphs.append(pmxstruct.PmxMorph(oldName, oldName, 4, 1, items_old))
	newName = "{}_{}_new".format(name_mat, vert_arr[0])
	pmx.morphs.append(pmxstruct.PmxMorph(newName, newName, 4, 1, items_new))
	log_line = [f"Cut along '{vert_file}'",f"Added two morphs '{oldName}' and '{newName}'"]
	end(pmx, input_filename_pmx, "_cut", log_line)

##################
### Collectors ###
##################

def from_material_get_bones(pmx, mat_idx, returnIdx=False):
	"""
	Input: STDIN -> Ask for Material ID or name
	Action: mat -> faces -> vertices -> bones
	Output: STDOUT -> Unique list of used bones (Format: id, sorted)
	"""
	mat = pmx.materials[mat_idx]
	print("Printing " + mat.name_jp)

	### Find Faces
	start = 0
	if mat_idx != 0: ## calc start based of sum of (previous mat.faces_ct) + 1
		for tmp in range(0, mat_idx):
			start = start + pmx.materials[tmp].faces_ct
	
	stop = start + mat.faces_ct
	faces = pmx.faces[start:stop]
	
	### Collect Vertex
	vert_idx = list(set(core.flatten(faces))) ## Insert into set already discards dupe
	vert_idx.sort()
	
	arr = []
	
	for idx in vert_idx:
		vert = pmx.verts[idx]
		if vert.weighttype == 0:
			arr.append(vert.weight[0])
		elif vert.weighttype == 1:
			arr.append([vert.weight[0], vert.weight[1]])
		elif vert.weighttype == 2:
			arr.append([vert.weight[0], vert.weight[1], vert.weight[2], vert.weight[3]])
		else:
			raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))
	
	bone_idx = list(set(core.flatten(arr))) ## Insert into set already discards dupe
	bone_idx.sort()
	if returnIdx: return bone_idx
	return [pmx.bones[bone] for bone in bone_idx]

def from_material_get_faces(pmx, mat_idx, returnIdx=False):
	start = 0
	if mat_idx != 0: ## calc start based of sum of (previous mat.faces_ct) + 1
		for tmp in range(0, mat_idx):
			start = start + pmx.materials[tmp].faces_ct
	stop = start + pmx.materials[mat_idx].faces_ct
	if returnIdx: return range(start, stop)
	return pmx.faces[start:stop]

def from_faces_get_vertices(pmx, faces, returnIdx=True, moreinfo=False):
	if (moreinfo or DEVDEBUG):
		print("First Face has: {} \n Last Face has: {}".format(str(faces[0]),str(faces[1])))
	vert_idx = list(set(core.flatten(faces)))
	vert_idx.sort()
	if returnIdx: return vert_idx
	verts = []
	for vert in vert_idx: verts.append(pmx.verts[vert])
	return verts

def from_vertices_get_bones(pmx, vert_arr, returnIdx=False):
	arr = []
	
	for idx in vert_arr:
		vert = pmx.verts[idx]
		if vert.weighttype == 0:
			arr.append(vert.weight[0])
		elif vert.weighttype == 1:
			arr.append([vert.weight[0], vert.weight[1]])
		elif vert.weighttype == 2:
			arr.append([vert.weight[0], vert.weight[1], vert.weight[2], vert.weight[3]])
		else:
			raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))
	
	bone_idx = list(set(core.flatten(arr))) ## Insert into set already discards dupe
	bone_idx.sort()
	if returnIdx: return bone_idx
	return [pmx.bones[bone] for bone in bone_idx]

def from_vertices_get_faces(pmx, vert_arr, mat_idx=-1, returnIdx=False, debug=None, trace=False, point=False):
	"""
	IN: list[int] -> indices of verts to find faces for
	@param {vert_arr} (list[int]) indices of verts to find faces for
	@param {mat_idx} Restrict the retrieved faces to only the given material.
	                 Set negative for all faces.
	@param {debug} override DEBUG
	@param {trace} default False to use Cut mode (vert_arr = line);
	                     True to use trace mode (vert_arr = polygon)
	                     Overrides point
	@param {point} default False: True to return each face as list[pmx.Vertex]
	OUT:[idx=True]  list -> [ face_idx containing at least one affected vertex]
	OUT:[idx=False]
	      [Cut]:    dict -> { face_idx: [ first not affected ] } // to calc direction, len = 1
	      [Trace]:  dict -> { face_idx: [ face verts not in in vert_arr ] } // len may be 0,1,2\\3
	      [Point]:  dict -> { face_idx: [ PmxVertex for each vertex of face_idx ] } // len = 3
	"""
	if debug is None: debug = DEBUG
	## 'dict' to keep the original indices
	faces = {}
	if debug:
		if len(vert_arr) > 10:
			print("Affected Vertices: {}...{} (total: {})".format(vert_arr[:5], vert_arr[-5:], len(vert_arr)))
		else: print("Affected Vertices: " + str(vert_arr))
	#else: print("Affected Vertices(Len): " + str(len(vert_arr)))
	if mat_idx < 0: area = enumerate(pmx.faces)
	else:
		area = from_material_get_faces(pmx, mat_idx, returnIdx=True)
		area = list(enumerate(pmx.faces))[slice(area[0], area[-1])]
	
	for idx, face in area:
		## Check if there is an overlap between [face] and [vert_arr]
		tmp = [i for i in face if i in vert_arr]
		if len(tmp) == 0: continue
		#print(pmx.faces[idx])
		if debug and DEVDEBUG: print("[{:4d}]: contains {}".format(idx, tmp))
		#faces[idx] = pmx.verts[tmp[0]] --> Only saves the 'to be replaced' vertices
		#** If cutting on a line, only two vertices will ever be affected, so always an free one.
		#** For overlap calc, there is always at least one affected, so there could be 2, 1, or 0 free ones.
		tmp = [i for i in face if i not in vert_arr]
		if    trace: faces[idx] = face#tmp
		elif  point: faces[idx] = [ pmx.verts[face[0]], pmx.verts[face[1]], pmx.verts[face[2]] ]
		else:        faces[idx] = pmx.verts[ tmp[0]   ]
		
	if debug:
		if len(faces) > 10:
			print("Affected Faces: {}...{} (total: {})".format(list(faces)[:5], list(faces)[-5:], len(faces)))
		else: print("Affected Faces: " + str(list(faces)))
	#else: print("Affected Faces(Len): " + str(len(faces)))
	if returnIdx: return list(faces)
	return faces

###############
### Riggers ###
###############

def move_weights_to_new_bone(pmx,input_filename_pmx): ## [08] @todo: change so that it just does all bones of a material (see print_material_bones)
	"""
Input(1): STDIN -> Material ID or name, default = cf_m_body <br/>
Input(2): STDIN -> Flag to create a root bone to attach all new bones to. <br/>
Loop Input: STDIN -> Bone ID to move weights away from <br/>

Output: PMX file '[filename]_changed.pmx'

Moves all bone weights of a given material to a copy of all affected bones.
The optional flag controls which parent the new bones use:
-- Yes / True --> Create a new bone to use as parent for all
-- No / False --> Set the original bone as parent of the new.
-- The parent itself will use ID:0 (root) as parent

Bones are reused if they already exist:
-- If used, the parent itself will be called '[mat.name_jp]_root'
-- With parent, new bones are called '[bone.name]_[mat.name_jp]'
-- Otherwise,   new bones are called '[bone.name]_new'

In terms of manual actions, this has a similar effect as:
-- Removing all other materials in a separate copy
-- Renaming all bones used by the chosen material
-- Re-Import into the current model to replace the old material
-- Setting parent bones correctly (with regards to [common parent])

Potential uses for this are:
-- Adding physics that only affect a material instead of multiple (which is common with KK-Models)
-- With a common parent, it can act as independent entity (similar to how it is in KK-Models)
-- -- Being detached from normal bones, they require own rigging since KK-Export only does it for skirts
-- -- This also allows utilizing the "outside parent" (OP) setting in MMD without the need of individual *.pmx files
-- -- which is usually required (but also more powerful) for things like throwing / falling of clothes
"""

	mat_idx = ask_for_material(pmx, returnIdx=True)
	mat_name = pmx.materials[mat_idx].name_jp
	common_parent = None
	if util.ask_yes_no("Create common parent"):
		common_parent = len(pmx.bones)
		common_name = mat_name + "_root"
		newBone = copy.deepcopy(pmx.bones[0])
		newBone.name_jp = common_name
		newBone.name_en = common_name
		newBone.has_translate = True
		newBone.parent_idx = 0
		pmx.bones.append(newBone)
	
	### Read in Bones to replace
	
	print("-- Select which bones to clone:")
	if util.ask_yes_no(f"> [y] to use all weighted bones of {mat_name}\n> [n] to input manually"):
		for bone_idx in from_material_get_bones(pmx, mat_idx, returnIdx=True):
			move_weights_to_new_bone__loop(pmx, mat_idx, bone_idx, common_parent)
	else:
		def __valid_check2(s): return s.isdigit()# | re.match("[\d, ]+",s)
		while True:
			target_idx = int(core.MY_GENERAL_INPUT_FUNC(__valid_check2, "Enter bone idx to replace: "))
			move_weights_to_new_bone__loop(pmx,mat_idx,target_idx,common_parent)
			if not util.ask_yes_no("Continue", "n"): break
	#---#
	log_line = f"Moved bone weights of {mat_idx}:{mat_name} (common_parent={common_parent})"
	end(pmx, input_filename_pmx, "_changed", log_line)

def move_weights_to_new_bone__loop(pmx,mat_idx,target_idx,parent):
	"""
	pmx        :: PMX
	mat_idx    :: The material to read the vertices from
	target_idx :: The bone to remove weighths from
	parent     :: Index of Parent Bone, or None to use target_idx instead
	----
	Effect: 
	:: [parent == None] creates [bone.name_jp + "_new"]       if missing
	:: [parent != None] creates [bone.name_jp + "_" + parent] if missing
	"""
	mat = pmx.materials[mat_idx]
	bone = pmx.bones[target_idx]
	core.MY_PRINT_FUNC("Replacing bone '{}' from '{}'".format(bone.name_jp,mat.name_jp))
	newName = bone.name_jp + ("_new" if parent is None else "_"+str(parent))
	if find_bone(pmx,newName,False) > -1:
		core.MY_PRINT_FUNC("Found existing bone '{}', using that.".format(newName))
		newIdx = find_bone(pmx,newName)
		newBone = pmx.bones[newIdx]
	else:
		newIdx = len(pmx.bones)
		### Add new bone
		newBone = copy.deepcopy(bone)
		newBone.name_jp = newName
		pmx.bones.append(newBone)
	
	newBone.parent_idx = target_idx if parent is None else parent
	newBone.name_en = translate_name(newBone.name_jp, newBone.name_en)
	newBone.has_translate = True
	
	### Find Faces
	start = 0
	if mat_idx != 0: ## calc start based of sum of (previous mat.faces_ct) + 1
		for tmp in range(0,mat_idx):
			start = start + pmx.materials[tmp].faces_ct
	
	stop = start + mat.faces_ct
	faces = pmx.faces[start:stop]
	
	### Collect Vertex
	vert_idx = list(set(core.flatten(faces))) ## Insert into set already discards dupe
	vert_idx.sort()
	
	for idx in vert_idx:
		vert = pmx.verts[idx]
		if vert.weighttype == 0:
			if(vert.weight[0] == target_idx): vert.weight[0] = newIdx
		elif vert.weighttype == 1:
			if(vert.weight[0] == target_idx): vert.weight[0] = newIdx
			if(vert.weight[1] == target_idx): vert.weight[1] = newIdx
		elif vert.weighttype == 2:
			if(vert.weight[0] == target_idx): vert.weight[0] = newIdx
			if(vert.weight[1] == target_idx): vert.weight[1] = newIdx
			if(vert.weight[2] == target_idx): vert.weight[2] = newIdx
			if(vert.weight[3] == target_idx): vert.weight[3] = newIdx
		else:
			raise NotImplementedError("weighttype '{}' not supported! ".format(vert.weighttype))

################
### Printers ###
################

def print_all_texture(pmx, input_filename_pmx): ### [02]
	myarr=[]
	myarr.append("...# of textures         ="+ str(len(pmx.textures))  )
	for tex in pmx.textures: myarr.append(str(tex))
	core.write_list_to_txtfile(input_filename_pmx+"_texture.txt", myarr)

def print_material_bones(pmx,_): ### [09] -- Print bones for material
	"""
	Input: STDIN -> Ask for Material ID or name <br/>
	Action: mat -> faces -> vertices -> bones <br/>
	Output: STDOUT -> Unique list of used bones (Format: id, sorted) <br/>
	"""
	def __valid_check(s): return True
	text = core.MY_GENERAL_INPUT_FUNC(__valid_check, "Enter material idx or name (empty for 'cf_m_body'")
	try:
		name = pmx.materials[text]
	except:
		if text == None or len(text) == 0: name = "cf_m_body"
		else: name = text
	mat_idx = find_mat(pmx,name) ## return if invalid
	
	bones = from_material_get_bones(pmx, mat_idx, returnIdx=True)
	print(str(bones))

###############
### Helpers ###
###############

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
				return '"' + pmxArr[idx] + '"'
			return '"' + pmxArr[idx].name_jp + '"'
		except: pass
	return default

def ask_for_material(pmx, extra = None, default = "cf_m_body", returnIdx = False):
	"""
	extra :: Append some text to the Input message
	default :: Name of texture to use if no input is provided.
	-- Will be ignored if not found in the model
	
	[return] :: An PmxMaterial instance
	"""
	_valid_def = find_mat(pmx, default, False) not in [-1, None]
	
	msg = "Enter material idx or name"
	if _valid_def: msg += f" (empty for '{default}')"
	if extra != None: msg += ' ' + extra
	def __valid_check(txt):
		if txt == None or len(txt) == 0: return _valid_def
		try: pmx.materials[txt]
		except:
			try: pmx.materials[find_mat(pmx, txt)]
			except:
				if DEVDEBUG: print("> ID or Name does not exist")
				return False
		return True
	text = core.MY_GENERAL_INPUT_FUNC(__valid_check, msg)
	if _valid_def and text in [None,""]: idx = find_mat(pmx, default)
	elif type(text) is str: idx = find_mat(pmx, text)
	else: idx = int(text)
	return idx if returnIdx else pmx.materials[idx]

def transfer_names():
	print("Input the source")
	input_filename_pmx = core.MY_FILEPROMPT_FUNC('.pmx')
	src = pmxlib.read_pmx(input_filename_pmx, moreinfo=True)
	print("Input the destination")
	input_filename_pmx = core.MY_FILEPROMPT_FUNC('.pmx')
	dst = pmxlib.read_pmx(input_filename_pmx, moreinfo=True)
	
	## small tabu list for not yet unique-fied materials
	names = []
	for mat in dst.materials:
		#print(f"Search for {mat.name_jp}...")
		idx = find_mat(src, mat.name_jp, False)
		#print(f"--> Idx: {idx}")
		while idx in names:
			idx = find_mat(src, mat.name_jp, False, idx+1)
			#print(f"--> Idx: {idx}")
		if idx == -1:
			print(f"Not found: {mat.name_jp}...")
			continue;
		dst.textures[mat.tex_idx] = src.textures[src.materials[idx].tex_idx]
		names.append(idx)
	return end(dst, input_filename_pmx, "_org")

def ask_to_rename_extra(pmx, base):
	if not os.path.exists(base):
		print(f"{base} does not exist")
		return
	
	re_cut = re.compile(r" ?\(Instance\)_?(\([-0-9]*\))?|_Export_[\d\-]+_")
	
	idx = -1
	names = []
	basepath = os.path.split(base)[0] + "\\"
	for idx, basename in enumerate(pmx.textures):
		fname = os.path.splitext(basename)[0]
		ftype = os.path.splitext(basename)[1]
		newname = re_cut.sub("", fname)
		
		suffix = 0
		if newname in names:
			while True:
				suffix += 1
				if ("{}+{}".format(newname, suffix)) not in names:
					newname = "{}+{}".format(newname, suffix)
					break
		elif basename == (newname+ftype): continue
		names.append(newname)
		dst = newname + ftype
		print(f"[{idx}] Rename '{basename}' to '{dst}'")
		pmx.textures[idx] = dst
		## Also rename the physical file
		fpath = ""
		if not os.path.isfile(basename):
			## if the file does not exist, its trash and can be ignored
			if not os.path.isfile(os.path.join(basepath,basename)): continue
			else: fpath = basepath
		try:
			os.renames(fpath+basename, fpath+dst)
		except:
			# Mixed case: Somehow an unrenamed texture made it into a clean model
			suffix = 0
			newname = re_cut.sub("", fname)
			tmp = ""
			while os.path.exists(fpath+dst):
				suffix += 1
				tmp = "{}+{}".format(newname, suffix)
				names.append(tmp)
				dst = tmp + ftype
			print(f"[!]--> Already exists. Renaming to {dst} instead")
			pmx.textures[idx] = dst
			os.renames(fpath+basename, fpath+dst)

def __do(pmx, input_filename_pmx): pass

def end(pmx, input_filename_pmx: str, suffix: str, log_line=None):
	"""
	Main Finalizer for Model changes.
	Will never overwrite any existing files (instead adds 1, 2, ...)
	If @suffix ends with a number, will add '_' inbetween.
	
	:param pmx                [PMX] : The context instance. Set none to only write a log_line.
	:param input_filename_pmx [str] : The working directory + PMX File name
	:param suffix             [str] : Infix to insert for unique-fication
	:param log_line           [str] : (default: None) If not None, will be appended to [editlog.log]
	"""
	# write out
	has_model = pmx is not None
	if DEVDEBUG and (pmx is None and log_line is None): print("[!] Called end() without doing anything!")
	print("----------------")
	suffix = "" if suffix is None else str(suffix)
	output_filename_pmx = input_filename_pmx[0:-4] + suffix + ".pmx"
	if suffix and util.is_number(suffix[-1]) and os.path.exists(output_filename_pmx):
		arr = [output_filename_pmx[0:-4] + "_.pmx"]
		output_filename_pmx = core.get_unused_file_name(arr[0], arr)
	else: output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	if log_line:
		paths = os.path.split(output_filename_pmx)
		path = os.path.join(paths[0], "editlog.log")
		if os.path.exists(path): os.path.rename(path, os.path.join(paths[0], "#editlog.log"))
		path = os.path.join(paths[0], "#editlog.log")
		if type(log_line) is str: log_line = [ log_line ]
		msg = "\n---- ".join([""] + log_line)
		## Add name of target file that contains the change 
		if has_model:
			with open(path, "a") as f: f.write(f"\n--[{util.now()}][{paths[1][0:-4]}]{msg}")
		else:
			with open(path, "a") as f: f.write(f"\n--[{util.now()}]{msg}")
	if has_model:
		pmxlib.write_pmx(output_filename_pmx, pmx, moreinfo=True)
		return output_filename_pmx
	return None

if __name__ == '__main__':
	print("Cazoo - 2022-02-10 - v.1.5.2")
	if DEBUG or DEVDEBUG:
		main()
		core.pause_and_quit("Done with everything! Goodbye!")
	else:
		try:
			main()
			core.pause_and_quit("Done with everything! Goodbye!")
		except (KeyboardInterrupt, SystemExit):
			# this is normal and expected, do nothing and die normally
			pass
		except Exception as ee:
			# if an unexpected error occurs, catch it and print it and call pause_and_quit so the window stays open for a bit
			print(ee)
			core.pause_and_quit("ERROR: something truly strange and unexpected has occurred, sorry!")
