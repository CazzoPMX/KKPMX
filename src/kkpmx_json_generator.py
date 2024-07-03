# Cazoo - 2021-05-08
# This code is free to use, but I cannot be held responsible for damages that it may or may not cause.
#####################
import json
import re
import os

import nuthouse01_core as core
import morph_scale
import kkpmx_utils as util
from copy import deepcopy
from kkpmx_utils import find_bone
DEBUG = util.DEBUG or False
DEVDEBUG = False
genFiles = False and DEBUG

###############

class Comment:
	def __init__(self, text="", end=False, idx=None, NL=None):
		self.text = text
		self.idx = idx
		self.end = end
		self.NL = NL
	def __str__(self):
		if self.NL: return ""
		if self.idx is not None:
			if len(self.text) == 0: return "// [{:0>2}]".format(self.idx)
			return "// [{:0>2}]: {}".format(self.idx, self.text)
		else: tmp = "// {} //" if self.end else "// {}"
		return tmp.format(self.text)

def _decoder(o, indent, lvl):
	if type(o).__name__ == 'Comment':
		return indent*lvl + str(o)
	elif type(o) == type(tuple()) and lvl == 1:
		### Main Level values: [1]=mat, [2]=object, [3]=Comment
		value = _decoder(o[1], indent, lvl+1)
		if len(o) == 3 and o[2]: ## @todo: Change so that it is behind the "{" unless empty
			if value.startswith('{'): value  = '{ ' + str(o[2]) + value.lstrip('{')
			else:                     value += ', ' + str(o[2])
		return '{}"{}": {},'.format(indent*lvl, o[0], value)
	elif type(o) == type(dict()):
		res = [ "{" ]
		### Calc whitespace between key & value
		inline = 0
		if lvl > 1:
			for k in iter(o): inline = max(len(k), inline)
		inline += 4 # for ("": )
		for kv in iter(o):
			# Write a comment into the object
			if "CMT_" in kv:
				key = "// "
				value = str(o[kv])
			# Write a recursive key-value entry
			else:
				key = "{0:<{align}}".format('"{}": '.format(kv), align=inline)
				value = _decoder(o[kv], indent, lvl+1)
				if type(value) == dict: key = '"{}": '.format(kv)
			res.append(indent*lvl + key + value + ",")
		res.append(indent*(lvl-1) + "}")
		return "\n".join(res)
	return json.dumps(o, ensure_ascii=False)

helptext = """
Parses the raw output from the [KKPMX] mod.
The result can be found in the same folder as [PmxExport] puts its models ("C:\koikatsu_model")
"""

#############
### Categories
ct_clothesTop  = "ct_clothesTop"
ct_top_parts_A = "ct_top_parts_A"
ct_top_parts_B = "ct_top_parts_B"
ct_top_parts_C = "ct_top_parts_C"
ct_clothesBot  = "ct_clothesBot"
ct_bra         = "ct_bra"
ct_shorts      = "ct_shorts"
ct_gloves      = "ct_gloves"
ct_panst       = "ct_panst"
ct_socks       = "ct_socks"
ct_shoes       = "ct_shoes"       # not real
ct_shoes_inner = "ct_shoes_inner"
ct_shoes_outer = "ct_shoes_outer"
ct_hairB       = "ct_hairB"       # Base or Back
ct_hairS       = "ct_hairS"       # Sides
ct_hairF       = "ct_hairF"       # Front
ct_hairO_01    = "ct_hairO_01"    # Extensions
ct_item        = "ct_item"        # not real
ct_body        = "p_cf_body_00"
ct_head        = "ct_head"
#############
##--## Raw JSON keys (Input)
raw_meta = "meta"
raw_name = "name"
raw_ren  = "render"
raw_mat  = "mats"
raw_eye  = "resetEyes"
raw_skip = "skipJSON"
raw_IsClot  = "chaClot" ## Slot contains respective Component
raw_IsHair  = "chaHair" ## Slot contains respective Component
raw_IsAccs  = "chaAccs" ## Slot contains respective Component
##--## Raw JSON keys (Output)
out_name    = "name"
out_opt     = "options"
out_optBase = "base"
out_optHair = "process_hair"
out_optSkip = "skipJSON"
out_temp    = "template"
out_inherit = "inherit"
##--## Options used for render_tree
ren_Enabled  = "enabled" ## Render is enabled:   "On", "Off" --> "True","False"
ren_Shadows  = "shadows" ## Can cast shadows:    "On", "Off", "Two Sided", "Shadows Only"
ren_Receive  = "receive" ## Can receive shadows: "On", "Off" --> "True","False"
ren_Parent   = "parent"  ## The Slot note (ca_slot & ct_)
ren_Render   = "render"  ## Original render name
ren_Slot     = "slot"
ren_Type     = "renType"
ren_Material = "mat"     ## Array of materials
ren_Target   = "target"  ## The converted / uniquefied material name (becomes render name and should match the PmxMaterial)
##--## Options used for json_mats
mat_MatId    = "matId"   ## 
mat_Special  = "special"

#### Structure
#inR:(key=BONE#RENID) enabled, shadows, receive, render=BONE, parent, mat: [ MAT+Instance#MATID ]
#inM:(key=MAT+Instance#MATID) offset, scale, token=MAT+Instance, matId=MATID, shader, textures=[...], <ATTR>, <TEX>
#outM:(key=MAT#MATID) available, textures, shader, <ATTR>, <TEX>, template
#outR:(key=MAT) meta = (enabled, receive, shadows, render=BONE, parent, slot), inherit=MAT#MATID

##--## Options for write_entity
opt_Name     = "name"      # Main argument
opt_Group    = "shader"    # Override token for shader
opt_texAvail = "available" # Override for available textures
opt_texUse   = "textures"  # Override for useable textures
opt_Comment  = "comment"   # Provide Comment
opt_Iter     = "suffix"    # Go forward when multiple are expected
opt_Optional = "optional"  # Ignore if missing
opt_Mode     = "mode"      # Used to differ which writer is running
#############
## State
mat_dict = { }
cloth_dict = {
	ct_clothesBot:0, ct_clothesTop:0, ct_shorts:0, ct_bra: 0,
	ct_gloves:0, ct_panst:0, ct_socks:0, ct_shoes:0
	}
KAGE_MATERIAL = "cf_m_eyeline_kage" ## Special exception, used as piggy back for Skincolor

renTag_isBody = "renTag_isBody"
renTag_idxOvr = "renTag_idxOvr" ## Index Override
local_state = { }
state_debug = "debug"
def verbose(): return False#local_state.get(state_debug, False)

#############
def GenerateJsonFile(pmx, input_filename_pmx):
	wdir = os.path.split(input_filename_pmx)[0]
	path = os.path.join(wdir, "#generateJSON.json")
	if os.path.exists(path):
		if util.is_auto(): return path
		elif not util.ask_yes_no("Found existing #generateJSON file. Regenerate?", "n"):
			return path

	local_state[renTag_isBody] = []
	local_state[renTag_idxOvr] = {}
	local_state[state_debug] = local_state.get(state_debug, not util.is_prod() and True)
	##### Generate Bone tree
	slots = []
	tree = {}
	generate_tree(pmx, tree, slots)
	## @todo: ask to make all material names unique (required anyway) ==> option
	
	#[X]: Populate Map with (pmx.materials).name_jp being unique
	#### dict --> { name: { name, idx } }
	#### dict --> { name: True or False }
	mat_filter = {}
	util.uniquefy_names(pmx)
	for (idx, mat) in enumerate(pmx.materials):
		name = mat.name_jp
		mat_filter[name] = mat_filter.get(name, 0) + 1
		matId = util.readFromCommentRaw(mat.comment, "[MatId]:")
		mat_dict[matId] = mat.name_jp
	def adjustNames(raw_json):
		for val in mat_dict.items():
			raw_json = re.sub(f"\".+?(#{val[0]})\"", f"\"{val[1]}#{val[0]}\"", raw_json)
		if genFiles: util.write_json(raw_json, "_gen\#raw_json");
		return raw_json
		
	##--- Verify Sanity check
	mat_filter = [f'- {k}: x{v}' for (k,v) in mat_filter.items() if v > 1]
	if len(mat_filter) > 0:
		print("[!] WARNING: Material List is not unique-fyied! Please ensure the list of materials has no duplicate names")
		print("\n".join(mat_filter))
		return
	##--- Write Header
	arr = [ ]
	arr.append(Comment("Generated with KKPMX v." + util.VERSION_TAG))
	arr.append(Comment("Colors are RGBA mapped to [0...1]; Alpha is added if missing"))
	arr.append(Comment("Explaination can be found in 'Customize.md' on github"))
	##	write Name
	namePos = len(arr)
	arr.append((out_name, "....")) ## in [json_ren]
	##	Write options: Maybe ask for each option ?
	opt = {
		"CMT_ENG1": "If this is true, the script will use the English names of materials to identify mappings.",
		"CMT_ENG2": "'true' is the default because PMXEditor shows usually only shows the JP names in the list, keeping the EN ones hidden.",
		"use_english": True,
		##to use script(cleanup script): default True ## << makes materials unique
		##to use script(add morphs):     default True
		out_optBase: "%PMX%/extra",##ask for base path ++ rename all "exported textures" in said folder
		out_optHair: True,
		"CMT_Skip1": "If this is true, the Texture-Generator will not try to rename PMX-Materials based on the order of the JSON-Slots.",
		"CMT_Skip2": "This will be set to true if the JSON-Parser found Names being shared between Accs and Clothes (e.g. some lazy Game-Model ports).",
		out_optSkip: False,
	}
	optPos = len(arr)
	arr.append((out_opt, opt))
	#print("--- << some nice message >>")
	jsonPath = None
	if (util.is_allYes()):
		for file in os.listdir(wdir):
			if file.endswith(".json"):
				if not "#generateJSON.json" in file:
					jsonPath = os.path.join(wdir, file)
					break
	json_ren = util.load_json_file(jsonPath, extra=adjustNames)
	if json_ren is None:
		print("--- No file has been generated")
		return False
	if raw_meta in json_ren:
		if raw_name in json_ren[raw_meta]:
			arr[namePos] = (out_name, json_ren[raw_meta][raw_name])
		if raw_eye in json_ren[raw_meta]:
			local_state[raw_eye] = json_ren[raw_meta][raw_eye] in ["True", "true"]
		if raw_skip in json_ren[raw_meta]:
			arr[optPos][1][out_optSkip] = json_ren[raw_meta][raw_skip] in ["True", "true"]
	##-- Parse all render entries into a slot independent order
	render_tree = generate_render_tree(pmx, tree, json_ren[raw_ren])
	##-- Parse all material entries and add renders that depend on them
	json_tree = generate_material_tree(pmx, tree, render_tree, json_ren[raw_mat])
	
	##-- Assign materials to their corresponding slots
	parent_tree = { "_blank": [] }
	prDEBUG("--- ParentTree")
	for (k,v) in json_tree.items():
		if DEBUG:
			prDEBUG(k, "   ")
			prDEBUG(k, "------- Start:" + str(k))
			prDEBUG(k, f"Key: {k} \\ Value: {v if type(v) is str else v['token']}")
		##-- Check if a material has at least one render that depends on it
		if ren_Render not in v:
			prDEBUG(k, f"(k,v) =\n> {k}\n> {v}")
			## Handle Copy-Material
			if type(v) is str: _parent = list(json_tree[v][ren_Render].values())[0].get(ren_Parent, "_blank")
			else: _parent = "_blank"
		else: _parent = list(v[ren_Render].values())[0].get(ren_Parent, "_blank")
		prDEBUG(k, f"------- End: {k} --- Parent={_parent}")
		parent_tree.setdefault(_parent, [])
		parent_tree[_parent].append(k)
	
	if DEBUG:
		tmp = parent_tree["_blank"]
		tmp = list(filter(lambda x: not x.startswith(KAGE_MATERIAL), tmp))
		if len(tmp) > 0:
			print("--- These materials contained no target and will be discarded")
			print(tmp)
	
	GenerateJsonFile__Body(pmx, arr, json_tree, parent_tree)
	GenerateJsonFile__Clothes(pmx, arr, json_tree, parent_tree)
	GenerateJsonFile__Accs(pmx, arr, json_tree, slots, parent_tree)
	
	####
	# In certain cases, especially when using Game-ported Models, Material names may be shared between Clothes and Accs.
	# The code that tries to repair the Name-order will get confused by that, so we disable that in such cases.
	if local_state.get(mat_Special, False):
		print(">> Found overlapping names in Clothes x Accs Groups -- Will disable Repair-Sort for PropParser")
		arr[optPos][1][out_optSkip] = True
	
	path = os.path.join(os.path.split(input_filename_pmx)[0], "#generateJSON.json")
	try:
		output = [ "{" ] + [_decoder(o, "\t", 1) for o in arr] + [ '}' ]
	except:
		with open(path+f"_{util.now()}", "a") as f: f.write(f"{arr}")
		raise
	try:
		core.write_list_to_txtfile(path, output, False)
	except RuntimeError:
		print(">>:: Switching to UTF-8, may break file paths...")
		core.write_list_to_txtfile(path, output, True)
	return path
GenerateJsonFile.__doc__ = helptext
########
def GenerateJsonFile__Body(pmx, arr, json_tree, parent_tree):
	local_state[opt_Mode] = "Body"
	local_state[local_state[opt_Mode]] = []
	print("==== Printing Body")
	arr2 = []
	##	write COMMENT_SKIN
	arr.append(Comment("== Skin ==", end=True))
	##	write "cf_m_body"
	
	#-- Get number of Body Bones -- Some assets directly attached to the body inherit its render name
	opt = {
			opt_Name: util.find_bodyname(pmx), opt_Group: "body",
			opt_texAvail: [t__Detail, t__Line, t__Main, t__NorMap, t__NorMapDet, t__overtex1], ## t__overtex2
			opt_texUse: [t__Detail, t__Line, t__Main, t__overtex1],
		}
	write_entity(pmx, arr, json_tree, opt) ## add option for [custom group], [Comment]
	
	##	write "cf_m_mm"
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_mm", opt_Group: "body",
		opt_texAvail: [t__Detail, t__Line, t__Main, t__NorMap, t__NorMapDet],
		opt_texUse: [t__Detail, t__Main], opt_Optional: True,
		})
	
	##	write "cf_m_face_00"
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_face_00", opt_Group: "face",
		opt_texAvail: [t__Detail, t__Line, t__Main, t__NorMap, t__NorMapDet, t__overtex1], ## t__overtex2, t__overtex3
		opt_texUse: [t__Detail, t__Line, t__Main, t__Alpha],
		})
	##	write WS
	arr.append(Comment(NL=True))

	##	write COMMENT_HEAD
	arr.append(Comment("== Head ==", end=True))
	##	>	cf_m_mayuge_00 -- Comment(": Type 3 (vertical short)")
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_mayuge_00", opt_Comment: Comment(idx="Eyebrows") })
	#arr.append(("cf_m_mayuge_00*1", "cf_m_mayuge_00")) ## @todo: Add option to produce merged if no textures
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_noseline_00", opt_Comment: Comment(idx="Nose") })
	
	##	>	cf_m_eyeline_00_up
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_eyeline_00_up", opt_Comment: Comment(idx="Upper Eye-line") } )
	##	>	cf_m_eyeline_kage
	#>> Kage is embedded in "eyeline up" and as such has no actual mesh. However, for unknown reasons it contains the skincolor (at least in KKS)
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_eyeline_kage", opt_Comment: Comment("Part of up, but we use it for getting the skincolor", idx="Part of Eyeline")})
	##	>	cf_m_eyeline_down
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_eyeline_down", opt_Comment: Comment(idx="Lower Eye-line")})
	##	>	cf_m_sirome_00
	#"cf_m_sirome_00": {}, // [Eye Whites]: Pattern 4
	##	>	cf_m_hitomi_00
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_hitomi_00",
		opt_Group: "eye",
		opt_texUse: [ t__Main, t__overtex1, t__overtex2 ],
		opt_Comment: Comment("offset+Scale (X,Y)", idx="Left Eye")
		})
	##	>	cf_m_hitomi_00*1 ---> inherit: "cf_m_hitomi_00", textures: [main_tex]
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_hitomi_00", opt_Iter: 1,
		opt_Group: "eye",
		opt_texUse: [ t__Main, t__overtex1, t__overtex2 ],
		opt_Comment: Comment("If Eyes look weird, use (0.0, -0.05) as offset", idx="Right Eye"),
		})
	##	>	cf_m_tang
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_tang|cf_m_tangchan",
		opt_texUse: [ t__Color, t__Detail, t__Main ],
		#// t__Another, t__Color, t__Detail, t__Line, t__Main, t__NorMap
		opt_Comment: Comment("Tongue may or may not be Gray or Cyan by default.", idx="Tongue")
		})
	#arr.append(Comment(NL=True))
	
	##	write COMMENT_HAIR
	def search_handler(cat):
		arr.append(Comment("", idx=cat_to_Title.get(cat,cat)))
		opt = { opt_Name: cat, opt_Group: "hair",
				opt_texAvail: [t__Alpha, t__Another, t__Color, t__Detail, t__HairGloss, t__Main, t__NorMap],
				opt_texUse: [t__Color, t__Detail, t__Alpha],
			}
		#print(f"Adding {len(parent_tree.get(cat, []))} for {cat}")
		for _name in parent_tree.get(cat, []):
			opt[opt_Name] = _name
			write_entity(pmx, arr, json_tree, opt)
	arr.append(Comment("== Hair ==", end=True))
	
	#arr.append(("meta__hair", {
	#	"Color":       [ 176, 126,  81 ], #// 0.6904762, 0.4949586, 0.3205782
	#	"Color2":      [ 160, 121, 117 ], #// 0.6285715, 0.4766880, 0.4624490
	#	"Color3":      [ 201, 206, 192 ], #// 0.7887006, 0.8095238, 0.7565193
	#	"LineColor":   [  74,  43,  34 ], #// 0.2904761, 0.2082239, 0.1348639
	#	"ShadowColor": [ 0.8304498, 0.8662278, 0.9411765 ],
	#	"template": True,
	#}, Comment("Use this with 'inherit: \"meta__hair\",' for shared hair colors")))
	##	>	MAIN :: ct_hair
	search_handler(ct_hairB)
	##	>	BANGS
	search_handler(ct_hairF)
	##	>	SIDES
	search_handler(ct_hairS)
	##	>	Extensions
	search_handler(ct_hairO_01)
	
	arr.append(Comment(NL=True))

def GenerateJsonFile__Clothes(pmx, arr, tree, parent_tree):
	local_state[opt_Mode] = "Clothes"
	local_state[local_state[opt_Mode]] = []
	print("==== Printing Clothes")
	def search_handler(cat):
		arr.append(Comment("", idx=cat_to_Title.get(cat,cat)))
		opt = {
				opt_Name: cat, # opt_Group: "cloth",
				## "#// t__Alpha, t__Another, t__Detail, t__Line, t__Main, t__NorMap",
				opt_texAvail: [t__Alpha, t__Another, t__Detail, t__Line, t__Main, t__NorMap],
				opt_texUse: [t__Detail, t__Main],
			}
		print(f"Adding {len(parent_tree.get(cat, []))} for {cat}")
		for _name in parent_tree.get(cat, []):
			opt[opt_Name] = _name
			write_entity(pmx, arr, tree, opt) ## add option for [custom group], [Comment]
	##	write COMMENT_CLOTHES
	arr.append(Comment("== Clothes ==", end=True))
	##	write COMMENT_TOP
	
	if ct_clothesTop in parent_tree:
		#arr.append(Comment("", idx="Top"))
		search_handler(ct_clothesTop)
	else: ## Only add if [ct_top_parts_A,B,C exists], else ct_clothesTop
		arr.append(Comment("Uniform (Blazer)", idx="Top"))
		#arr.append(Comment("Uniform (Blazer)", idx="Top"))
		##	>	descend [ct_top_parts_A]	 // [Inner Layer] Open collar and hem (half off)
		search_handler(ct_top_parts_A)
		##	>	descend [ct_top_parts_B]	 // [Outer Layer] Puffer Jacket Long
		search_handler(ct_top_parts_B)
		##	>	descend [ct_top_parts_C]	 // [Ornament] Loose ribbon 3
		search_handler(ct_top_parts_C)

	##	write COMMENT_BOTTOM
	#name = "<Skirt>";arr.append(Comment(name, idx="Bottom"))
	##	>	descend [ct_clothesBot] or [bottoms] >> [n_bot_a] usually has the stuff // exists multiple times
	search_handler(ct_clothesBot)

	##	write COMMENT_BRA
	#name = "<Bra>";arr.append(Comment(name, idx="Bra"))##>	descend [ct_bra] or [bra]
	search_handler(ct_bra)

	##	write COMMENT_SHORTS
	#name = "<Shorts>";arr.append(Comment(name, idx="Shorts"))##>	descend [ct_shorts] or [under],[shorts]
	search_handler(ct_shorts)

	##	write COMMENT_GLOVES
	#name = "<Gloves>";arr.append(Comment(name, idx="Gloves"))##>	descend [ct_gloves]
	search_handler(ct_gloves)

	##	write COMMENT_STOCKINGS
	#name = "<Thighs>";arr.append(Comment(name, idx="Thighs"))##>	descend [ct_panst]
	search_handler(ct_panst)

	##	write COMMENT_SOCKS
	#name = "<Socks>";arr.append(Comment(name, idx="Socks"))##>	descend [ct_socks]
	search_handler(ct_socks)

	##	write COMMENT_SHOES_INDOOR
	#name = "<Shoes (Indoor)>";arr.append(Comment(name, idx="Shoes (Indoors)"))
	##	>	descend [ct_shoes_inner]
	search_handler(ct_shoes_inner)

	##	write COMMENT_SHOES_OUTDOOR
	#name = "<Shoes (Outdoor)>";arr.append(Comment(name, idx="Shoes (Outdoors)"))
	search_handler(ct_shoes_outer)
	
	#####
	arr.append(Comment(NL=True))

def GenerateJsonFile__Accs(pmx, arr, tree, slots, parent_tree):
	local_state[opt_Mode] = "Accs"
	local_state[local_state[opt_Mode]] = []
	print("==== Printing Accessories")
	##	write COMMENT_ACCS
	arr.append(Comment("----------- Accs", end=False))
	for i in slots:
		slot = pmx.bones[i].name_jp
		idx = slot.lstrip("ca_slot")
		name = "-------------------"
		arr.append(Comment(name, idx="Slot "+str(idx)))
		_len = len(parent_tree.get(slot, []))
		print(f"== Adding {_len:2} for {slot}")
		### Looks like this: // [01]: ret_Name -- ret_RenderArr.length segments, ret_Parent
		## repeat for each render found
		opt = {
				opt_Name: slot, # opt_Group: "cloth",
				## "#// t__Alpha, t__Another, t__Detail, t__Line, t__Main, t__NorMap",
				opt_texAvail: [t__Alpha, t__Another, t__Detail, t__Line, t__Main, t__NorMap],
				opt_texUse: [t__Alpha, t__Color, t__Detail, t__Main],
			}
		for _name in parent_tree.get(slot, []):
			opt[opt_Name] = _name
			write_entity(pmx, arr, tree, opt) ## add option for [custom group], [Comment]


##############
cat_to_Title = {
	ct_head       : "Head",
	ct_clothesTop : "Top",
	ct_top_parts_A: "Top: Inner Layer",
	ct_top_parts_B: "Top: Outer Layer",
	ct_top_parts_C: "Top: Ornament",
	ct_clothesBot : "Bottom",
	ct_bra        : "Bra",
	ct_shorts     : "Underwear",
	ct_gloves     : "Gloves",
	ct_panst      : "Stockings",
	ct_socks      : "Socks",
	ct_shoes_inner: "Shoes (Indoor)",
	ct_shoes_outer: "Shoes (Outdoor)",
	#--- alias
	ct_body       : "Body",
	ct_hairB      : "Hair (Rear)",
	ct_hairF      : "Hair (Bangs)",
	ct_hairS      : "Hair (Side)",
	ct_hairO_01   : "Extensions",
	ct_item       : "Accessory",
	}


tabuKeys = { "keys": [] }
def write_entity(pmx, arr, json_tree, opt):
	"""
#	Search in [json_tree] for all entities named 'opt' (if str) or opt[opt_Name] (if dict)
#	-- then skip [opt.opt_Iter] entries and store the result in [elem]:
#	[[receive]]
#	"m_hood (Instance) (Instance)@ca_slot22": {
#		"offset": "(0.0, 0.0)",
#		"scale": "(1.0, 1.0)",
#		"token": "m_hood (Instance) (Instance)",
#		"shader": "Shader Forge/main_item",
#		<<attributes>> with '_' prefix
#		"render": {
#			"1210": {
#				"enabled": "True",			"mat": [ "m_hood (Instance) (Instance)@ca_slot22" ],
#				"parent": "ca_slot22",		"receive": "True",   "render": "hood_root",
#				"shadows": "On",			"target": "m_hood"
#	},	},	},
#	[[----]]
#	-- If a material is used by multiple renders, the additional ones are additional keys in "render"
#	-- If a render uses multiple materials (of the same name), the additional ones are added as
#	"NAME": "NAME to COPY",
#	[[----]]
	"""
	name   = opt
	isDict = type(opt) == dict
	if isDict: name = opt.get(opt_Name)
	else: opt = {}
	_verbose = verbose()
	
	#-- Support for multiple names of an entity
	isBody = local_state[opt_Mode] == "Body"
	if isBody:
		if "|" in name: nameFilter = name.split('|')
		else: nameFilter = [ name ]
	
	targetBase = {}
	#_filter = re.compile(name + r'(#-\d+|\*\d+)?$')
	#_filter = re.compile(name + r'(\*\d+)?(#-\d+)?$')
	if not isBody: _filter = re.compile(re.escape(name) + r'([#*]-?\d+)*$')
	else: _filter = re.compile('(' + '|'.join([re.escape(n) for n in nameFilter])  + ')' + r'([#*]-?\d+)*$')
	#_elem = filter(lambda kv: kv[0].startswith(name), json_tree.items())
	
	_elem = filter(lambda kv: _filter.match(kv[0]), json_tree.items())
	#for x in _elem: print(x[0])### Verifyer
	if not _elem:
		print("[!] Could not find any match for " + name)
		return
	try:
		elem = next(_elem)
	except StopIteration:
		if not opt.get(opt_Optional, False): print(f"[!] Model does not contain an entry for {name}")
		return
	suffix = opt.get(opt_Iter, 0)
	try:
		for x in range(suffix): elem = next(_elem)
	except StopIteration:
		print(f"State: {name}, {suffix}")
		return
	#prDEBUG("-------------------------------")
	prDEBUG(elem[0], f"> [{suffix}]: {reduceDictData(elem[1])}")
	if _verbose: print(elem[0], f"> [{suffix}]: {reduceDictData(elem[1])}")
	
	#---#
	token = re.sub(r"( \(Instance\))+", "", elem[0]) ## the full name that started with [name], without (instance)
	mat = elem[1]
	###-- Handle Copy-Material: mat will be string then -- Just add as is
	if type(mat) is str:
		arr.append((token, re.sub(r"\*\d+", "", token)))
		return
	
	
	### if using [meta.resetEyes], change it accordingly
	if local_state.get(raw_eye, False):
		if opt.get(opt_Group, "") == "eye":
			mat["offset"] = "(0.0, -0.05)"
	
	def appendMatch(_key, _name):
		if _key != _name: return False
		v = mat.get(_name, None)
		if not v: return True
		if _name == "shader":
			targetBase["shader"] = opt.get(opt_Group, re.sub("Shader ?Forge/|Koikano/","",v))
			return True
		## Use a different [default] for offset
		df = "(0.0, 0.0)" if _name == "offset" else "(1.0, 1.0)"
		## Only add to tree if [value != default]
		if v != df: targetBase[_name] = v
		return True
		
	###--- Generate Template (== the Material)
	targetBase["available"] = opt.get(opt_texAvail, []) ## Build some map of {"t__Main": ["main_item", ...]} and do a filter over all included
	targetBase["textures"] = opt.get(opt_texUse, [])
	##-- Only exists in KKS
	kks_tex = []
	if mat.get("textures", None):
		kks_tex = [x.lstrip('_') for x in mat["textures"]]
		targetBase["available"] = kks_tex
		targetBase["textures"]  = [x for x in targetBase["textures"] if x in kks_tex]
	
	
	###------
	for (k,v) in mat.items():
		if k in ["render","token","textures",mat_MatId,mat_Special]: continue
		## sync how its done in eye
		if appendMatch(k,"offset"): continue      # ignore if == (0.0, 0.0)
		if appendMatch(k,"scale"): continue       # ignore if == (1.0, 1.0)
		if appendMatch(k,"shader"): continue      # add as "group" (without "Shader Forge/")
		if k.startswith("_"): targetBase[k.lstrip("_")] = v
		else: print("[W] Unprocessed attribute " + k)
	if local_state[opt_Mode] == "Clothes":
		if targetBase[opt_Group] == "main_item" and t__Color in kks_tex:
			targetBase["textures"] += [t__Color]
	#-----
	##--- build object & add to [arr]
	
	## Get all Render elements that use this material
	render = mat.get("render",{})
	
	targetBase[out_temp] = len(render) > 0 ## Generate Warning about "template without render" (+ add special case for kage)
	if isBody:
		## Prevent unused Kage from raising a warning later on
		if token.startswith(KAGE_MATERIAL):
			token = re.sub(r"#-\d+","",token)
			targetBase[out_temp] = True
		## Some notes in case anything breaks
		if not targetBase[out_temp]:
			print(f"[W] Body Part {token} does not have any Render Entries!")
	
	#-- Add to list for weirdness detection
	local_state[local_state[opt_Mode]] += [re.sub(r"[*#\-]+\d+","",token)]
	
	##-- Fix the token if its special
	if mat.get(mat_Special, None):
		local_state[mat_Special] = True
		prDEBUG(elem[0], f"Special Token: {token}")
		##-- Retrieve the render name we have to reassociate
		r1 = mat[ren_Render]
		token2 = r1[list(r1.keys())[0]][ren_Target] ## Target is NAME*X
		renBet = r1[list(r1.keys())[0]][ren_Render]
		#tmp = re.sub(r"[*#\-]+\d+","",token) + '#' + str(mat[mat_MatId])
		##-- Copy the previous render that was responsible for this material
		elem = arr[-1] ## [Start with previous] in case we run through the whole thing, so that we don't end with nothing
		#::[Bugfix]: in rare cases, an asset with sub-materials could have subsequent renderers which messes with "refer to previous". Find the correct one
		for x in range(len(arr)-1, len(arr)-8, -1):
			_elem = arr[x]
			if type(_elem) != tuple:   continue ## Skip [Comment] entries
			if len(_elem) == 3:                 ## >>> arr.append((token, targetBase, opt.get(opt_Comment)))
				(_key, _value, XXX) = _elem
			else: (_key, _value) = _elem
			if type(_value) == str:    continue ## Skip [Inline inherit] entries
			if raw_meta not in _value: continue ## Skip [Texture] entries
			_tmp = _value[raw_meta].get(ren_Render, "<.>")
			#prDEBUG(elem[0], f">> [{_tmp}] vs. {renBet}")
			if _tmp != renBet:
				prDEBUG(elem[0], f">>->> [!] Skip possible mis-association of special material! ({token} to [{x}]={arr[x][0]} << {_tmp})")
				continue
			prDEBUG(elem[0], f">=> Found correct Meta-Entry [{x}]={arr[x][0]}!")
			elem = _elem
			break
		(key, value) = deepcopy(elem)
		if (value[raw_meta].get(ren_Render, "<.>") != renBet):
			print(f"[!] Possible wrong association of special material! ({token} to {key})")
		
		prDEBUG(f">> {key} -> {token} -- {value}") ### [Key of previous Value-Owner], [My Key, under which value is copied], [the meta/inherit to copy] 
		# prDEBUG(elem[0], f">> {key} -> {token} -- {value}")
		key = token ## Name is NAME*X
		arr.append((key, value)) ## Key is NAME*X, Inherit is NAME#matId
		########
		return## -- Avoid adding them again
	
	arr.append((token, targetBase, opt.get(opt_Comment)))

	### Generate the render entries that use that material
	for (k,r) in render.items(): ## mat
		key = r.get(ren_Target) ## Contains already *-suffix if any
		prDEBUG(key, f"--> Material Key is {key}")
		val = { }
		val[ren_Enabled] = r.get(ren_Enabled, "False") == "True"
		val[ren_Receive] = r.get(ren_Receive, "False") == "True"
		val[ren_Shadows] = r.get(ren_Shadows, "Off")
		val[ren_Render]  = r.get(ren_Render, "")
		IsAcc   = r.get(raw_IsAccs, "False") == "True"
		IsCloth = r.get(raw_IsClot, "False") == "True"
		IsHair  = r.get(raw_IsHair, "False") == "True"
		mt = util.MatTypes
		typeStr = \
			mt.HAIR if IsHair else \
			mt.CLOTH if IsCloth else \
			mt.ACCS if IsAcc else mt.ANY
		val[ren_Type] = typeStr.value
		
		parent = r.get(ren_Parent)
		if parent:
			val[ren_Parent] = parent
			if name.startswith("ct_"): # If this is a "ct_" slot, use the parent as is
				val[ren_Slot]   = parent
			else: # Otherwise use the grandparent (== N_move -> ca_slot > a_n_*)
				tmp = local_state[renTag_idxOvr].get(token, find_bone(pmx, parent)) ##[_f__IdxOvr]: Use Index Override if we declared one
				val[ren_Slot]   = pmx.bones[pmx.bones[tmp].parent_idx].name_jp
			###---
			# Body things will be in p_cf_body_00 under BodyTop
			# Head things will be in ct_head under p_cf_head_bone
			# Clothes will be in their respective slot under BodyTop, except top which further splits into extra parts A+B+C
			# Accessories are in their respective slot under a_n_*
			#### Add weird Body assets using "Armature" too
			if parent in local_state[renTag_isBody]: val[ren_Type] = mt.BODYACC.value
			if parent in ["ct_head", "p_cf_body_00", "p_cm_body_00"]: val[ren_Type] = mt.BODY.value
			if val[ren_Render] == "cf_O_face": val[ren_Type] = mt.FACE.value
		
		### add to arr
		#mat_comment = opt.get(opt_Comment) ## generate some based on data
		arr.append((key, { "meta": val, out_inherit: token }))
	

### Goal with Comment
# Show original slot (mapped with dict) ++ Name (mapped with dict ?)

##############
###

def collectSubTree(pmx, tree, _start, _forceEnd=False):
	"""
	IN  :: pmx \\ tree \\ idx in [tree] to start
	OUT :: dict of all children of [start]
	:: Format: { "bone.name_jp": bone_idx }
	"""
	subTree = {}
	local_state["pvRoot"] = local_state.get("pvRoot", find_bone(pmx, "cf_pv_root")) # Avoids repeated warnings if not found
	#def stPrint(txt): if doPrint: print(txt)
	def __treeWalker(idx):
		if idx == -1: return
		#subTree[pmx.bones[idx].name_jp] = idx
		name = pmx.bones[idx].name_jp
		target = idx
		#stPrint(f" >>[{idx}] Name: {name}")
		if name in subTree:
			## This usually appears when an asset is used multiple times (but only those which generate their render after the body)
			#-- Which causes the render bones to all be attached to the first such slot.
			#-- The C# plugin is not intelligent enough to split them up, so we do that in [Rigging] at a later point
			#-- - and simply skip them here to avoid it having the same bone as anyone else
			if DEBUG: print("[subTree] {} already exists (as {}, new {})!".format(name, subTree[name], idx))
			target = max(subTree[name], target)
		subTree[name] = target
		#stPrint(f"-- Iterate Tree {tree[idx]} --") #stPrint(f"--Start({i})--"); __treeWalker(i); stPrint(f"--End({i})--")
		for i in tree[idx]: __treeWalker(i)
	if _forceEnd: __treeWalker(find_bone(pmx, _start, True, local_state["pvRoot"])) # First sibling after Armature
	else: __treeWalker(find_bone(pmx, _start))
	return subTree

kk_re = re.compile(r"( \(Instance\))*(@\w+|#\-\d+)")
kk_skip = re.compile(r"bonelyfans|shadowcast|Highlight_(cf_O_face|o_body_a)_rend")
def uniquefy_material(mat: str, names: list):
	"""
	Uniquefy a name based on a list of provided names.
	Also removes 'Instance' & @slot / #id suffix before checking.
	Adds the element to [names] before returning.
	"""
	mat = kk_re.sub("", mat)
	suffix = 0
	if mat in names:
		while True:
			suffix += 1
			if ("{}*{}".format(mat, suffix)) not in names: break
		mat = "{}*{}".format(mat, suffix)
	names.append(mat)
	return mat

def generate_render_tree(pmx, tree, json_ren):
	"""
	:param [pmx]: PMX instance
	:param [tree]: Output from [generate_tree]
	:param [json_ren]: 'render' subTree from raw JSON -- { render name: render }
	
	Parse the render part of the generated plugin data
	-- Maps unique-fyied names to their respective bones
	-- Which also ensures that only useable render elements / materials remain
	
	Example entry: ```
	RENDER NAME: {
		enabled, shadows, receive,
		render: 'bone name',         << must exist in [tree]
		parent: 'ca_slot00'          << key for [renArr]
		mat: [ NAME of material(s) ] << read in [material tree]
	}
	```
	"""
	if genFiles: util.write_json(json_ren, "_gen\#1R00_json_ren", True)
	#::: Generates each Renderer with META + its Mat Tokens
	#DEBUG = True
	
	### Group by Parent
	renArr = {}
	if DEBUG: print(f"[json_ren]:")
	for key in json_ren.keys(): ## RENDER in { RENDER: BODY }
		r = json_ren[key]
		if DEBUG: print(f"-- {key}")
		renArr.setdefault(r[ren_Parent], [])
		renArr[r[ren_Parent]].append(key) ## --> "Parent": { RENDER: BODY, ...}, ...
		#if len(renArr[r[ren_Material]]) > 1:
		#	print("[] Warning: Render '{}' contains multiple materials!".format(key))
	if genFiles: util.write_json(renArr, "_gen\#1R01_renArr", True) ### Dict of { "parent": [ "render", ...] }
	## "ca_slot00": [ <All Render with "parent"="ca_slot00"> ], ....
	#::>>> Prints dict of slots with their Render Bones
	
	### Link to bone_idx
	#print("------------")
	#print(renArr)
	#print("------------")
	
	renToBone = {}
	
	#### Q/A: Why even searching for the bone_idx to begin with ?
	# An asset can potentially be used multiple times, which can cause vertices
	#   to target the wrong bones (which always belong to the first such material found).
	# So we want to find the correct anchor bone for every render
	#   in order to separate it from its name and sort it based on its bone index.
	# That way we can easily assume which vertices were supposed to belong to it
	#   and correctly assign them to the bones that actually belong to the material.
	# It also makes it easier to find the correct PmxMaterial, which is exported in bone order, too.
	# This also allows discarding unused renders or materials without anchor.
	bodyPar = util.find_bodypar(pmx)
	for (k,v) in renArr.items(): #// SLOT: { RENDER: BODY, .... }, ...
		if DEVDEBUG: print("==== " + k)
		#-- Catch some weird Body Assets using p_cf_body_00 -- Since we process slots in reverse order, the real body will be last
		doBackwards = k == bodyPar and len(local_state[renTag_isBody]) > 0
		cArr = collectSubTree(pmx, tree, k, doBackwards) #//--> dict{"name": idx}
		if DEVDEBUG: print(f"Subtree: {cArr}") #// All bones under this slot
		if cArr == {}: continue
		#print(f"[V]: {v}")
		
		storeIdx = False
		#-- Store Body Weirdness
		if bodyPar in cArr: local_state[renTag_isBody].append(k); storeIdx = True ##[_f__IdxOvr]: Announce override
		
		for c in v: #// [RENDER, RENDER, ....]
			cc = re.sub("@\w+$|#-?\d+$","", c) ## Cut away the meta suffix
			#print(f"[CC]: {cc}")
			#--> Relies on the fact that [RENDER - suffix == bone name]
			if cc in cArr.keys(): #// if RENDER in cArr
				i = cArr[cc] #// idx of Bone for RENDER
				if DEVDEBUG: print("{} << {}".format(i,cc)) #//== Render Bone
				if i not in renToBone:
					renToBone[i] = json_ren[c] #// idx: BODY
					if storeIdx: local_state[renTag_idxOvr][i] = cArr[k]
					continue
	#util.write_jsonX(renToBone, "#renToBone.json", indent="\t", sort_keys=True)
	if genFiles: util.write_jsonX(renToBone, "_gen\#1R02_renToBone.json", indent="\t", sort_keys=True)
	#if DEBUG: print(f"------------------")
	return json.loads(json.dumps(renToBone, sort_keys=True))
#
#	renToBone :: for each render that exists in EXPORT, we have its bone_idx and RENDER.BODY
#
def generate_material_tree(pmx, tree, render_tree: dict, json_mats: dict):
	"""
	:param [tree]: unused
	:param [render_tree] dict -- { bone_idx: render }
	:param [json_mats]   dict -- { mat name: material }
	
	@return [json_mats] which now contains these fields
	-- All fields used by [generated.Material]
	-- Field 'render' which contains a copy of the corresponding item in [render_tree]
	-- Said [render_tree] item having [generated.Render.Name] in 'target'
	"""
	if genFiles: util.write_json(json_mats, "_gen\#2M00_json_mats", True)
	
	#print("------ render_tree")
	#util.__typePrinter_Dict(render_tree)
	#print("------ json_mats")
	#util.__typePrinter_Dict(json_mats)
	#print("------ ----")
	
#	### Create unique material names for all render elements
	uniqueMats = []
	prDEBUG(f"RenderTree:")
	tabuMats = []
	
	idxOvr = [x[0] for x in local_state[renTag_idxOvr].items()]
	
	## Collect Materials based on InstanceID (so that only those who exist in both JSON and PMX are picked)
	matIdDict = {}
	for mat in pmx.materials:
		m = util.readFromCommentRaw(mat.comment, '[MatId]:')
		if not m is None: matIdDict[m] = mat.name_jp #mat.name_en if options[OPT_ENG] else mat.name_jp
	
	for ren in render_tree.items():
		##== ('bone_idx', {'enabled': 'True', 'mat': ["", ...], 'parent': 'ca_slot00', 'receive': 'True', 'render': 'NAME in render_tree', 'shadows': 'On'})
		try:
			mats = ren[1][ren_Material]
			_mat = mats[0]
			_idx = int(ren[0])
			prDEBUG(_mat, f"\n-- {_mat} --> {ren}") ## MAT#MATID --> ('bone_idx', { .... })
			
			if _idx in idxOvr: ##[_f__IdxOvr]: Connect if we set an override
				local_state[renTag_idxOvr][_mat] = local_state[renTag_idxOvr][_idx]; ## Store the real Parent-Index for this Material
				del local_state[renTag_idxOvr][_idx]                                 ## Delete the older Render Index
#	###--- Find the correct render based on ID
			## Reason why it is not added to name: Names can change, or sorted differently, etc.
			## Reason why it did not work before: When descending the Bones for mapping, instances of same-name mats where not all bones are remapped might be swapped
			_vXFlag_UseId = True
			if not _vXFlag_UseId: render_tree[ren[0]][ren_Target] = uniquefy_material(_mat, uniqueMats)
			else:
				_matId = _mat.split('#')[-1]
				if not _matId in matIdDict:
					if not kk_skip.search(ren[1][ren_Render]): ## Dirty workaround to not log missing things that were useless
						util.throwIfDebug(DEBUG, f"ID '{_matId}' was supposed to exist but does not")
					continue
				render_tree[ren[0]][ren_Target] = matIdDict[_matId] #uniquefy_material(_mat, uniqueMats)
			prDEBUG(_mat, f"-- ren_Target: {render_tree[ren[0]][ren_Target]}")
#	### Map existing render to existing materials
			if _mat in json_mats:
				json_mats[_mat].setdefault(ren_Render, {})
				json_mats[_mat][ren_Render][ren[0]] = ren[1] ## Add a key 'BONE' with value 'render obj'
				prDEBUG(_mat, f"-- ren_Render: {json_mats[_mat]}")
			if len(mats) == 1: continue
			## This is the case if there are more "Material:" Rows than "Renderer:" Rows in the Material-Editor GUI
			if DEBUG: print(f"--:: Found {len(mats[1:])} more Mats to associate for this Renderer, using extra-scan....")
			matIdx = 0
			_mats = mats
			for mat in _mats[1:]:
				matIdx += 1
				if KAGE_MATERIAL in mat: continue
				prDEBUG2(_mat, f"-- MADE FOR: {reduceDictData(json_mats[_mat])}")
				
				prDEBUG2(_mat, f"-- Extra: {mat}")
				#--(1): Check if the name is identical -- Shared Material in Unity
				if mat == _mat: json_mats[uniquefy_material(mat, uniqueMats)] = _mat
				#--(2): Could also be copied in Material-Editor
				elif "MECopy" in mat:
					## As the name is already different, [json_mats] should contain an entry for this
					## So we just assign the same render to it
					if mat in json_mats and ren_Render not in json_mats[mat]:
						json_mats[mat].setdefault(ren_Render, {})
						json_mats[mat][ren_Render][ren[0]] = deepcopy(ren[1])
						### Set the Target to use the Unique extra key too (names are already correct by Uniquefy at the start)
						json_mats[mat][ren_Render][ren[0]][ren_Target] = re.sub(r"[#\-]+\d+$","",mat)
						
						prDEBUG2(mat, f"Setting ren_Render to {json_mats[mat][ren_Render][ren[0]].get(ren_Target, '<<error>')}");
					else: print(f"[W] Non-unique extra mat '{mat}' in '{_mat}'.Render")
				#--(3): Last thing could be some weird Multi-Mesh-per-Material stuff (basically (1) but for Renderer)
				else: 
					found = False
					matId = mat.split('#')[-1]
					if matId:
						matId = int(matId)
						for xMat in [x for x in json_mats if json_mats[x].get(ren_Render, None) is None]:
							prDEBUG2(f">(3) Check extra mat '{xMat}' == '{matId}' ....")
							#### If we have an Asset with more (effective) materials than renders, then we have to duplicate the render instead.
							## We also can't just add another item to the original object because we don't have a bone for that.
							#+++ If a Mat ends up in [Found overlapping names], it will get checked repeatedly
							if json_mats[xMat].get(mat_MatId, "<<>>") == matId:
								zMat = uniquefy_material(xMat, uniqueMats) ## MAT#MATID --> MAT*X
								#-- First create a new Render Entry like usual, but using the MaterialName
								json_mats[zMat] = json_mats[xMat]
								json_mats[zMat].setdefault(ren_Render, {})
								json_mats[zMat][ren_Render][ren[0]] = deepcopy(ren[1]) ## Else we change the original
								#-- Now remove the other materials from the own array
								json_mats[zMat][ren_Render][ren[0]][ren_Material] = [ mat ]
								#-- And the own from the actual owner
								del json_mats[_mat][ren_Render][ren[0]][ren_Material][matIdx]
								matIdx -= 1
								#-- Finally, delete the original (else it will be found again, which we don't want)
								del json_mats[xMat]
								#-- And set the correct Target
								json_mats[zMat][ren_Render][ren[0]][ren_Target] = xMat #zMat #xMat #zMat
								#-- Also add a special attribute that makes you special, for later
								json_mats[zMat][mat_Special] = True
								prDEBUG(zMat, f"\n>(2c) Full mat: {json_mats[zMat]}\n")
								prDEBUG2(zMat, f">(1) Found '{xMat}' as '{zMat}' ....")
								found = True
								break
					if found: continue
					print(f"[W] Unknown extra mat '{mat}' in '{_mat}'.Render")
		except Exception as ex:
			print(f"\n---[!!]: Skipped the following material:")
			print(ren)
			print(f"> Error-Reason: {ex}")
			if DEVDEBUG: raise ex
	if genFiles: util.write_json(render_tree, "_gen\#2M01_render_tree", True)
	if genFiles: util.write_json(json_mats, "_gen\#2M02_json_mats", True)
	return json_mats
#### By now, we only have existing materials and added render for which one exists.
## We also know which materials have no render and can auto-disable them



##############
# tree = { parent_idx: [ idx, idx ] }
def generate_tree(pmx, tree, slots):
	"""
		for idx,bone in bones:
			if parent != -1: add idx to tree[parent]
	"""
	for (i,b) in enumerate(pmx.bones):
		tree[i] = []
		if b.name_jp.startswith("ca_slot"): slots.append(i)
		#if b.tail_usebonelink is False and b.tail != -1: tree[b.tail].append(i)
		if b.parent_idx != -1: tree[b.parent_idx].append(i)

def treePrinter(pmx, tree, _start):
	def __treePrinter(start, indent="- ", lvl=0):
		bone = pmx.bones[start]
		print("{}{}: {}".format(indent*lvl, start, bone.name_jp))
		for i in tree[start]: __treePrinter(i,indent,lvl+1)
	__treePrinter(_start)

def prDEBUG(token, text=None):
	if not DEBUG: return
	if text is None: print(token)
	elif "hair*1" in str(token): print(text)
	elif "cf_m_hair_f_08" in str(token): print(text)
	elif "o_bot_skirt01" in str(token): print(text)
def prDEBUG2(token, text=None):
	if DEVDEBUG: prDEBUG(token if text is None else text, None)
	else:        prDEBUG(token, text)

def reduceDictData(obj):
	import copy
	if not type(obj) in [dict]: return obj
	_dict = copy.deepcopy(obj)
	for k in _dict.keys():
		if "Color" in k: _dict[k] = ["...."]
		elif "textures" == k: _dict[k] = ["...."]
	return _dict

##################
### Texture Tags
t__Alpha     = "AlphaMask"
t__Another   = "AnotherRamp"
t__Color     = "ColorMask"
t__Detail    = "DetailMask"
t__Glass     = "GlassRamp"
t__HairGloss = "HairGloss"
t__Line      = "LineMask"
t__Liquid    = "liquid"
t__Main      = "MainTex"
t__NorMap    = "NormalMap"
t__NorMapDet = "NormalMapDetail"
t__NorMask   = "NormalMask"
t__overtex1  = "overtex1"
t__overtex2  = "overtex2"
t__overtex3  = "overtex3"


## shorthands:  __typePrinter_Dict
if __name__ == '__main__': util.main_starter(GenerateJsonFile)