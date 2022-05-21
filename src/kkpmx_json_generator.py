# Cazoo - 2021-05-08
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
import json
import re
import os

import nuthouse01_core as core
import morph_scale
import kkpmx_utils as util
DEBUG = util.DEBUG or False
DEVDEBUG = False

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
			key = "{0:<{align}}".format('"{}": '.format(kv), align=inline)
			value = _decoder(o[kv], indent, lvl+1)
			if type(value) == dict: key = '"{}": '.format(kv)
			res.append(indent*lvl + key + value + ",")
		res.append(indent*(lvl-1) + "}")
		return "\n".join(res)
	return json.dumps(o)

def find_bone(pmx,name,e=True):  return morph_scale.get_idx_in_pmxsublist(name, pmx.bones,e)

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
##--## Raw JSON keys (Output)
out_name    = "name"
out_opt     = "options"
out_optBase = "base"
out_optHair = "process_hair"
out_temp    = "template"
out_inherit = "inherit"
##--## Options used for render_tree
ren_Enabled  = "enabled" ## Render is enabled:   "On", "Off" --> "True","False"
ren_Shadows  = "shadows" ## Can cast shadows:    "On", "Off", "Two Sided", "Shadows Only"
ren_Receive  = "receive" ## Can receive shadows: "On", "Off" --> "True","False"
ren_Parent   = "parent"  ## The Slot note (ca_slot & ct_)
ren_Render   = "render"  ## Original render name
ren_Material = "mat"     ## Array of materials
ren_Target   = "target"  ## The converted / uniquefied material name
##--## Options for write_entity
opt_Name     = "name"      # Main argument
opt_Group    = "shader"    # Override token for shader
opt_texAvail = "available" # Override for available textures
opt_texUse   = "textures"  # Override for useable textures
opt_Comment  = "comment"   # Provide Comment
opt_Iter     = "suffix"    # Go forward when multiple are expected
#############
## State
mat_dict = { }
cloth_dict = {
	ct_clothesBot:0, ct_clothesTop:0, ct_shorts:0, ct_bra: 0,
	ct_gloves:0, ct_panst:0, ct_socks:0, ct_shoes:0
	}
global_dict = { }

#############
def GenerateJsonFile(pmx, input_filename_pmx):
	path = os.path.join(os.path.split(input_filename_pmx)[0], "#generateJSON.json")
	if os.path.exists(path):
		if not util.ask_yes_no("Found existing #generateJSON file. Regenerate?", "n"):
			return path

	##### Generate Bone tree
	slots = []
	tree = {}
	generate_tree(pmx, tree, slots)
	## @todo: ask to make all material names unique (required anyway) ==> option
	
	#[X]: Populate Map with (pmx.materials).name_jp being unique
	#### dict --> { name: { name, idx } }
	#### dict --> { name: True or False }
	kk_re = re.compile(r" ?\(Instance\)_?(\([-0-9]*\))?")
	kk_skip = re.compile('|'.join(["Bonelyfans","shadowcast","Standard"]))
	for (idx, name) in enumerate([m.name_jp for m in pmx.materials]):
		suffix = 0
		mat = kk_re.sub("", name)
		if mat in mat_dict:
			while True:
				suffix += 1
				if ("{}*{}".format(mat, suffix)) not in mat_dict: break
			#pmx.materials[idx].name_en = "{}*{}".format(mat.name_en, suffix)
			mat = "{}*{}".format(mat, suffix)
		mat_dict[mat] = kk_skip.match(name)
	
	arr = [ ]
	arr.append(Comment("Generated with KKPMX v.1.7.0"))
	arr.append(Comment("Colors are RGBA mapped to [0...1]; Alpha is added if missing"))
	##	write Name
	arr.append((out_name, "....")) ## in [json_ren]
	##	Write options: Maybe ask for each option ?
	opt = {
		"use_english": True,
		##to use script(cleanup script): default True ## << makes materials unique
		##to use script(add morphs):     default True
		out_optBase: "%PMX%/extra",##ask for base path ++ rename all "exported textures" in said folder
		"expl_Hair": "## Set this to false to skip generating Hair Textures",
		out_optHair: True,
	}
	arr.append((out_opt, opt))
	#print("--- << some nice message >>")
	json_ren = util.load_json_file()
	if json_ren is None:
		print("--- No file has been generated")
		return False
	if raw_meta in json_ren:
		if raw_name in json_ren[raw_meta]:
			arr[2] = (out_name, json_ren[raw_meta][raw_name])
		if raw_eye in json_ren[raw_meta]:
			global_dict[raw_eye] = json_ren[raw_meta][raw_eye] in ["True", "true"]
	render_tree = generate_render_tree(pmx, tree, json_ren[raw_ren])
	json_tree = generate_material_tree(pmx, tree, render_tree, json_ren[raw_mat])
	
	parent_tree = { "_blank": [] }#generate_parent_tree(json_tree)
	for (k,v) in json_tree.items():
		#print(f"Key: {k} \\ Value: {v['token']}")
		if ren_Render not in v:
			#print(f"(k,v) =\n> {k}\n> {v}")
			## Handle Copy-Material
			if type(v) is str: _parent = list(json_tree[v][ren_Render].values())[0].get(ren_Parent, "_blank")
			else: _parent = "_blank"
		else: _parent = list(v[ren_Render].values())[0].get(ren_Parent, "_blank")
		parent_tree.setdefault(_parent, [])
		parent_tree[_parent].append(k)
	#util.write_json(parent_tree, "_gen\#3Parents")
	
	if DEBUG:
		print("--- These materials contained no target and will be discarded")
		print(parent_tree["_blank"])
	
	GenerateJsonFile__Body(pmx, arr, json_tree, parent_tree)
	GenerateJsonFile__Clothes(pmx, arr, json_tree, parent_tree)
	GenerateJsonFile__Accs(pmx, arr, json_tree, slots, parent_tree)
	
	path = os.path.join(os.path.split(input_filename_pmx)[0], "#generateJSON.json")
	output = [ "{" ] + [_decoder(o, "\t", 1) for o in arr] + [ '}' ]
	core.write_list_to_txtfile(path, output, True)
	return path
GenerateJsonFile.__doc__ = helptext
########
def GenerateJsonFile__Body(pmx, arr, json_tree, parent_tree):
	print("==== Printing Body")
	arr2 = []
	##	write COMMENT_SKIN
	arr.append(Comment("== Skin ==", end=True))
	##	write "cf_m_body"
	opt = {
			opt_Name: "cf_m_body", 	opt_Group: "body",
			opt_texAvail: [t__Detail, t__Line, t__Main, t__NorMap, t__NorMapDet, t__overtex1], ## t__overtex2
			opt_texUse: [t__Detail, t__Line, t__Main, t__overtex1],
		}
	write_entity(pmx, arr, json_tree, opt) ## add option for [custom group], [Comment]
	
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
	#arr.append("cf_m_eyeline_kage", {
	#	"group": "color", #// ShaderForge/toon_eyew_lod0, 2900
	#	"Color":       [ 1,         0.95, 0.92, 1 ],
	#	"ShadowColor": [ 0.6298235, 0.6403289, 0.747, 1 ],
	#},Comment("Export manually"))
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
	write_entity(pmx, arr, json_tree, { opt_Name: "cf_m_tang",
		opt_texUse: [ t__Color, t__Detail, t__Main ],
		#// t__Another, t__Color, t__Detail, t__Line, t__Main, t__NorMap
		opt_Comment: Comment("Tongue may or may not be Gray or Cyan by default.", idx="Tongue")
		})
	#arr.append(Comment(NL=True))
	#
	#return
	
	##	write COMMENT_HAIR
	def search_handler(cat):
		arr.append(Comment("", idx=cat_to_Title.get(cat,cat)))
		opt = { opt_Name: cat, opt_Group: "hair",
				opt_texAvail: [t__Alpha, t__Another, t__Color, t__Detail, t__HairGloss, t__Main, t__NorMap],
				opt_texUse: [t__Color, t__Detail, t__Alpha],
			}
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
	print("==== Printing Accessories")
	##	write COMMENT_ACCS
	arr.append(Comment("----------- Accs", end=False))
	for i in slots:
		slot = pmx.bones[i].name_jp
		idx = slot.lstrip("ca_slot")
		name = "-------------------"
		arr.append(Comment(name, idx="Slot "+str(idx)))
		print("== Printing " + slot)
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
	
	targetBase = {}
	_elem = filter(lambda kv: kv[0].startswith(name), json_tree.items())
	if not _elem:
		print("[!] Could not find any match for " + name)
		return
	try:
		elem = next(_elem)
	except StopIteration:
		print(f"[!] Model does not contain an entry for {name}")
		return
	suffix = opt.get(opt_Iter, 0)
	for x in range(suffix): elem = next(_elem)
	
	#---#
	token = re.sub(r"( \(Instance\))+", "", elem[0]) ## the full name that started with [name], without (instance)
	mat = elem[1]
	## Handle Copy-Material: mat will be string then -- Just add as is
	if type(mat) is str:
		arr.append((token, re.sub(r"\*\d+", "", token)))
		return
	
	render = mat.get("render",{})
	## @todo: print comment
	
	### if using [meta.resetEyes], change it accordingly
	if global_dict.get(raw_eye, False):
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
		
	#### Generate Template (== the Material)
	targetBase["available"] = opt.get(opt_texAvail, []) ## Build some map of {"t__Main": ["main_item", ...]} and do a filter over all included
	targetBase["textures"] = opt.get(opt_texUse, [])
	
	for (k,v) in mat.items():
		if k in ["render","token"]: continue
		## sync how its done in eye
		if appendMatch(k,"offset"): continue      # ignore if == (0.0, 0.0)
		if appendMatch(k,"scale"): continue       # ignore if == (1.0, 1.0)
		if appendMatch(k,"shader"): continue      # add as "group" (without "Shader Forge/")
		if k.startswith("_"): targetBase[k.lstrip("_")] = v
		else: print("[W] Unprocessed attribute " + k)
	#-----
	## build object & add to [arr]
	
	targetBase[out_temp] = len(render) > 0 ## Generate Warning about "template without render" (+ add special case for kage)
	
	#comment = opt.get(opt_Comment) ## if len(render) > 1 else None
	#if len(render) > 1:
	arr.append((token, targetBase, opt.get(opt_Comment)))
	#else: arr.append((token, targetBase))

	# (?) ### Do smt about Comment(...)
	### Generate the render entries that use that material
	for (k,r) in render.items(): ## mat
		key = r.get(ren_Target) ## Contains already *-suffix if any
		val = { }
		val[ren_Enabled] = r.get(ren_Enabled, "False") == "True"
		val[ren_Receive] = r.get(ren_Receive, "False") == "True"
		val[ren_Shadows] = r.get(ren_Shadows, "Off")
		val[ren_Render]  = r.get(ren_Render, "")
		parent = r.get(ren_Parent)
		if parent:
			val[ren_Parent] = parent
			if name.startswith("ct_"):
				val["slot"]   = parent
			else:
				val["slot"]   = pmx.bones[pmx.bones[find_bone(pmx, parent)].parent_idx].name_jp
		
		### add to arr
		#mat_comment = opt.get(opt_Comment) ## generate some based on data
		arr.append((key, { "meta": val, out_inherit: token }))

### Goal with Comment
# Show original slot (mapped with dict) ++ Name (mapped with dict ?)


def Generate__main_cloth(arr, retObj):
	org    = retObj.get(ret_Self)
	if org is None: raise Exception("INVALID DATA: No Org found")
	render = retObj.get(ret_Render, "<org:{}>".format(org))
	mat    = retObj.get(ret_Mat, "<{}>".format(render))
	name   = retObj.get(ret_Name)
	cat    = retObj.get(ret_Cat)
	meta   = { "render": render }
	if cat:
		meta["slot"] = cat
		cat = cat_to_Title[cat]
	com    = None
	if name: com = Comment(name, idx=cat)
	elif cat: com = Comment("<Acc>", idx=cat)
	arr.append((mat, {# [Outer Layer] Puffer Jacket Long
		"group": "cloth", #// ShaderForge/main_opaque
		"meta": meta,
		"available": "#// t__Alpha, t__Another, t__Detail, t__Line, t__Main, t__NorMap",
		"textures": [ "t__Detail", "t__Main" ], #// Sometimes only has Main
		"ShadowColor":          [  0.7881584,  0.8663371, 0.9803922 ],
		"SpecularColor":        [  1,  1,  1, 0],
		"notusetexspecular":    0,
		"rimpower":             0.75,
		"rimV":                 0.2,
		"ShadowExtend":         0.6,
		"ShadowExtendAnother":  0,
		"SpecularHeight":       0.98,
		"SpecularPower":        0,
		"SpecularPowerNail":    0,
	}, com))

def Generate__main_item(arr, retObj):
	org    = retObj.get(ret_Self)
	if org is None: raise Exception("INVALID DATA: No Org found")
	render = retObj.get(ret_Render, "<org:{}>".format(org))
	mat    = retObj.get(ret_Mat, "<{}>".format(render))
	name   = retObj.get(ret_Name)
	parent = retObj.get(ret_Parent)
	com    = None
	if name: com = Comment(name, idx=parent)
	arr.append((mat, {
		"group": "item", #// ShaderForge/main_item
		"meta": {
			"render": render,
			"slot": parent,
		},
		"available": "#// t__Another, t__Color, t__Detail, t__Line, t__Main, t__NorMap",
		"textures": [ ],
		"Color":                [ 0.0, 0.0, 0.0 ],
		"Color2":               [ 0.0, 0.0, 0.0 ],
		"Color3":               [ 0.0, 0.0, 0.0 ],
		"ShadowColor":          [ 0.0, 0.0, 0.0 ],
		"AnotherRampFull":      0,
		"LineWidthS":           1,
		"notusetexspecular":    0,
		"rimpower":             0.5,
		"rimV":                 0.2,
		"ShadowExtend":         0.5,
		"ShadowExtendAnother":  0,
		"SpecularHeight":       0.98,
		"SpecularPower":        0,
	}, com))

##############
###

def collectSubTree(pmx, tree, _start):
	"""
	IN  :: pmx \\ tree \\ idx in [tree] to start
	OUT :: dict of all children of [start]
	:: Format: { "bone.name_jp": bone_idx }
	"""
	subTree = {}
	def __treeWalker(idx):
		if idx is None: return # works because declared own find_bone
		#subTree[pmx.bones[idx].name_jp] = idx
		name = pmx.bones[idx].name_jp
		target = idx
		if name in subTree:
			#print("[subTree] {} already exists (as {}, new {})!".format(name, subTree[name], idx))
			target = max(subTree[name], target)
		subTree[name] = target
		for i in tree[idx]: __treeWalker(i)
	__treeWalker(find_bone(pmx, _start))
	return subTree

kk_re = re.compile(r"( \(Instance\))*(@\w+|#\-\d+)")
def uniquefy_material(mat: str, names: list):
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
	Parse the render part of the generated plugin data
	-- Maps unique-fyied names to their respective bones
	-- Which also ensures that only useable render elements / materials remain
	"""
	#util.write_json(json_ren, "_gen\#1R00_json_ren", True)
	#DEBUG = True
	
	### Group by Parent
	renArr = {}
	if DEBUG: print(f"[json_ren]:")
	for x in json_ren.keys(): ## RENDER in { RENDER: BODY }
		r = json_ren[x]
		if DEBUG: print(f"-- {x}")
		renArr.setdefault(r[ren_Parent], [])
		renArr[r[ren_Parent]].append(x) ## --> "Parent": { RENDER: BODY, ...}, ...
		#if len(renArr[r[ren_Material]]) > 1:
		#	print("[] Warning: Render '{}' contains multiple materials!".format(x))
	#util.write_json(renArr, "_gen\#1R01_renArr", True) ### Dict of { "parent": [ "render", ...] }
	### Link to bone_idx
	#print("------------")
	#print(renArr)
	#print("------------")
	
	renToBone = {}
	for (k,v) in renArr.items(): #// SLOT: { RENDER: BODY, .... }, ...
		if DEVDEBUG: print("==== " + k)
		cArr = collectSubTree(pmx, tree, k) #//--> dict{"name": idx}
		if DEVDEBUG: print(f"Subtree: {cArr}") #// All bones under this slot
		if cArr == {}: continue
		#print(f"[V]: {v}")
		for c in v: #// [RENDER, RENDER, ....]
			cc = re.sub("@\w+$|#-?\d+$","", c) ## Cut away the meta suffix
			#print(f"[CC]: {cc}")
			if cc in cArr.keys(): #// if RENDER in cArr
				i = cArr[cc] #// idx of Bone for RENDER
				if DEVDEBUG: print("{} << {}".format(i,cc)) #//== Render Bone
				if i not in renToBone:
					renToBone[i] = json_ren[c] #// idx: BODY
					continue
	#util.write_jsonX(renToBone, "#renToBone.json", indent="\t", sort_keys=True)
	#util.write_jsonX(renToBone, "_gen\#1R02_renToBone.json", indent="\t", sort_keys=True)
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
	#util.write_json(json_mats, "_gen\#2M00_json_mats", True)
	
	#print("------ render_tree")
	#util.__typePrinter_Dict(render_tree)
	#print("------ json_mats")
	#util.__typePrinter_Dict(json_mats)
	#print("------ ----")
	
#	### Create unique material names for all render elements
	uniqueMats = []
	#print(f"RenderTree:")
	for ren in render_tree.items():
		##== ('bone_idx', {'enabled': 'True', 'mat': ["", ...], 'parent': 'ca_slot00', 'receive': 'True', 'render': 'NAME in render_tree', 'shadows': 'On'})
		try:
			mats = ren[1][ren_Material]
			_mat = mats[0]
			#print(f"-- {_mat} --> {ren}")
			render_tree[ren[0]][ren_Target] = uniquefy_material(_mat, uniqueMats)
#	### Map existing render to existing materials
			if _mat in json_mats:
				json_mats[_mat].setdefault(ren_Render, {})
				json_mats[_mat][ren_Render][ren[0]] = ren[1]
			if len(mats) == 1: continue
			for mat in mats[1:]:
				# If the name is identical -- Shared Material in Unity
				if mat == _mat: json_mats[uniquefy_material(mat, uniqueMats)] = _mat
		except Exception as ex:
			print(f"---[!!]: Skipped the following material:")
			print(ren)
			print(f"> Error-Reason: {ex}")
	#util.write_json(render_tree, "_gen\#2M01_render_tree", True)
	#util.write_json(json_mats, "_gen\#2M02_json_mats", True)
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