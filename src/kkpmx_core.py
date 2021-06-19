# Cazoo - 2021-06-12
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
from typing import List
import re
import os
import copy
from datetime import datetime ### used in [end]

import kkpmx_property_parser as PropParser ## parseMatComments
import kkpmx_utils as util
from kkpmx_handle_overhang import run as runOverhang
from kkpmx_json_generator import GenerateJsonFile
try:
	import nuthouse01_core as core
	import nuthouse01_pmx_parser as pmxlib
	import nuthouse01_pmx_struct as pmxstruct
	import _prune_unused_bones as bonelib
	#import _translate_to_english
	import _translation_tools as tlTools
	import morph_scale
	from kkpmx_csv import csv__from_bones, csv__from_mat, csv__from_vertex, export_material_surface
	import _prune_invalid_faces as facelib ### delete_faces()
except ImportError as eee:
	print(eee.__class__.__name__, eee)
	print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
	print("...press ENTER to exit...")
	input()
	exit()
	core = pmxlib = pmxstruct = morph_scale = bonelib = None

## Global "moreinfo"
DEBUG = False
## Certain things which are only useful when developing
DEVDEBUG = False
insert_bone = bonelib.insert_single_bone

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
	elif idx == 6: return
	else: print_help(idx)
	# prompt PMX name
	core.MY_PRINT_FUNC(">> The script can be terminated at any point by pressing Ctrl+C")
	core.MY_PRINT_FUNC("Please enter name of PMX input file:")
	input_filename_pmx = core.MY_FILEPROMPT_FUNC('.pmx')
	
	pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=moreinfo)
	choices[idx][1](pmx, input_filename_pmx)
	core.MY_PRINT_FUNC("Done!")
	return None

###################
### Main Method ###
###################

def cleanup_texture(pmx, input_filename_pmx, write_model=True): ### [01]
	"""
This is one of two main methods to make KK-Models look better.
It does the following things:

- disable "Bonelyfans", "Standard"
- Simplify material names (removes "(Instance)" etc)
- if tex_idx != -1: Set diffRGB to [1,1,1] ++ add previous to comment
- else:             Set specRGB to [diffRGB] ++ add previous to comment
- Set toon_idx = "toon02.bmp"
- Rename certain bones to match standard MMD better
- Remove items with idx == -1 from dispframes

In some cases, this is already enough to make a model look good for simple animations.

Output: PMX File '[filename]_cleaned.pmx'
"""
	###### ---- materials
	def disable_mat(name_mat):
		mat_idx = name_mat
		if type(name_mat) == str:
			mat_idx = find_mat(pmx, name_mat, False)
			if mat_idx == None: return
		pmx.materials[mat_idx].alpha = 0
		pmx.materials[mat_idx].edgesize = 0
		pmx.materials[mat_idx].flaglist[4] = False
	disable_mat("Bonelyfans (Instance)")
	disable_mat("Bonelyfans")
	disable_mat("Bonelyfans*1")
	disable_mat("Standard (Instance) (Instance)") ## Exists with kedama (?)
	#disable_mat("acs_m_kedama (Instance) (Instance)")
	
	kk_re = re.compile(r" ?\(Instance\)_?(\([-0-9]*\))?")
	for mat in pmx.materials:
		mat.name_jp = kk_re.sub("", mat.name_jp)
		mat.name_en = kk_re.sub("", mat.name_en)
		
		### KK Materials with own texture rarely use the diffuse color
		### So replace it with [1,1,1] to make it fully visible
		if (mat.tex_idx != -1):
			if mat.diffRGB != [1,1,1]:
				mat.comment = mat.comment + "\n[Old Diffuse]: " + str(mat.diffRGB)
				mat.diffRGB = [1,1,1]
		elif mat.diffRGB != [1,1,1]:
			## Otherwise replicate it into specular to avoid white reflection
			if mat.specRGB != [1,1,1] and mat.specRGB != [0,0,0]:
				mat.comment = mat.comment + "\n[Old Specular]: " + str(mat.specRGB)
			mat.specRGB = mat.diffRGB
		else:
			if mat.specRGB != [1,1,1]:
				mat.comment = mat.comment + "\n[Old Specular]: " + str(mat.specRGB)
			mat.specRGB = [0,0,0]
		
		mat.toon_mode = 1
		mat.toon_idx  = 1 ## toon02.bmp
	#-------
	## Make sure that all materials have unique names
	names = []
	for (idx, name) in enumerate([m.name_jp for m in pmx.materials]):
		suffix = 0
		mat = pmx.materials[idx]
		if name.startswith("Bonelyfans"): disable_mat(idx)
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
	
	###### ---- bones
	def rename_bone(org, newJP, newEN):
		tmp = find_bone(pmx, org, False)
		if tmp is not None:
			pmx.bones[tmp].name_jp = newJP
			pmx.bones[tmp].name_en = newEN
	## rename Eyes: [両目x] to [両目], [左目x] to [左目], [右目x] to [右目]
	rename_bone("両目x", "両目", "both eyes")
	rename_bone("左目x", "左目", "eye L")
	rename_bone("右目x", "右目", "eye R")
	
	## add [グルーブ][groove] at [Y +0.2] between [center] and [BodyTop] :: Add [MVN], [no VIS] head optional
	## add [腰][waist] at ??? between [upper]/[lower] and [cf_j_hips]
	
	###### ---- dispframes
	## add [BodyTop], [両目], [eye_R, eye_L], [breast parent] [cf_j_hips] to new:[TrackAnchors]
	frames = [
		[0, find_bone(pmx,"両目", False)], [0, find_bone(pmx,"左目", False)],
		[0, find_bone(pmx,"右目", False)], [0, find_bone(pmx, "breast parent", False)],
		[0, find_bone(pmx, "cf_j_hips", False)], [0, find_bone(pmx,"BodyTop", False)],
	]
	pmx.frames.append(pmxstruct.PmxFrame("TrackAnchors", "TrackAnchors", False, frames))
	## add [groove] to [center]
	## add [waist] to [lower body]
	
	### Clean up invalid dispframes
	for disp in pmx.frames:
		disp.items = list(filter(lambda x: x[1] not in [-1,None], disp.items))
	
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
	moreinfo = util.ask_yes_no("Display more details in some cases")
	## rename input_filename_pmx to "_org"
	orgPath = input_filename_pmx[0:-4] + "_org.pmx"
	if os.path.exists(orgPath):
		section("[-1] Restore to original state")
		if util.ask_yes_no("Found a backup, should the model be reset to its original state"):
			util.copy_file(orgPath, input_filename_pmx)
			pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=False)
	else:
		end(None, input_filename_pmx, "_org", "Created Backup file")
		util.copy_file(input_filename_pmx, orgPath)
	#-------------#
	section("[0] Bare minimum cleanup")
	## run cleanup_texture --- [0] because it renames the materials as well
	path = cleanup_texture(pmx, input_filename_pmx, write_model)
	if write_model: util.copy_file(path, input_filename_pmx)
	#-------------#
	section("[1] Plugin File")
	## ask for parser file
	if util.ask_yes_no("Using data generated by associated JSONGenerator Plugin of KK"):
		if GenerateJsonFile(pmx, input_filename_pmx):
			## run parseMatComments
			#>> <<< ask for base path
			path = PropParser.parseMatComments(pmx, input_filename_pmx, write_model)
			if write_model and path != input_filename_pmx: util.copy_file(path, input_filename_pmx)
	#-------------#
	section("[2] Sort Textures (will make a backup of all files)")
	## run [core] sort textures (which edits in place) --- [2nd] to also sort the property files
	import file_sort_textures
	if not write_model: core.write_pmx(input_filename_pmx, pmx, moreinfo=moreinfo)
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
	section("[3] Cleanup & Morphs")	
	## ask to run make_material_morphs --- [3rd] to make use of untranslated names for sorting
	if util.ask_yes_no("Generate Material Morphs", "y"):
		## -- run make_material_morphs
		path = make_material_morphs(pmx, input_filename_pmx, write_model, moreinfo=moreinfo)
		if write_model: util.copy_file(path, input_filename_pmx)
	#-------------#
	section("[4] General Cleanup")
	
	## run [core] general cleanup
	import model_overall_cleanup
	model_overall_cleanup.__main(pmx, input_filename_pmx, moreinfo)
	path = input_filename_pmx[0:-4] + "_better.pmx"
	util.copy_file(path, input_filename_pmx)
	#if not write_model: delete the "_better" file (?)
	
	#-------------#
	section("[5] Fixing material bleed-through")
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
		arrZeroA, arrZeroA, arrZeroA ## Keep Texture
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
jpMats = ['[上下]半身','白目','眼','耳','頭','顔','体','舌','瞳','まぶた','口内','ハイライト']
# 眼(Eyes), 白目(sirome), 瞳(hitomi), まぶた(eyelids), ハイライト(Highlights)
# 顔(Face), 口内(Inside of Mouth), 舌(Tongue), 耳(Ears)
# 頭(Head), 体(Body), [上下]半身(upper / lower body), 肌(Skin), 首(Neck)
jpMats += ['肌', '首', '脚', '手', '歯', '目']
# 脚(Leg)  手(Hand)  歯(Teeth)  目(eye)


jpHair = ['髪', 'もみあげ','まつ毛','まゆ毛','サイドテール','横髪','あほ毛','前髪','後ろ髪','睫毛']
# もみあげ(Sideburns), 前髪(Forelock), 後ろ髪(Back Hair)
jpAccs = ['グローブ','チョーカー','ブーツ','帽子','頭リボン','ニーハイ', 'ソックス','靴','アクセサリー']
# ソックス(Socks), 靴(Shoes), アクセサリー(Accessories)
#>> 表情(Expression)
#>> パーカー(Parker), スカート(Skirt), パンツ(Pantsu)
#### EN originals
enMats =  ['Head','Face','Teeth','Eyes?','Tng','Tongue','Lash','Ears?','Hair','Horns?','Neck']
enMats += ['Skin','Chest','Tummy','Foot','Feet','Body','Tail','breasts?']
enAccs = ['Accessories','Bracelet','Crown','Armband','Scrunchie','Headband','Flowers']
#### KK-Models
## All core mats
baseMats = ['body', 'mm', 'face', 'hair', 'noseline', 'tooth', 'eyeline', 'mayuge', 'sirome', 'hitomi', 'tang']
## Aux parts that should always stay
accMats = ['hair','ahoge','tail','acs_m_mimi_','kedama'] ## Hair & Kemomimi
hairAcc = ['mat_body','kamidome'] ## Common hair accs
## Additional parts that are not main clothing
accOnlyMats = ['socks','shoes','gloves','miku_headset','hood']
accOnlyMats += ['^acs_m_', '^cf_m_acs_']
####--- 
rgxBase = 'cf_m_(' + '|'.join(baseMats) + ')'
rgxBase += '|' + '|'.join(accMats)
rgxBase += '|\\b(' + '|'.join(jpMats + jpHair) + ')'
rgxBase += '|' + '|'.join(enMats)

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
slotAlways = slot_dict["hair"] + slot_dict["face"] + ["ct_hairB", "ct_hairF", "ct_hairS"]
slotMostly = slot_dict["hand"] + slot_dict["foot"] + ["ct_gloves", "ct_socks", "ct_shoes_outer", "ct_shoes_inner"]
slotMed    = slot_dict["body"] + slot_dict["nether"]
slotFull   = slot_dict["lower"] + slot_dict["upper"]

def make_material_morphs(pmx, input_filename_pmx, write_model=True, moreinfo=False): ## [02]
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

Output: PMX file '[modelname]_morphs.pmx'
"""
	moreinfo = moreinfo or DEBUG
	itemsCloth = []
	itemsAcc = []
	itemsSlots = { "always": [], "mostly": [], "med": [], "full": [], "slotMatch": False }
	flag = util.ask_yes_no("Emit morphs for body-like materials", "n")
	for idx, mat in enumerate(pmx.materials):
		### Filter out what we do not want
		if re.search(rgxSkip, mat.name_jp): continue
		name_both = f"'{mat.name_jp}'  '{mat.name_jp}'"
		isBody = re.search(rgxBase, name_both, re.I)
		
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
		pmx.morphs.append(pmxstruct.PmxMorph(name_jp, name_en, 4, 8, items))
		### Check if comments contain Slot names (added by Plugin Parser)
		if re.search(r'\[:Slot:\]', mat.comment):
			itemsSlots["slotMatch"] = True
			m = re.search(r'\[:Slot:\] (\w+)', mat.comment)[1]
			if m in slotAlways : __append_itemmorph_add(itemsSlots["always"], idx)
			if m in slotMostly : __append_itemmorph_add(itemsSlots["mostly"], idx)
			if m in slotMed    : __append_itemmorph_add(itemsSlots["med"]   , idx)
			if m in slotFull   : __append_itemmorph_add(itemsSlots["full"]  , idx)
		elif moreinfo: print(f"{mat.name_jp} did not match any slot")
		## Sort into Body, Accessories, Cloth
		if isBody: continue
		if re.search(rgxAcc, name_both, re.I): __append_itemmorph_mul(itemsAcc, idx)
		else: __append_itemmorph_mul(itemsCloth, idx)
		
	do_ver3_check(pmx)
	#### Add extra morphs
	items = []
	__append_bonemorph(pmx, find_bone(pmx,"全ての親",False), [0,-3,0], [0,0,0], "Move Model downwards")
	__append_bonemorph(pmx, find_bone(pmx,"センター",False), [0,-5,0], [0,0,0], "Move Body downwards")
	
	#### Add special morphs
	def addMatMorph(name, arr): pmx.morphs.append(pmxstruct.PmxMorph(name, name, 4, 8, arr))
	if itemsSlots.get("slotMatch", False):
		addMatMorph("Show:Head Acc",   itemsSlots["always"])
		addMatMorph("Show:Hand/Foot",  itemsSlots["mostly"])
		addMatMorph("Show:Neck/Groin", itemsSlots["med"]   )
		addMatMorph("Show:Body Acc",   itemsSlots["full"]  )
	addMatMorph("Hide Acc", itemsAcc)
	addMatMorph("Hide Non-Acc", itemsCloth)
	itemsBoth = list(filter(lambda x: x != None, core.flatten([ itemsCloth, itemsAcc ])))
	addMatMorph("BD-Suit", itemsBoth)
	log_line = "Added Material Morphs"
	if not flag: log_line += " (without body-like morphs)"
	return end(pmx if write_model else None, input_filename_pmx, "_morphs", log_line)

def do_ver3_check(pmx):
	"""
	Checks for the existence of the naming scheme from a very specific group of models
	"""
	if find_mat(pmx, "【M2】上半身", False) is None: return
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
		if find_mat(pmx, "【M1】") is not None:
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
		#** For overlap calc, there is always at least one affected, so there could be 2,1, or 0 free ones.
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
-- If used, the parent itself will be called '[mat.name_jp]_root' // @verify
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
	if find_bone(pmx,newName,False) != None:
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

def find_bone(pmx,name,e=True):  return morph_scale.get_idx_in_pmxsublist(name, pmx.bones,e)
def find_mat(pmx,name,e=True):   return morph_scale.get_idx_in_pmxsublist(name, pmx.materials,e)
def find_disp(pmx,name,e=True):  return morph_scale.get_idx_in_pmxsublist(name, pmx.frames,e)
def find_morph(pmx,name,e=True): return morph_scale.get_idx_in_pmxsublist(name, pmx.morphs,e)

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

def __do(pmx, input_filename_pmx): pass

def end(pmx, input_filename_pmx: str, suffix: str, log_line=None):
	"""
	Main Finalizer for Model changes.
	Will never overwrite any existing files (instead adds _1, _2, ...)
	
	@param pmx      [PMX] The context instance. Set none to only write a log_line.
	@param input_filename_pmx [str] The working directory + PMX File name
	@param suffix   [str] Infix to insert for unique-fication
	@param log_line [Optional(str)] If not None, will be appended to [editlog.log]
	"""
	# write out
	has_model = pmx is not None
	print("----------------")
	output_filename_pmx = input_filename_pmx[0:-4] + suffix + ".pmx"
	output_filename_pmx = core.get_unused_file_name(output_filename_pmx)
	if log_line:
		paths = os.path.split(output_filename_pmx)
		path = os.path.join(paths[0], "editlog.log")
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
	print("Cazoo - 2021-06-16 - v.1.O.1")
	if DEBUG:
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
