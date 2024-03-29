# Cazoo - 2021-05-08
# This code is free to use, but I cannot be held responsible for damages that it may or may not cause.
#####################
import re     ## re.sub
import os     ## 
import copy   ## copy.deepcopy
import datetime
import numpy as np

try:
	import nuthouse01_core as core
	import nuthouse01_pmx_parser as pmxlib
	import nuthouse01_pmx_struct as pmxstruct
except ImportError as eee:
	print(eee.__class__.__name__, eee)
	print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
	print("...press ENTER to exit...")
	input()
	exit()

infotext = '''
Scans the given material(s) against bleed-through of vertices / faces poking through the surface of another.
> Currently will only find all protrusions going towards negative Z-Axis, and may not work for X or Y Axis.

The initial bounding box is defined by the base material which the target is checked against
- Example: [Base] Jacket vs. Vest \\ [Target] Body ::: Look where the body is visible through clothes
--- Jacket: Bounding Box goes from wrist to wrist, and neck to waist. It won't scan Hands or the lower body
--- Vest:   Bounding Box stops at the shoulders --- That means it will ignore the arms as well.

There are three options to define the coordinates of a bounding box. All vertices outside it will be ignored.
-- Choose best-guess defaults to remove chest protrusions on a KK-Model
-- Input manual coordinates (for either a scan or box cut)
-- Full scan (== full box of target against full box of base)
The smaller it is, the less calculations are performed and it will complete faster.

[Output]: PMX file '[modelname]_cutScan.pmx'
-- As opposed to usual, it will always count up instead of appending if '_cutScan' is already part of the filename

[Logging]: Stores which mode, materials, and bounding box was used.

'''

DEBUG = False          # Local debug
global_opt = { }       # Store argument info ## TODO: Switch to global_state of util
OPT_MORE = "moreinfo"
OPT_YES  = "all_yes"
def _verbose(): return global_opt.get("moreinfo", True)
local_state = {}
mirMat = "mirrorMat"
mirDst = "mirrorMorph"
mirCan = "enableMirror" # Exists to avoid surprises in case the methods are called in some other way
def _mirror(): return local_state.get(mirCan, False)

def run(pmx, input_filename_pmx, moreinfo=False, _opt = {}):
	from kkpmx_core import end
	import kkpmx_utils as util
	import json
	global_opt["moreinfo"] = moreinfo or DEBUG or util.DEBUG
	global_opt[OPT_YES] = _opt.get("all_yes", False)
	
	message = """Choose:
-- [0] Use best-guess defaults from KK :: this will ask for 2-3 idx/names and perform 1-2 runs
-- [1] Input manual bounding box (and cut out completely into new material) :: 1 material, 0 runs
-- [2] Input manual bounding box (and scan against the base material)       :: 2 materials, 1 run
-- [3] Full scan (Warning: this WILL take long depending on material size)  :: 2 materials, 1 run
"""
	value = core.MY_GENERAL_INPUT_FUNC(lambda x: x in ['0','1','2','3'], message + " [0/1/2/3]?")
	if value == "0": return run_kk_defaults(pmx, input_filename_pmx)
	#
	#bounds = { "minY": 10.20, "maxZ": 0 }
	bounds = { }
	if value in ["1","2"] :
		def check(x):
			try:
				y = json.loads(x)
				if type(y) in [int, float]: return True
				if type(y) is not list: return False
				if len(y) != 3: return False
				return any([type(z) in [int, float] for z in y])
			except: return False
		def askValue1(key, message):
			if key not in bounds: bounds[key] = float(core.MY_GENERAL_INPUT_FUNC(util.is_number, f"[{key}]: {message}"))
		def askValue2(key, message):
			value = json.loads(core.MY_GENERAL_INPUT_FUNC(check, f"[{key}]: {message}"))
			if type(value) == list:
				if key.startswith("min"): bounds.update({"minX": value[0], "minY": value[1], "minZ": value[2]})
				else: bounds.update({"maxX": value[0], "maxY": value[1], "maxZ": value[2]})
			else: bounds[key] = value
					
		print("Note: Coordinates exceeding the bounding box of the base material will be ignored.")
		print("Note: The first two can also be an array of three coordinates [X, Y, Z], for faster copy paste.")
		askValue2("minX", "Towards right Arm")
		askValue2("maxX", "Towards left Arm")
		askValue1("minY", "Minimum height")
		askValue1("maxY", "Maximum height")
		askValue1("minZ", "Towards Face")
		askValue1("maxZ", "Towards Back")
	else: bounds = { "minY": 0 }
	if value == "1":
		__results = cut_out_box_from_material(pmx, bounds)
		if (bounds.get("minX", 0) != 0 or bounds.get("max", 0) != 0):
			print("")
			if util.ask_yes_no("Mirror Cut-out on X-Axis", "n"):
				local_state[mirCan] = True
				tmp = bounds.get("minX", 0)
				bounds["minX"] = - bounds.get("maxX", 0)
				bounds["maxX"] = - tmp
				__results += cut_out_box_from_material(pmx, bounds)
				local_state[mirCan] = False
	else:
		options = { "affectPMX": True }
		__results = __run(pmx, new_bounds=bounds, moreinfo=moreinfo, options=options)
	if __results: return __endCut(pmx, input_filename_pmx, __results)
run.__doc__ = infotext
############
def run_kk_defaults(pmx, input_filename_pmx, _opt = {}):
	import kkpmx_core as kklib
	import kkpmx_utils as util
	print("")
	log_line = []
	
	### Ask for Body Index
	body = kklib.ask_for_material(pmx, extra="-- Body (The thing that causes the bleed)", default = "cf_m_body", returnIdx = False)
	print("")

	### Ask for Bra Index (or none)
	print(">Note: On KK the underwear follows the body and cuts through the upper layers as well.")
	print(">-- Use the same name/idx as for [body] (or leave empty) to skip the 2nd run (e.g. you plan to hide the inside anyway)")
	inside = kklib.ask_for_material(pmx, extra="-- Bra / Inside", default = body.name_jp, returnIdx = False, rec="ct_bra")
	has_inside = inside.name_jp != body.name_jp
	if not has_inside: print(f"[*] Skipping Inside Material")
	print("")
	
	### Ask for Outer Index (or none)
	print(">Note: If it bleeds through multiple textures, use the most inner of them");print("")
	flag = True
	while flag:
		outside = kklib.ask_for_material(pmx, extra="-- Outside (Shirt or Jacket)", default = "cf_m_top_inner01", returnIdx = False, rec="ct_clothesTop")
		### if neither shirt nor bra, return
		flag = util.find_mat(pmx, outside.name_jp) == util.find_mat(pmx, body.name_jp)
		if flag: print("[!] This mode requires 1st and 3rd material to be different! You may want to use Mode[1] instead.")
	#----------#
	
	msg = ["== Cut Mode [0] ==", f"using Base:{body.name_jp}" + (f", Inner:{inside.name_jp}" if has_inside else "") + f", Outside:{outside.name_jp}"]
	log_line += msg
	print("[*] " + msg[1])
	print("")
	
	## Do shoulders as well? --> Needs Shirt (also fix Emblem bc bleed through)
	## Ask if providing own bounds or using default box (extended or only around nips)
	bounds = { "minY": 10.20, "minZ": 0, "maxZ": 0 }
	def addIfFound(name,key,idx,pad=None):
		bone_idx = util.find_bone(pmx, name)
		if bone_idx:
			bounds[key] = pmx.bones[bone_idx].pos[idx]
			if pad is not None: bounds[key] += pad
	def averageOut(name, key, idx, pad=None):
		bone_idx = util.find_bone(pmx, name)
		if bone_idx:
			tmp = pmx.bones[bone_idx].pos[idx]
			if pad is not None: bounds[key] += pad
			bounds[key] = (bounds.get(key,0)+tmp)/2
	
	CH__DETAIL = 0; CH__BOX_SMALL = 1; CH__BOX_BIG = 3; CH__NO = 4; CH__BOX_MEDIUM=2; CH__BOX_MINI=5;
	choices = [
		("Detailed           -- Restrict around Chest then do full scan within", CH__DETAIL),
		#("Rough Box (nano)  -- Tips only", CH__BOX_NANO),
		("Rough Box (mini)   -- Front only", CH__BOX_MINI),
		("Rough Box (small)  -- Just barely above the nips", CH__BOX_SMALL),
		("Rough Box (medium) -- Inbetween these two options", CH__BOX_MEDIUM),
		("Rough Box (big)    -- Height around the center of the arms (incl. armpits)", CH__BOX_BIG),
		("No                 -- Restrict to bounding box of inner, then do full scan of both", CH__NO)
	]
	choice = util.ask_choices("KK Defaults: Restrict to optimized box around chest ?", choices)
	if choice == CH__DETAIL:
		#if util.find_bone(pmx, "cf_j_spinesk_02", True):
		#	addIfFound("cf_j_spinesk_02", "maxY", 1)
		#	addIfFound("cf_hit_bust00", "minY", 1)
		##--- cf_hit_spine02_L -- rough upper limit of standard size
		##--- cf_j_spinesk_02(14.36657) -- slightly higher
		##--- cf_hit_bust00(13.84542) -- comfortable lower limit of standard size
		#else:
		posY = pmx.bones[util.find_bone(pmx, "胸親")].pos[1]
		bounds["minY"] = posY - 0.25
		bounds["maxY"] = posY + 0.50 ## 14.07162
		#- [Z-Axis](back<front): 右胸操作(-0.66) cf_j_bust02_R_01(-0.697)
		#-- -- 右AH1 (rough maxZ=back[0.4539899])
		#-- -- cf_s_bust03_R(barely behind them[-0.8914542])
		#-- -- 胸親 (Parent bone for physics[-0.6669899])
		addIfFound("cf_s_bnip02_R", "minZ", 2)
		bounds["minZ"] = bounds["minZ"] - 2
		
		addIfFound("cf_s_bust03_R", "maxZ", 2)
		averageOut("胸親", "maxZ", 2)
		averageOut("cf_s_bust03_R", "maxZ", 2)
		averageOut("cf_s_bust03_R", "maxZ", 2)
	elif choice == CH__BOX_BIG:
		addIfFound("右腕捩1", "minX", 0)
		addIfFound("左腕捩1", "maxX", 0)
		addIfFound("cf_s_spine02", "minY", 1)
		addIfFound("左腕捩1", "maxY", 1, -0.2)
		bounds["maxZ"] = 3
		bounds["minZ"] = -3
	elif choice == CH__BOX_MEDIUM:
		addIfFound("右腕捩1", "minX", 0)
		addIfFound("左腕捩1", "maxX", 0)
		addIfFound("cf_s_spine02", "minY", 1)
		addIfFound("左腕捩1", "maxY", 1)
		
		averageOut("cf_s_bnip02_R", "minX", 0, -0.3)
		averageOut("cf_s_bnip02_L", "maxX", 0, 0.3)
		averageOut("胸親", "minY", 1, -0.25)
		averageOut("胸親", "maxY", 1, 0.25)
		
		bounds["maxZ"] = 3
		bounds["minZ"] = -3
		
	elif choice == CH__BOX_SMALL:
		addIfFound("cf_s_bnip02_R", "minX", 0, -0.3)
		addIfFound("cf_s_bnip02_L", "maxX", 0, 0.3)
		
		addIfFound("cf_j_bnip02_R", "minY", 1, -0.25)
		addIfFound("胸親", "maxY", 1, 0.25)
		
		bounds["maxZ"] = 3
		bounds["minZ"] = -3
		
	elif choice == CH__BOX_MINI:
		addIfFound("cf_j_bnip02_R", "minX", 0, -0.33)
		addIfFound("cf_j_bnip02_L", "maxX", 0, 0.33)
		
		addIfFound("cf_j_bnip02_R", "minY", 1, -0.33)
		addIfFound("cf_j_bnip02_R", "maxY", 1, 0.33)
		
		addIfFound("cf_s_bnip02_R", "maxZ", 2, 0.25)
		bounds["minZ"] = -3
	elif has_inside:
		bounds = get_bounding_box(pmx, inside)
	
	options = {
		"affectPMX": True,
		"exceed": [4],
		"ask": False,
		"initial_hidden": True,
	}
	
	if choice in [CH__BOX_BIG, CH__BOX_MEDIUM, CH__BOX_SMALL, CH__BOX_MINI]:
		if has_inside:
			results = cut_out_box_from_material(pmx, bounds, util.find_mat(pmx, inside.name_jp))
			#log_line.append(f"Isolated vertices of {inside.name_jp} peaking through {outside.name_jp}")
			log_line.append(results)
			#log_line.append("--------")
			print("-------------------")
		results = cut_out_box_from_material(pmx, bounds, util.find_mat(pmx, body.name_jp))
		#log_line.append(f"Isolated vertices of {body.name_jp} peaking through {outside.name_jp}")
	else:
		if has_inside:
			results = __run(pmx, outside, inside, bounds, options=options)
			log_line.append(f"Isolated vertices of {inside.name_jp} peaking through {outside.name_jp}")
			log_line.append(results)
			log_line.append("--------")
			print("-------------------")
		results = __run(pmx, outside, body, bounds, options=options)
		log_line.append(f"Isolated vertices of {body.name_jp} peaking through {outside.name_jp}")
	log_line.append(results)
	return __endCut(pmx, input_filename_pmx, core.flatten(log_line))
run_kk_defaults.__doc__ = infotext
############
def __run(pmx, base_mat=None, new_mat=None, new_bounds=None, moreinfo=False, options={}):
	"""
	:param pmx      [Pmx]
	:param base_mat [PmxMaterial] Protruded  Material (to calculate cut-worthyness)
	:param new_mat  [PmxMaterial] Protruding Material (to cut off from)
	
	Options = {
		"affectPMX":   False for simulation mode; default is True
		"exceed":      Array of int (1 to 6) -- directions that ignore the bounding box
		"ask":         True to ask for material to store into, False to not ask
		:     -- Also allows a material index directly, but will fall back to [ask=True] if invalid. -1 for new
		"initial_hidden": When generating a new material, set True to hide it initially, else false.
	}
	The morph has to be added to the [Facial] frame manually for the time being.
	"""
	from kkpmx_core import ask_for_material, from_faces_get_vertices, from_material_get_faces, from_vertices_get_faces
	from kkpmx_utils import find_mat, translate_name
	import kkpmx_core as kklib
	global_opt["moreinfo"] = _verbose() or moreinfo or DEBUG
	
	affectPMX = options.get("affectPMX", True)
	##################################
	import numpy as np
	import kkpmx_utils as util
	
	
	##  Get sub mat lists
	if new_mat is None:
		new_mat = ask_for_material(pmx, ": Material that causes the bleed-through", default="cf_m_body", returnIdx=False)
	##  Get main mat
	if base_mat is None:
		base_mat = ask_for_material(pmx, ": Material that received the bleed-through", default="cf_m_top_inner06", returnIdx=False)
	
	##  Collect all verts
	mat_idx   = find_mat(pmx, base_mat.name_jp)
	old_faces = from_material_get_faces(pmx, mat_idx, False, moreinfo=False) ## Never print the line here
	old_verts = from_faces_get_vertices(pmx, old_faces, False, moreinfo=moreinfo)
	if DEBUG: print(f"[D]>: Faces: {len(old_faces)} \\ Vertex: {len(old_verts)}")
	old_idx_verts  = from_faces_get_vertices(pmx, old_faces, True, moreinfo=False)
	bounds = get_bounding_box(pmx, base_mat, old_verts, moreinfo=moreinfo)
	# Array in case I change it to allow multiple
	if "exceed" not in options:
		exceed = [ util.ask_direction("Any Direction to exceed/ignore bounds", allow_empty=True) ]
	else: exceed = options.get("exceed", [])
	
	def formatBox(box): print(f"[ {box[0]:19.15f}, {box[1]:19.15f}, {box[2]:19.15f}]")
	print("-- Bounding Box (X / Y / Z) of " + base_mat.name_jp)
	formatBox(bounds[0])
	formatBox(bounds[1])
	if new_bounds is not None:
		def extendBounds(name, i1, i2, minmax):
			if new_bounds.__contains__(name):
				iX = i2 * 2 + i1
				#print(f"{iX} -- {name}")
				#if (iX in exceed):
				#	#print(f"*{minmax.__name__}({float(new_bounds[name])}, {bounds[i1][i2]})")
				#	minmax = min if i1 == 0 else max
				#	exceed.remove(iX)
				try: ## box should not get smaller than original material bounds
					#print(f"{minmax.__name__}({float(new_bounds[name])}, {bounds[i1][i2]})")
					bounds[i1][i2] = minmax(float(new_bounds[name]), bounds[i1][i2])
				except: pass
		extendBounds("minX",0,0,max)
		extendBounds("minY",0,1,max)
		extendBounds("minZ",0,2,max)
		extendBounds("maxX",1,0,min)
		extendBounds("maxY",1,1,min)
		extendBounds("maxZ",1,2,max)
		if (len(exceed) == 0) or (None in exceed):
			print("-- Bounding Box (override)")
			formatBox(bounds[0])
			formatBox(bounds[1])
			exceed = [None]
	if None not in exceed:
		eee = exceed[0]
		sign = eee % 2
		val = int((eee - sign) / 2)
		bounds[sign][val] = 50 * (-1 if sign == 0 else 1)
		print("-- Bounding Box (override)")
		formatBox(bounds[0])
		formatBox(bounds[1])

	##  Get sub mat lists
	if type(new_mat) == type(0):
		mat_idx2 = new_mat
		new_mat = pmx.materials[mat_idx2]
	else:
		mat_idx2 = find_mat(pmx, new_mat.name_jp)
	
	##  Their verts
	faces = from_material_get_faces(pmx, mat_idx2, False)
	new_verts = from_faces_get_vertices(pmx, faces, False)
	idx_verts = from_faces_get_vertices(pmx, faces, True)  ## So that the mapping matches later on.
	##  >> Filter out outside bounds
	#print("----[Important] This will only calculate surface cuts within the bounding box of (minX,minY) to (maxX,maxY) of the base material.")## verify
	#print("----[Important] >>> That means, it will find all surface cuts going along the Z-Axis, but may not work for X or Y Axis.")
	#print("----[Stage] Filter out all vertices that are outside of the base mat ")
	def filterer(v):# Note: used in Parsing loop instead
		minX = v.pos[0] < bounds[0][0]
		maxX = v.pos[0] > bounds[1][0]
		minY = v.pos[1] < bounds[0][1]
		maxY = v.pos[1] > bounds[1][1]
		minZ = v.pos[2] < bounds[0][2]
		maxZ = v.pos[2] > bounds[1][2]
		return not(minX or minY or minZ or maxX or maxY or maxZ)
	#verts = new_verts#list(filter(filterer, new_verts))

	print(f">Searching for peaking vertices of '{new_mat.name_jp}' going through the surface of '{base_mat.name_jp}'")
	if DEBUG: print(f">> Stats: moreinfo={moreinfo}, affectPMX={affectPMX}")

	print("\n----[Stage] Split the materials at the Z-Axis ")
	##** Split at Z Axis (X+ vs X-) :: Fixes X-Axis so that only one axis[Z] can be anything
	def filterPos(v): return v.pos[0] > 0
	def filterNeg(v): return v.pos[0] < 0
	old_pos = list(filter(filterPos, old_verts))
	old_neg = list(filter(filterNeg, old_verts))
	new_pos = list(filter(filterPos, new_verts))
	new_neg = list(filter(filterNeg, new_verts))
	if DEBUG: print(f"[D]> Old: {len(old_pos)}+{len(old_neg)}, New: {len(new_pos)}+{len(new_neg)}")
	
	##** Rebuild mapping back
	def remapper(list_of_verts):
		"""
		IN: List of verts
		OUT: List:
			  [0]: dict of { idx from POS, idx from [IN] }
			  [1]: dict of { idx from NEG, idx from [IN] }
		"""
		filter_map = [ ]
		filter_map_pos = []
		filter_map_neg = []
		for (idx,v) in enumerate(list_of_verts):
			if v.pos[0] > 0: filter_map_pos.append(idx)
			else: filter_map_neg.append(idx)
		tmp = range(len(filter_map_pos))
		filter_map.append(dict(zip(tmp, filter_map_pos)))
		tmp = range(len(filter_map_neg))
		filter_map.append(dict(zip(tmp, filter_map_neg)))
		return filter_map
	filter_map_old = remapper(old_verts)
	filter_map_new = remapper(new_verts)
	####################
	
	print("----[Stage] Calculate nearest_neighbors")
	###  For each Vert, find its closest match in the base
	
	that_dist = [[],[]]
	that_dist[0], that_list_pos = nearest_neighbors_scipy_KTree(old_pos, new_pos)
	that_dist[1], that_list_neg = nearest_neighbors_scipy_KTree(old_neg, new_neg)
	
	flag__usePos = len(that_list_pos) > 0
	flag__useNeg = len(that_list_neg) > 0
	## Stop if both are empty
	if not(flag__usePos or flag__useNeg):
		print(">> Unable to find any overlap between these two materials. Terminated scan.")
		return [f"-- No overlap found between '{new_mat.name_jp}' and '{base_mat.name_jp}'"]
	elif not(flag__usePos and flag__useNeg): ## Report if either is empty
		__tmp = "Left/Positive" if flag__useNeg else "Right/Negative"
		print(f">> {__tmp} side contains no overlap, so it will be ignored")
	
	###############

	##*** Rebuild a mapping between both
	print("----[Stage] Zip the respective nearest_neighbors together with the mapping indices")
	mapping_map = [[],[]]
	def connector(sign, idx, that, __old, __new):
#		__old_veclen    =        old_map[sign][that[idx]]
		__old_map_idx   = filter_map_old[sign][that[idx]]
		__old_do_filter = __old               [that[idx]]
#		__old_no_filter = old_verts           [__old_map_idx]
		
#		__new_veclen    =        new_map[sign]     [idx] -  that_dist[sign][idx]
		__new_map_idx   = filter_map_new[sign]     [idx]
		__new_do_filter = __new                    [idx]
#		__new_no_filter = verts               [__new_map_idx]
		
		mapping_map[sign].append({
			'dist': that_dist[sign][idx],
			'old': { 'vert':__old_do_filter, 'idx': __old_map_idx },
			'new': { 'vert':__new_do_filter, 'idx': __new_map_idx }
		})
	for i in range(0,len(that_list_pos)): connector(0, i, that_list_pos, old_pos, new_pos)
	for i in range(0,len(that_list_neg)): connector(1, i, that_list_neg, old_neg, new_neg)
	
	#for vert in <above verts>:
	##  :	Check if visible
	##  :	if False: continue
	##  :	If True: Add all faces that use this vertex as array into a list
	##  
	print("----[Stage] Find the faces that cut through the surface, or are connected to such.")
	if DEBUG: print("--[Note]: These Numbers represent the vector distance between the choosen vertices.")
	print("--[Note]: The status-% is only a full number if the hits are evenly dividable.")
	print("--[Note]: Read as: (Progress)% Left/Right Side: TimeStamp -- found: X vertices in 'tested'.")
	__results = []
	that_verts_list = []
	parts = 10
	left_size = 0
	def parsingMap(sign):
		cnt = 0
		__breaker = len(mapping_map[sign])/parts
		breaker = int(__breaker)
		rmd = len(mapping_map[sign]) - (breaker * parts)
		print("----[Sub] Parsing {} X-Axis: {} = {} x {} + {}".format("positive" if sign == 0 else "negative", len(mapping_map[sign]), parts, breaker, rmd))
		signText = "Left" if sign == 0 else "Right"
		for vert in mapping_map[sign]:
			idx     = vert['new']['idx']
			old_idx = vert['old']['idx']
			if DEBUG: print(vert['dist'])
			cnt += 1
			if cnt % breaker == 0:
				dt = str(datetime.datetime.now())
				print("---- {:7.2%} ({} side): ---- {} -- found: {} in {}".format((cnt / __breaker) / parts, signText, dt, len(that_verts_list) - left_size, cnt))
			if not filterer(pmx.verts[idx_verts[idx]]): continue
			#print(vert['dist'])
			if vert['dist'] > 0.15: continue
			
			#print("'{}' < '{}': idx={} {}".format(vert['old']['veclen'], vert['new']['veclen'], idx, pmx.verts[idx_verts[idx]].pos))
			#print("old vert: " + str(vert['old']['vert'].pos))
			#print("new vert: " + str(vert['new']['vert'].pos))
			
			isHidden = __find_sign_against_plane(pmx, old_vert=old_idx_verts[old_idx], new_vert=idx_verts[idx], mat_idx=mat_idx, moreinfo=moreinfo)
			if not isHidden:
				#print(">>>> VertIdx={}".format(idx_verts[idx]))
				that_verts_list.append(idx_verts[idx])

	if flag__usePos: parsingMap(0);
	left_size = len(that_verts_list);
	if flag__useNeg: parsingMap(1);
	
	__results.append("-- Found {} of {} vertices peaking through the surface ".format(len(that_verts_list), len(new_verts)))

	return move_verts_to_new_material(pmx, new_mat, that_verts_list, __results, options)

def move_verts_to_new_material(pmx, old_mat, that_verts_list, __results, options={}): ## Moves vertices & creates/extends the material
	"""
	:param pmx             [Pmx]
	:param old_mat         [PmxMaterial] The Material from which we cut off the vertices
	:param that_verts_list [list[int]]   The list of Vertex indices to relocate
	:param __results       [list[str]]   Log lines for #edit_log
	:param options         [dict]        Options passed through from previous method
	
	Options = {
		"affectPMX":   False for simulation mode; default is True
		"exceed":      Array of int (1 to 6) -- directions that ignore the bounding box
		"ask":         True to ask for material to store into, False to not ask
		:     -- Also allows a material index directly, but will fall back to [ask=True] if invalid. -1 for new
		"initial_hidden": When generating a new material, set True to hide it initially, else false.
	}
	"""
	import kkpmx_core as kklib
	import kkpmx_utils as util
	verbose = _verbose()
	affectPMX = options.get("affectPMX", True)
	if global_opt.get(OPT_YES, False):
		options["ask"] = False
		options["initial_hidden"] = True
	
	old_idx = util.find_mat(pmx, old_mat.name_jp)
	that_faces_list = kklib.from_vertices_get_faces(pmx, vert_arr=that_verts_list, mat_idx=old_idx, returnIdx=False, debug=False, trace=True)
	#>> dict { int, <class 'list', len=3> [ int, int, int ] }
	#util.write_json(that_faces_list, "moved_faces", False)
	################
	print("----[Stage] Delete the original faces")
	##  Flatten and uniquefy that_list into that_list_flat
	that_list_flat = list(sorted(set(list(that_faces_list)))) # list(reduce to idx) -> set(unique) -> list(cast)
	
	##  Delete the old faces and decrease the faces_ct of the old material
	__results.append("-- Moved {} of {} faces from '{}' to new material".format(len(that_list_flat), old_mat.faces_ct, old_mat.name_jp))
	
	if affectPMX:
		old_mat.faces_ct -= len(that_list_flat)
		for f in reversed(that_list_flat): pmx.faces.pop(f)

	########
	##  Add new material(s)
	print("----[Stage] Ask for a material to add the deleted faces to")
	
	add_mat = None
	ask = options.get("ask", False)
	def valid_value(x): return util.is_number(x) and not (int(x) < -1 or int(x) >= len(pmx.materials))
	value = -1
	
	if verbose: old_ask = copy.deepcopy(ask)
	
	if type(ask) != bool and not valid_value(ask):
		print(f">> Provided material index {value} is invalid.")
		ask = True
	elif type(ask) != bool: value = int(ask)
	
	if verbose: print(f"Ask: {old_ask}, IsNumber: {util.is_number(old_ask)}, Value: {value}")
	if DEBUG: print(f">> Provided is Valid: {valid_value(old_ask)} -> ask: {ask}")
	
	is_new_mat = True
	if _mirror() and mirDst in local_state:
		value = local_state[mirDst]; ask = False ##:[_feat_MirrorCut]
	
	if ask == True:
		print(f"- Please provide the target for the faces removed from '{old_mat.name_jp}'")
		value = int(core.MY_GENERAL_INPUT_FUNC(valid_value, "Id of the Material to append to (-1 for new)"))
	if value == -1:
		add_mat = copy.deepcopy(old_mat)
		add_mat.faces_ct = 0
		add_mat.name_jp = re.sub(r'( \(Instance\))+','',old_mat.name_jp)
		add_mat.name_en = util.translate_name(add_mat.name_jp, old_mat.name_en) + "_delta"
		add_mat.name_jp = add_mat.name_jp + "_delta"
		## Option: Normalize EN Name based on original slot (instead of name) -- duplicates based on JP name regardless of option
		#-- so that 'cf_m_bra_06_delta' or 'cf_m_bra_emblem_delta' are both 'cf_m_bra_delta'
		#-- Also store it as _delta_XXXXD (e.g. _delta_bra, _delta_body2, etc.)
		local_state[mirDst] = len(pmx.materials)
	else:
		is_new_mat = False
		add_mat = pmx.materials[value]
		if (value == old_idx): __results.append(f"--- Adding back to {add_mat.name_jp}({old_idx}) instead of creating new material")
		else: __results.append(f"--- Extended {add_mat.name_jp} instead of creating new material")
		

	########
	##  Add faces from that_list with respect to the material at the end
	if affectPMX:
		## New mats are added to the end, so we can simply append the moved faces
		if is_new_mat or value == len(pmx.materials) - 1:
			pmx.faces += list(that_faces_list.values())
		## When reusing the mat, we need to insert the faces at the correct position
		else:
			xx = [m.faces_ct for m in pmx.materials[:value]]
			insert_idx = sum(xx, pmx.materials[value].faces_ct) ## int of last index
			pmx.faces = pmx.faces[:insert_idx] + list(that_faces_list.values()) + pmx.faces[insert_idx:]
		
	##  Refresh target.faces_ct
	add_mat.faces_ct += len(that_list_flat)
	##  Add morph to fade in / out
	if is_new_mat:
		print("----[Stage] Create morphs to fade it in/out")
		items = []
		add_idx = len(pmx.materials)
		OPTION_2 = options.get("initial_hidden", None)
		if OPTION_2 == None or type(OPTION_2) != bool:
			OPTION_2 = util.ask_yes_no("Make material initial hidden(y) or visible(n)", "y")
		if (OPTION_2): ## initially hidden
			__results.append("--- Material is initially hidden")
			add_mat.alpha = 0
			kklib.__append_itemmorph_add(items, add_idx)
			add_mat.edgealpha = 0
		else:
			__results.append("--- Material is initially visible")
			add_mat.alpha = 1
			kklib.__append_itemmorph_mul(items, add_idx)
		##### If an material of that name already exists, add "Hide" to it
		if affectPMX:
			add_to_morph_hide(pmx, old_mat.name_jp, add_idx, __results)
			## Rudimentary Acc: Hide from Acc and BD-Suit
			if re.search(kklib.rgxAcc, old_mat.name_jp):
				add_to_morph_hide(pmx, "Hide Acc", add_idx, __results)
				add_to_morph_hide(pmx, "BD-Suit", add_idx, __results)
			## Rudimentary Body Part: Show in clothes and BD-Suit
			elif re.search(kklib.rgxBase, old_mat.name_jp):
				if (old_mat.name_jp == util.find_bodyname(pmx)):
					add_to_morph_show(pmx, "Hide Non-Acc", add_idx, __results)
				add_to_morph_show(pmx, "BD-Suit", add_idx, __results)
			## Anything else: Hide from Clothes and BD-Suit
			else:
				add_to_morph_hide(pmx, "Hide Non-Acc", add_idx, __results)
				add_to_morph_hide(pmx, "BD-Suit", add_idx, __results)
		__results.append("-- Added one new material and one new morph")
	
	####
	if affectPMX:
		if is_new_mat:
			pmx.materials.append(add_mat)
			pmx.morphs.append(pmxstruct.PmxMorph(add_mat.name_jp, add_mat.name_en, 4, 8, items))
			util.add_to_facials(pmx, add_mat.name_jp)
		print("--------\n Results:\n" + "\n".join(__results))
		return __results
	else:
		__results.append("-- As this was just a simulation, no model was written")
		print("\n".join(__results))
		return False
################
def cut_out_box_from_material(pmx, new_bounds, mat_idx=None):
	moreinfo = False
	from kkpmx_core import ask_for_material, from_material_get_faces, from_faces_get_vertices
	
	if _mirror(): mat_idx = local_state.get(mirMat, mat_idx) ##:[_feat_MirrorCut]
	if mat_idx is None:
		mat_idx = ask_for_material(pmx, ": Material to cut vertices off from", default="cf_m_body", returnIdx=True)
		local_state[mirMat] = mat_idx
	base_mat = pmx.materials[mat_idx]
	##  Their verts
	faces = from_material_get_faces(pmx, mat_idx, False)
	old_verts = from_faces_get_vertices(pmx, faces, False)
	idx_verts = from_faces_get_vertices(pmx, faces, True)
	###
	__results = []
	###
	def formatBox(box): return (f"[ {box[0]:19.15f}, {box[1]:19.15f}, {box[2]:19.15f}]")
	bounds = get_bounding_box(pmx, base_mat, old_verts, moreinfo=moreinfo)
	def extendBounds(name, i1, i2, minmax):
		if new_bounds.__contains__(name):
			try: ## box should not exceed original material bounds
				bounds[i1][i2] = minmax(float(new_bounds[name]), bounds[i1][i2])
			except: pass
	#print("-- Bounding Box (override)")
	extendBounds("minX",0,0,max)
	extendBounds("minY",0,1,max)
	extendBounds("minZ",0,2,max)
	extendBounds("maxX",1,0,min)
	extendBounds("maxY",1,1,min)
	extendBounds("maxZ",1,2,min)
	print(formatBox(bounds[0]))
	print(formatBox(bounds[1]))
	__results.append("Created cutting box around")
	__results.append("- Min: " + formatBox(bounds[0]))
	__results.append("- Max: " + formatBox(bounds[1]))
	###
	print("----[Stage] Retrieve all affected vertices")
	def filterer(idx):
		v = pmx.verts[idx]
		minX = v.pos[0] < bounds[0][0]
		maxX = v.pos[0] > bounds[1][0]
		minY = v.pos[1] < bounds[0][1]
		maxY = v.pos[1] > bounds[1][1]
		minZ = v.pos[2] < bounds[0][2]
		maxZ = v.pos[2] > bounds[1][2]
		return not(minX or minY or minZ or maxX or maxY or maxZ)
	that_verts_list = list(filter(filterer, idx_verts))
	#----
	print("----[Stage] Collect affected faces")
	
	options = {
		"affectPMX": True,
		"ask": True,
	}
	return move_verts_to_new_material(pmx, base_mat, that_verts_list, __results, options)

def __endCut(pmx, input_filename_pmx, logs):
	import kkpmx_core as kklib
	from _dispframe_fix import dispframe_fix
	
	print("->> Making sure display isn't too big <<-")
	print("->>> Will add all no-where added morphs first, so don't worry about the high number")
	dispframe_fix(pmx, moreinfo=_verbose())
	print("--- >>  << ---")
	
	input_filename_pmx = re.sub("_cutScan\d*", "", input_filename_pmx)
	return kklib.end(pmx, input_filename_pmx, "_cutScan", log_line=logs)


##################################

def get_bounding_box(pmx, mat=None, vertices=None, moreinfo=False):
	"""
	:param pmx      [Pmx]
	:param mat      [Union(int, PmxMaterial, None)] The material to generate the bounding box from.
	:param vertices [Optional(List(PmxVertex))] Shortcut if already retrieved the vertices
	"""
	from kkpmx_core import find_mat, from_material_get_faces, from_faces_get_vertices
	if vertices is None:
		##  Collect all verts
		mat_idx = mat
		if type(mat_idx) is not int: mat_idx = find_mat(pmx, mat.name_jp)
		faces = from_material_get_faces(pmx, mat_idx, returnIdx=False)
		vertices = from_faces_get_vertices(pmx, faces, returnIdx=False, moreinfo=moreinfo)
	##  sort by Y- X- -> Y+ X+ 
	__forX = sorted(vertices, key=lambda v: (v.pos[0], v.pos[1], v.pos[2]))
	__forY = sorted(vertices, key=lambda v: (v.pos[1], v.pos[2], v.pos[0]))
	__forZ = sorted(vertices, key=lambda v: (v.pos[2], v.pos[0], v.pos[1]))
	
	##  Mark max min bounds
	bounds = [ ## Face towards X(+ left, - right), Y+, Z- \\ Butt towards: X +-, Y-, Z+
		[ __forX[0].pos[0],  __forY[0].pos[1],  __forZ[0].pos[2], ], ## Lowest  (X- Y Z+) --> Make Z big instead of Bounding
		[ __forX[-1].pos[0], __forY[-1].pos[1], __forZ[-1].pos[2], ] ## Highest (X+ Y Z-) --> Make Z big instead of Bounding
	]
	return bounds

def add_to_morph_hide(pmx, name, add_idx, __results):
	from kkpmx_core import find_morph, __append_itemmorph_sub
	exist_morph = find_morph(pmx, name, False)
	if exist_morph != -1:
		exist_morph = pmx.morphs[exist_morph]
		__append_itemmorph_sub(exist_morph.items, add_idx)
		__results.append("-- Extended morph '{}' to hide the new material.".format(exist_morph.name_jp))

def add_to_morph_show(pmx, name, add_idx, __results):
	from kkpmx_core import find_morph, __append_itemmorph_add
	exist_morph = find_morph(pmx, name, False)
	if exist_morph != -1:
		exist_morph = pmx.morphs[exist_morph]
		__append_itemmorph_add(exist_morph.items, add_idx)
		__results.append("-- Extended morph '{}' to show the new material.".format(exist_morph.name_jp))

##################################
## https://stackoverflow.com/questions/48312205/find-the-k-nearest-neighbours-of-a-point-in-3d-space-with-python-numpy?noredirect=1&lq=1
## https://stackoverflow.com/questions/54114728/finding-nearest-neighbor-for-python-numpy-ndarray-in-3d-space
def nearest_neighbors_scipy_KTree(__data, __sample, doPrint=False):
	"""
	Both arguments are 'List[PmxVertex]'
	Return: Tuple[np.ndarray[np.float64], np.ndarray[numpy.int64]]
	"""
	import numpy as np
	from scipy.spatial import KDTree
	if len(__data) == 0 or len(__sample) == 0: return ([], [])
	
	limit = 5
	data = list(map(lambda v: v.pos, __data))     ## Base
	sample = list(map(lambda v: v.pos, __sample)) ## Find nearest_neighbor in base
	
	kdtree = KDTree(data)
	dist, points = kdtree.query(sample) ## k=2 gives the best 2 neighbours for [sample]
	if doPrint:
		zipped = list(zip(dist,points))
		print("---- Org")
		print("\n".join([str(i) for i in data[0:limit]]))
		print("---- Against")
		print("\n".join([str(i) for i in sample[0:limit]]))
		print("---- KDTree")
		print("\n".join([str(i) for i in zipped[0:limit]]))
	return (dist, points)

## https://docs.sympy.org/latest/modules/geometry/plane.html
## https://stackoverflow.com/questions/15688232/check-which-side-of-a-plane-points-are-on
__plane_cache = {}
def __find_sign_against_plane(pmx, old_vert, new_vert, mat_idx, moreinfo):
	"""
	Find all faces that contain [old_vert] and look if [new_vert] is in front of at least one of them.
	"""
	from kkpmx_core import from_vertices_get_faces
	from sympy import Plane
	new_point = pmx.verts[new_vert].pos
	if moreinfo: print("Find pos of {} against planes around {}".format(new_vert, old_vert))
	faces = from_vertices_get_faces(pmx, vert_arr=[old_vert], mat_idx=mat_idx, returnIdx=False, debug=False, point=True)
	
	def getFromCache(face_idx):
		if __plane_cache.__contains__(face_idx) == False:
			face = faces[face_idx]
			__plane_cache[face_idx] = Plane(tuple(face[0].pos), tuple(face[1].pos), tuple(face[2].pos))
		return __plane_cache[face_idx]
	for face in faces:
		plane = getFromCache(face)
		if plane.equation(x=new_point[0], y=new_point[1], z=new_point[2]) > 0:
			if moreinfo: print(">> Point is on side B (visible)")
			return False
	if moreinfo: print(">> Point is on side A (hidden)")
	return True

