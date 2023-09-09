# Cazoo - 2022-05-13
# This code is free to use, but I cannot be held responsible for damages that it may or may not cause.
#####################
from typing import List, Union, Tuple
import re, os, json, copy  ## copy.deepcopy

import kkpmx_core as kklib
import kkpmx_utils as util
from kkpmx_utils import find_bone, find_mat, find_disp, find_morph, find_rigid, __typePrinter
import kkpmx_rigging as kkrig

try:
	import nuthouse01_core as core
	import nuthouse01_pmx_parser as pmxlib
	import nuthouse01_pmx_struct as pmxstruct
	import _prune_unused_bones as bonelib
	import morph_scale
except ImportError as eee:
	print(eee.__class__.__name__, eee)
	print("ERROR: failed to import some of the necessary files, all my scripts must be together in the same folder!")
	print("...press ENTER to exit...")
	input()
	exit()
	core = pmxlib = pmxstruct = morph_scale = bonelib = None


## Local "moreinfo" -- See [ANNIV List]
DEBUG = util.DEBUG or False
local_state = {}
def _verbose(): return local_state.get("moreinfo", False)
def _univrm(): return local_state.get("univrm", False)

c_TrackVoiceName = "TrackVoice"
c_AuxMorphName   = "AuxMorphs"
cName_extraBones = "ExtraBones"
cName_morebones  = "morebones"
c_moremorphs     = "moremorphs" # By dispframe_fix

#--- [Text]: How it appears in the exported morph name
#--- [Morph]: The name how it should be displayed in MMD [== name_en]
#--- [KK Name]: The Display name in the respective dropdown in KK
#--- [EN]: The segment for the VertexMorph (maybe only JP / EN ?)
#--- [JP]: "name_jp" of the morph. Should reflect the phrase most commonly used in dance motions.
prefixes = [ # ["Text", "", "", "EN"]
	## Combos for convenience
	["eye"        , "",     "", "eye"],
	["kuti"       , "",     "", "mouth|teeth|canine|tongue"],
	["mayuge"     , "",     "", "eyebrow"],
	####
	["eye_face"   , "",     "", "eyes"],
	["kuti_face"  , "",     "", "mouth"],
	["eye_nose"   , "[N] ", "", "eye.nose"],
	["kuti_nose"  , "[N] ", "", "mouth.nose"],
	["eye_siroL"  , "[W] ", "", "eye.siroL"],
	["eye_siroR"  , "[W] ", "", "eye.siroR"],
	["eye_line_u" , "[U] ", "", "eyeline_u"],
	["eye_line_l" , "[L] ", "", "eyeline_l"],
#	["eye_naL"    , "", "", ""],
#	["eye_naM"    , "", "", ""],
#	["eye_naS"    , "", "", ""],
	["kuti_ha"    , "[Te] ", "", "teeth"],
	["kuti_yaeba" , "[T2] ", "", "canine"],
	["kuti_sita"  , "[Tg] ", "", "tongue"],
	["mayuge"     , "",      "", "brow"],
	]
infixes  = [ # ["Text", "Morph", "KK Name", ".EN", "JP", ]		\t"\t, "\t
	["_a"         , "'A'"          ,  ".." 			, ".a"			, "あ"		],
	["_e"         , "'E'"          ,  ".." 			, ".e"			, "え"		],
	["_i"         , "'I'"          ,  ".." 			, ".i"			, "い"		],
	["_o"         , "'O'"          ,  ".." 			, ".o"			, "お"		],
	["_u"         , "'U'"          ,  ".." 			, ".u"			, "う"		],
	["_n"         , "'N'"          ,  ".." 			, ".n"			, "ん"		],
	# [Infix]        [My name]       [KK Name/TL]    [EN Infix] []
	## Mayuge only[B]	
	##### All[X]
	##### Eye or Mayuge only[E]
	##### Mouth only[M]
	["_akire"     , "Flustered"    ,  "Flustered"   , ".zzz", 		""   		],#[M] あせり		Haste
	["_aseri"     , "Impatient"    ,  ""            , ".zzz", 		""   		],#[X] あせり		Haste
	["_bisyou"    , "Grin"         ,  "Grin"        , ".zzz", 		""   		],#[X] びしょう		Smile
	["_def"       , "Default"      ,  "default"     , ".default",	""   		],#[X] デフォルト	
	["_doki"      , "Excited"      ,  ""            , ".zzz",		""   		],#[M] どき		
	["_doya"      , "Smug"         ,  "Smug"        , ".zzz",		""   		],#[X] どや		
	["_egao"      , "Smiling"      ,  "Smiling"     , ".smile",		""   		],#[X] えがお		
	["_gag"       , "xxx"          ,  ""            , ".zzz",		""   		],#[E] がが		< Circle Eyes >
	["_gyu"       , "xxx"          ,  ""            , ".zzz",		""   		],#[E] ぎゅ		< Blank Eyes >
	["_gyul"      , "xxx"          ,  ""            , ".zzz",		""   		],#[E] 			
	["_gyur"      , "xxx"          ,  ""            , ".zzz",		""   		],#[E] 			
	["_gimo"      , "Doubt"        ,  ""            , ".zzz",		""   		],#[B] 			
	["_huan"      , "Confused"     ,  ""            , ".zzz",		""   		],#[B] 			
	["_human"     , "Pouting"      ,  "Grumbling"   , ".zzz",		""   		],#[M] ふまん		
	["_ikari"     , "Angry"        ,  "Angry"       , ".zzz",		""   		],#[X] いかり		
	["_kanasi"    , "Sad 2"        ,  "Sad 2"       , ".zzz",		""   		],#[E] かなし		
	["_keno"      , "Disgust"      ,  "Disgust"     , ".zzz",		"気の"		   ],#[X] けの		
	["_kisu"      , "Kiss"         ,  "Kiss"        , ".zzz",		""   		],#[M] きす		
	["_koma"      , "Concerned"    ,  ""            , ".zzz",		""   		],#[B] こま		
	["_komaru"    , "Concerned"    ,  "Concerned"   , ".zzz",		""   		],#[E] こまる		
	["_kurusi"    , "In Pain"      ,  "In Pain"     , ".zzz",		""   		],#[E] くるし		
	["_kuwae"     , "Sucking"      ,  "Sucking"     , ".zzz",		""   		],#[M] くわえ		
	["_mogu"      , "Chewing"      ,  ""            , ".zzz",		""   		],#[M]
	["_naki"      , "Crying"       ,  "Crying"      , ".zzz",		""   		],#[E] なき		
	["_name"      , "Licking"      ,  "Licking"     , ".zzz",		""   		],#[M] なめ		
	["_neko"      , "OwO"          ,  ""            , ".zzz",		""   		],#[M]
	["_niko"      , "NikoNikoNii"  ,  ""            , ".zzz",		""   		],#[M]
	["_odoro"     , "Surprised"    ,  "Surprised"   , ".zzz",		""   		],#[X] おどろ		
	["_oko"       , "Angry"        ,  ""            , ".zzz",		""   		],#[B] 			
	["_pero"      , "Bleh"         ,  "Bleh"        , ".zzz",		""   		],#[M] ぺろ		
	["_rakutan"   , "Upset"        ,  "Upset"       , ".zzz",		""   		],#[E] らくたん	
	["_sabisi"    , "Lonely"       ,  "Lonely"      , ".zzz",		""   		],#[M] さびし		
	["_san"       , "Triangle"     ,  ""            , ".zzz",		""   		],#[M]
	["_setunai"   , "Sad"          ,  "Sad"         , ".zzz",		""   		],#[E] せつない	
	["_sian"      , "Thoughtful"   ,  "Thoughtful"  , ".zzz",		""   		],#[E] しあん		
	["_sinken"    , "Serious"      ,  "Serious"     , ".zzz",		""   		],#[X] しんけん	
	["_tabe"      , "Eating"       ,  ""            , ".zzz",		""   		],#[M]
	["_tere"      , "Shy"          ,  "Shy"         , ".zzz",		""   		],#[E] てれ		
	["_tmara"     , "Bored"        ,  ""            , ".zzz",		""   		],#[B] 			
	["_tumara"    , "Bored"        ,  "Bored"       , ".zzz",		""   		],#[E] つまら		
	["_uresi"     , "Happy"        ,  "Happy"       , ".zzz",		""   		],#[M] うれし		
	["_winkl"     , "Wink L"       ,  "Wink L"      , ".zzz",		""   		],#[E] うぃんく		
	["_winkr"     , "Wink R"       ,  "Wink R"      , ".zzz",		""   		],#[E] 			
]; infixes_2 = [
	["_doki_s"    , ""             ,  ""            , ".zzz",		""   		],#[X] 			
	["_doki_ss"   , ""             ,  ""            , ".zzz",		""   		],#[X] 			
	["_gyu02"     , ""             ,  ""            , ".zzz",		""   		],#[E] 			
	["_gyul02"    , ""             ,  ""            , ".zzz",		""   		],#[E] 			
	["_ikari02"   , ""             ,  ""            , ".zzz",		""   		],#[X] 			
	["_name02"    , ""             ,  ""            , ".zzz",		""   		],#[M] 			
	["_odoro_s"   , ""             ,  ""            , ".zzz",		""   		],#[X] 			
	["_sianL"     , ""             ,  ""            , ".zzz",		""   		],#[B] 			
	["_sianR"     , ""             ,  ""            , ".zzz",		""   		],#[B] 			
	["_sinken02"  , ""             ,  ""            , ".zzz",		""   		],#[X] 			
	["_sinken03"  , ""             ,  ""            , ".zzz",		""   		],#[X] 			
	["_uresi_s"   , "Happy"        ,  "Happy"       , ".zzz",		""   		],#[M] 			
	["_uresi_ss"  , "Happy"        ,  "Happy"       , ".zzz",		""   		],#[M] 			
	]
suffixes = [ # ["Text", "Morph", "", "EN"]
	["_op"    , ""            , "", ".open"],
	["_cl"    , " (closed)"   , "", ".close"],
	["_s"     , " (small)"    , "", ".s"],
	#["_s_op"  , " (small)"    , "", ".s.op"],
	["_ss"    , " (small 2)"  , "", ".s2"],
	["_l"     , " (big)"      , "", ".big"],
	["02"     , " 2"          , "", ".2"],
	["03"     , " 3"          , "", ".3"],
	#["02_op"  , " 2"          , "", ".2.op"],
#	["l"   , " (Left)"     , "", ".left"],
#	["r"   , " (Right)"    , "", ".right"],
#	[""    , ""],
	]
########
def genGroupItem(pmx, arr): ## only existing morphs are added
	lst = [find_morph(pmx, elem[0], False) for elem in arr]
	return [pmxstruct.PmxMorphItemGroup(lst[idx], elem[1]) for (idx,elem) in enumerate(arr) if lst[idx] != -1]
def replaceItems(pmx, name, arr): ## Does nothing if [name] is not found
	morph = find_morph(pmx, name, False)
	if morph != -1: pmx.morphs[morph].items = genGroupItem(pmx, arr)
def translateItem(name, useEN=False): ## Always input the untranslated name
	parts = re.search("(\w+)\.[a-z]+\d+(_[a-z]+)(\w+?)(_\w+)?$", name) ## \2\t\1 \3
	if not parts: return name
	if len(parts.groups()) < 3: return name
	dest = ""
	arrIdx = 1 if useEN else 3
	## Get Prefix
	m = parts.group(1)
	arr = [x[arrIdx] for x in prefixes if x[0] == m]
	dest += arr[0] if len(arr) > 0 else m
	## Get Infix
	m = parts.group(2)
	arr = [x[arrIdx] for x in infixes if x[0] == m]
	tmp = arr[0] if len(arr) > 0 else m
	tmp = ("."+m[1:]) if tmp == ".zzz" else tmp
	dest += tmp
	## Get Suffix
	m = parts.group(3)
	arr = [x[arrIdx] for x in suffixes if x[0] == m]
	dest += arr[0] if len(arr) > 0 else m
	if (parts.group(4)):
		m = parts.group(4)
		arr = [x[arrIdx] for x in suffixes if x[0] == m]
		dest += arr[0] if len(arr) > 0 else m
	
	if len(dest) == 0: return name
	if dest == parts.group(1) + parts.group(2) + parts.group(3): return name
	return dest

## Create or find a given morph and write the given fields
def addOrReplace(pmx, name_jp:str, name_en:str, panel:int, items:List[Tuple[str, float]], morphtype=0):# > PMX, "", "", int, [ ("", 0.0) ]
	""" IN: PMX, str, str, int, List<Tuple<str, float>> or PmxMorph** ==> OUT: void """
	# if exist: get from store & set Idx \\ else: create new, append, set Idx
	idx = find_morph(pmx, name_jp, False)
	if idx == -1:
		idx = len(pmx.morphs)
		pmx.morphs.append(pmxstruct.PmxMorph(name_jp, "", 0, 0, []))
	morph = pmx.morphs[idx]
	morph.name_en = name_en
	morph.panel   = panel
	if morphtype == 0:
		morph.items   = genGroupItem(pmx, items)
	else:
		morph.morphtype = morphtype
		morph.items     = items

## Returns the name by which this morph can be found, or ""
def find_one_morph(_morphs, name, value=None) -> Union[str, Tuple[str, float]]:
	"""
	IN: List[str], str, float=None
	OUT(value=None): str
	OUT(value=float): Tuple[str, float]
	
	OUT.str may be "" if IN.name is not a Morph
	"""
	ret = ["", value]
	dest = translateItem(name)
	if name in _morphs: ret[0] = name
	elif dest in _morphs: ret[0] = dest
	if value is None: return ret[0]
	return tuple(ret)

####
### Remark: Throw out all of the "translated" matches again
def find_all_morphs(_morphs, prefix=None, infix=None, suffix=None, value=None, isVocal=False, exclude=None) -> Union[List[str], List[Tuple[str, float]]]:
	"""
	OUT(empty):       []
	OUT(value==None): List[str]
	OUT(value!=None): List[Tuple[str, float]]
	"""
	verbose = _verbose()
	## Get all morphs
	morphs = copy.copy(_morphs)
	if verbose: print(f"\nFind all morphs called <{prefix}:{infix}:{suffix}>")
	## Reduce by prefixes, if any
	if prefix is not None: ## Only match at start
		pat = [x[3] for x in prefixes if x[0] == prefix]
		if len(pat) == 0: raise Exception(f"Prefix {prefix} is not defined!")
		r = re.compile(f"{prefix}|{pat[0]}")
		morphs = [m for m in morphs if r.match(m)] ## Only match at start
	## Reduce by infixes, if any
	if infix is not None:
		noNum = False; exact = False
		if infix[-1] == "$": noNum = True; infix = infix[:-1]
		if infix[-1] == "%": exact = True; infix = infix[:-1]
		pat = [x[3] for x in infixes if x[0] == infix]
		if len(pat) == 0: raise Exception(f"Infix {infix} is not defined!")
		if exact:   r = re.compile(re.escape(infix) + "(_op|_cl)|" + re.escape(pat[0]) + "(_|$)")
		elif noNum: r = re.compile(re.escape(infix) + "_|" + re.escape(pat[0]) + "(_|$)")
		else:       r = re.compile(re.escape(infix) + "|" + re.escape(pat[0]) + "(\.|$)")
		#print(f">>[Infix]: " + re.escape(infix) + "|" + re.escape(pat[0]))
		morphs = [m for m in morphs if r.search(m)]
	## Reduce by suffixes, if any
	if suffix is not None: ## Only match at end
		if type(suffix).__name__ == "str": suffix = [suffix, None]
		(_suffix, oc) = suffix
		pat = [x[3] for x in suffixes if x[0] == _suffix]
		if oc is not None: _suffix = oc if _suffix is None else _suffix+oc
		elif len(pat) == 0: raise Exception(f"_suffix {_suffix} is not defined!")
		if oc is None: _suffix += "(_op|_cl)"
		# The single length vocals cause problems, so combine with the infix
		if isVocal: _suffix = infix + _suffix
		r = re.compile(f"{_suffix}$")
		morphs = [m for m in morphs if r.search(m)]
	if exclude:
		r2 = re.compile(exclude)
		morphs = [x for x in filter(lambda x: not r2.search(x), morphs)]
	if verbose: print(f">> " + str(morphs))
	if len(morphs) == 0: return []
	if value is not None: return [(m, value) for m in morphs]
	return morphs
	
def replace_one_morph(_morphs, text, value=None):
	data = []
	for m in _morphs:
		if text in m[0]: data.append((m[0], value))
		else: data.append(m)
	return data

def generateAlias(pmx, name, alias, alias_en):
	if find_morph(pmx, alias, False) != -1: return False
	m_idx = find_morph(pmx, name, True)
	if m_idx == -1: return False
	morph = copy.deepcopy(pmx.morphs[m_idx])
	morph.name_jp = alias
	morph.name_en = alias_en
	pmx.morphs.append(morph)

###########################
def emotionalize(pmx, input_file_name: str, write_model = True, moreinfo = False):
	"""
Utilizes the emotion morphs extracted from KK to construct TDA morphs.
Will override existing morphs, which allows "repairing" cursed Impact-Values.

[Option]:
-- Impact-Value: Between 0%-100%(=0..1), how strong the morphs should pull on the face.
-- -- Default is 0.66, but 0.75 is also common.

[Side-effects]:
-- Will rerun Morph-Validation, which ensures that [Display] has less than 250 morphs.
-- All surplus and otherwise ungrouped morphs are then added into [moremorphs].

[Output]: PMX file '[modelname]_emote.pmx'
"""
	local_state["moreinfo"] = moreinfo or DEBUG
	local_state["univrm"] = util.is_univrm()
	####
	if not _univrm() and find_mat(pmx, "cf_m_face_00", True) == -1:
		print(">> Skipping because model has no standard face texture.")
		return input_file_name
	####
	CH__TDA = 0; CH__VRM = 1;
	choices = [
		("TDA           -- Try to assemble morphs resembling TDA", CH__TDA, add_TDA),
		#("UniVRM        -- Categorize morphs on imported model ", CH__VRM, sort_morphs_into_frames),
		]
	choice = CH__TDA#util.ask_choices("Select the target collection", choices)
	if _univrm(): choice = CH__VRM
	####
	putAuxIntoGroup(pmx)
	choices[choice][2](pmx);
	sort_bones_into_frames(pmx)
	sort_morphs(pmx)
	
	from _dispframe_fix import dispframe_fix
	if moreinfo:
		print("->> Making sure display isn't too big <<-")
		print("->>> Will add all no-where added morphs first, so don't worry about the high number")
	idx = find_disp(pmx, c_moremorphs, False)
	if idx != -1: pmx.frames.remove(pmx.frames[idx])
	dispframe_fix(pmx, moreinfo=moreinfo)
	if moreinfo: print("--- >>  << ---")
	
	####--- Find a convenience way to sort all [KK morph segments] below the groups
	
	_results = []#["Mode: " + str(choice)]
	if "eyeOpenness" in local_state: _results += ["EyeSlider Value: " + str(local_state["eyeOpenness"])]
	cleanup_invalid(pmx)
	
	return kklib.end(pmx if write_model else None, input_file_name, "_emote", _results)

def add_TDA(pmx): ## Note: Add specific morphs as empty placeholder (JP, EN="Placeholder", it=[])
	addOrReplaceEye   = lambda jp,en,it: addOrReplace(pmx, jp, en, 2, it)
	addOrReplaceMouth = lambda jp,en,it: addOrReplace(pmx, jp, en, 3, it)
	addOrReplaceBrow  = lambda jp,en,it: addOrReplace(pmx, jp, en, 1, it)
	addOrReplaceOther = lambda jp,en,it: addOrReplace(pmx, jp, en, 4, it)
	## Avoid excessive collection of morphs again and again
	morphs = [m.name_jp for m in pmx.morphs]
	### Eyes ----------------------------
	def eyes():
		#まばたき			mabataki			Blink			C	Close eyes (Up full = 100% 0%)
		#笑い			warai				Laughter		C	Close eyes (Lids meet at center = 50 50)
		#ウィンク			winku				Wink			CO	Close left (5050)
		#ウィンク右			winku R				Wink R			OC	Close right (5050)
		#ウィンク２			Winku 2				Wink 2			CO	Close left (100 0)
		#ｳｨﾝｸ２右			Winku 2 R			Wink 2 R		OC	Close right (0 100)
		#なごみ			nagomi				Softing			C	Close both (80 20) – Hor eyes
		#はぅ				ha					<emphasis>		C	">.<" – Upper brow from inside
		#びっくり			bikkuri				Surprise		O	“0.0” – Lids go outwards
		#じと目			jitome				Disgust			O	Upper goes 33% (is hor)
		#ｷﾘｯ			kiri				“click”			O	Inner Angle pulled down
		#はちゅ目			hachiyume			Hachu eyes		*	“White with fuzzy black border”
		#はちゅ目縦潰れ		… tatetsubure		Vert. Squint	*	: ^ Squint Vert
		#はちゅ目横潰れ		… yokotsubure		Hort Squint		*	: ^ Squint Hor
		pass
	# def: Search all morphs with "_winkl" in their name -- Could also search for the alternative name in case it was renamed
	eyeOpenness = util.ask_number("Set Impact Value for Eye-Morphs", 0.00, 1.00, 0.66)
	local_state["eyeOpenness"] = eyeOpenness
	
	find_all_morphs_eyes = lambda prefix,infix,suffix,value=eyeOpenness: find_all_morphs(morphs, prefix, infix, suffix, value, exclude="_siro[LR]")
	
	addOrReplaceEye("hitomi-small", "hitomi-small",  [
			find_one_morph(morphs, "hitomiX-small", 1),
			find_one_morph(morphs, "hitomiY-small", 1),
			])
	
	## Suggestion: Add (Face[Smile / Blink]=0.125), respective, and set Sirome to 0.66
	# L = Lips \\ Z = Tongue \\ T = Teeth \\ X = Mouth Cavity \\ MC = Mouth Corners
	# -- Tongue moves with jaw when Mouth is open
	
	#-# まばたき			mabataki			Blink			C	Close eyes (Up full = 100% 0%)
	#-# 笑い				warai				Laughter		C	Close eyes (Lids meet at center = 50 50)
	addOrReplaceEye("まばたき",   "Blink",  find_all_morphs_eyes("eye", "_def", [None,"_cl"]) )
	addOrReplaceEye("笑い",   "Smile",    find_all_morphs_eyes("eye", "_egao", [None,"_cl"]) )
	#-# ウィンク			winku				Wink			CO	Close left (5050)
	#-# ウィンク右			winku R				Wink R			OC	Close right (5050)
	addOrReplaceEye("ウィンク",   "Wink",    find_all_morphs_eyes("eye", "_winkl$", None) )
	addOrReplaceEye("ウィンク右", "Wink R",  find_all_morphs_eyes("eye", "_winkr$", None) )
	
	#-# ウィンク２			Winku 2				Wink 2			CO	Close left (100 0)
	#-# ｳｨﾝｸ２右			Winku 2 R			Wink 2 R		OC	Close right (0 100)
	if generateWink(pmx):
		morphs = [m.name_jp for m in pmx.morphs]
		addOrReplaceEye("ウィンク２", "Wink 2", [
			find_one_morph(morphs, "eye_face.f00_winkl02_op", eyeOpenness),
			find_one_morph(morphs, "eye_nose.nl00_winkl_op", eyeOpenness),
			#find_one_morph(morphs, "eye_siroL.sL00_def_cl", eyeOpenness),
			find_one_morph(morphs, "eye_line_u.elu00_winkl02_cl", eyeOpenness),
			find_one_morph(morphs, "eye_line_l.ell00_winkl02_cl", eyeOpenness),
			])
		addOrReplaceEye("ｳｨﾝｸ２右", "Wink 2 R", [
			find_one_morph(morphs, "eye_face.f00_winkr02_op", eyeOpenness),
			find_one_morph(morphs, "eye_nose.nl00_winkr_op", eyeOpenness),
			#find_one_morph(morphs, "eye_siroR.sR00_def_cl", eyeOpenness),
			find_one_morph(morphs, "eye_line_u.elu00_winkr02_cl", eyeOpenness),
			find_one_morph(morphs, "eye_line_l.ell00_winkr02_cl", eyeOpenness),
			])
	
	
	#-# なごみ			nagomi				Softing			C	Close both (80 20) – Hor eyes
	#addOrReplaceEye("なごみ", "...",  find_all_morphs(morphs, "eye", "_winkr", None, 0.8) )
	#-# はぅ				ha					<emphasis>		C	">.<" – Upper brow from inside
	#addOrReplaceEye("<ha>", "...",  find_all_morphs(morphs, "eye", "_winkr", None, 0.8) )
	#-# びっくり			bikkuri				Surprise		O	“0.0” – Lids go outwards
	#-# じと目			jitome				Disgust			O	Upper goes 33% (is hor)
	
	#-- Slightly inwards slanted eyes
	addOrReplaceEye("じと目", "Disgust",  find_all_morphs_eyes("eye", "_keno", None) )
	#-- Wide open eyes
	addOrReplaceEye("! あせり", "BigEyes",  find_all_morphs_eyes("eye", "_aseri", None) )
	addOrReplaceEye("! 切ない", "Sad (Eyes)",  find_all_morphs(morphs, "eye", "_setunai", None, 0.75) ) # 切ない = Pained
	
	#-# ｷﾘｯ				kiri				“click”			O	Inner Angle pulled down
	#-# はちゅ目			hachiyume			Hachu eyes		*	“White with fuzzy black border”
	#-# はちゅ目縦潰れ		… tatetsubure		Vert. Squint	*	: ^ Squint Vert
	#-# はちゅ目横潰れ		… yokotsubure		Hort Squint		*	: ^ Squint Hor
	#############
	def mouth():
		#	あ				a					Say "A"			O	Open L+T for A
		#	い				I					Say "I"			*	Wide Op L for I
		#	う				u					Say "U"			O	Open L+T for U
		#	え				e					Say "E"			O	Open L+T for E
		#	お				o					Say "O"			O	Open L+T for O
		#	あ２				a2					Say "A" (big)	O	Open WIDE for A
		#	ん				n					Say “N”			C	MC for N
		#	▲				*					°▲°				O	L as-such, X infront of T+Z
		#	∧				*					°∧°				C	L as-such – T open, Z pulls back
		#	□				*					°□°				O	Same as ▲
		#	ワ				*					Say “Wa”		O	Looks like :D with barely T
		#	ω				*					[Form]			C	L into shape
		#	ω□				*									O	L into shape, T behind L
		#	にやり			niyari				Grin			C	M widens (flat smile)
		#	にやり２			Niyari 2			Grin 2			C	Left MC high up
		#	にっこり			nikkori				Smirk			C	・‿・ (almost creepy smile)
		#	ぺろっ			pero				Lick			~~	T+L barely, Z out 50%
		#	てへぺろ			tehepero			Happy “bleh”	C	Venti “Tehe” (Like Grin2, but Z in it)
		#	てへぺろ２			tehepero2			Happy “bleh”	C	Same, but Z points down
		#	口角上げ			koukaku age			Raise MC		C	MC up
		#	口角下げ			koukaku sage		Lower MC		C	MC down
		#	口横広げ			kuchiyoko hiroge	Widen M			C	Very wide M
		#	歯無し上			hanashijou			No UpT			C	Up T is gone
		#	歯無し下			hanashimoto			No DwT			C	Dw T is gone
		#	ハンサム			hansamu				Handsome			Transform Chin
		pass
	defT_Op = find_one_morph(morphs, "kuti_ha.ha00_def_op")   ## Default open teeth
	defY_Op = find_one_morph(morphs, "kuti_yaeba.y00_def_op") ## Default open canine
	defZ_Op = find_one_morph(morphs, "kuti_sita.t00_def_op")  ## Default Tongue
	
	#-# あ				a					Say "A"			O	Open L+T for A
	#-# い				I					Say "I"			*	Wide Op L for I
	#-# う				u					Say "U"			O	Open L+T for U
	#-# え				e					Say "E"			O	Open L+T for E
	#-# お				o					Say "O"			O	Open L+T for O
	#-# ん				n					Say “N”			C	MC for N
	#-# *２				*2					Say "*" (big)	O	Open WIDE for *
	addOrReplaceMouth("あ", "A",  find_all_morphs(morphs, "kuti", "_a", "_s", 1.0, True) )
	addOrReplaceMouth("い", "I",  find_all_morphs(morphs, "kuti", "_i", "_s", 0.75, True) )
	addOrReplaceMouth("う", "U",  find_all_morphs(morphs, "kuti", "_u", "_s", 0.75, True) + [ (defT_Op, 0.75), (defY_Op, 0.1) ])
	
	#addOrReplaceMouth("え", "E",  find_all_morphs(morphs, "kuti", "_e", "_s", 1.0, True) ) # idk maybe change tongue to 0.95
	eMorphs = find_all_morphs(morphs, "kuti", "_e", "_s", 1.0, True)
	eMorphs = replace_one_morph(eMorphs, "sita", value=0.85)
	addOrReplaceMouth("え", "E",  eMorphs)
	
	addOrReplaceMouth("お", "O",  find_all_morphs(morphs, "kuti", "_o", "_s", 1.0, True)	+ [ (defT_Op, 0.75), (defY_Op, 0.5), (defZ_Op, 0.5) ])
	addOrReplaceMouth("ん", "N",  find_all_morphs(morphs, "kuti", "_n", "_s", 1.0, True) )
	addOrReplaceMouth("あ２", "A (Large)",  find_all_morphs(morphs, "kuti", "_a", "_l", 1.0, True) )
	addOrReplaceMouth("い２", "I (Large)",  find_all_morphs(morphs, "kuti", "_i", "_l", 0.75, True) )
	addOrReplaceMouth("う２", "U (Large)",  find_all_morphs(morphs, "kuti", "_u", "_l", 0.75, True) + [ (defT_Op, 0.75), (defY_Op, 0.1) ])
	addOrReplaceMouth("え２", "E (Large)",  find_all_morphs(morphs, "kuti", "_e", "_l", 1.0, True) )
	addOrReplaceMouth("お２", "O (Large)",  find_all_morphs(morphs, "kuti", "_o", "_l", 1.0, True) + [ (defT_Op, 0.75), (defY_Op, 0.33), (defZ_Op, 0.5) ])
	
	#-# ▲				*					°▲°				O	L as-such, X infront of T+Z	
	addOrReplaceMouth("▲", "°▲°",  find_all_morphs(morphs, "kuti", "_san", None, 1) + [(defT_Op, 1.0), (defY_Op, 1), (defZ_Op, -0.6)])
	
	#-# ∧				*					°∧°				C	L as-such – T open, Z pulls back
#	addOrReplaceMouth("∧", "°∧°",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	#-# □				*					°□°				O	Same as ▲
#	addOrReplaceMouth("□", "°□°",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	addOrReplaceMouth("□", "°□°[Placeholder]", [])
	#-# ワ				*					Say “Wa”		O	Looks like :D with barely T
#	addOrReplaceMouth("ワ", "Wa",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	addOrReplaceMouth("ワ", "Wa[Placeholder]", [])

	#-# ω				*					[Form]			C	L into shape
	addOrReplaceMouth("ω", "°ω°",  find_all_morphs(morphs, "kuti", "_neko", [None,"_cl"], 0.5) )
	#-# ω□				*									O	L into shape, T behind L
#	addOrReplaceMouth("ω□", "°ω° (Open)",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )

	#-# にやり			niyari				Grin			C	M widens (flat smile)
	#-# にやり２			Niyari 2			Grin 2			C	Left MC high up
	#--- Default does not expect eyes in it, remove them again
	addOrReplaceMouth("にやり", "Grin",    [find_one_morph(morphs, "kuti_face.f00_bisyou_op", 1)])
	addOrReplaceMouth("にやり２", "Grin 2", [find_one_morph(morphs, "kuti_face.f00_bisyou_op", 4)])
	#-# にっこり			nikkori				Smirk			C	・‿・ (almost creepy smile)
#	addOrReplaceMouth("にっこり	", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	addOrReplaceMouth("にっこり", "にっこり[Placeholder]", [])
	#-# ぺろっ			pero				Lick			~~	T+L barely, Z out 50%
#	addOrReplaceMouth("ぺろっ", "Licking",  find_all_morphs(morphs, "kuti", "_pero", None, 0.5) ) ##>> Fix or off
	addOrReplaceMouth("ぺろっ", "ぺろっ[Placeholder]", [])
	#-# てへぺろ			tehepero			Happy “bleh”	C	Venti “Tehe” (Like Grin2, but Z in it)
	#-# てへぺろ２			tehepero2			Happy “bleh”	C	Same, but Z points down
#	addOrReplaceMouth("てへぺろ", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
#	addOrReplaceMouth("てへぺろ２", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	addOrReplaceMouth("てへぺろ", "てへぺろ[Placeholder]", [])
	addOrReplaceMouth("てへぺろ２", "てへぺろ２[Placeholder]", [])
	#-# 口角上げ			koukaku age			Raise MC		C	MC up
	addOrReplaceMouth("口角上げ", "Be Happy", [find_one_morph(morphs, "kuti_face.f00_uresi_cl", 0.5)])
	#-# 口角下げ			koukaku sage		Lower MC		C	MC down
	addOrReplaceMouth("口角下げ", "Be Sad", [find_one_morph(morphs, "kuti_face.f00_ikari_cl", 1.0)])
	#-# 口横広げ			kuchiyoko hiroge	Widen M			C	Very wide M
#	addOrReplaceMouth("口横広げ", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	#-# 歯無し上			hanashijou			No UpT			C	Up T is gone
#	addOrReplaceMouth("歯無し上", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	#-# 歯無し下			hanashimoto			No DwT			C	Dw T is gone
#	addOrReplaceMouth("歯無し下", "Disgust",  find_all_morphs(morphs, "kuti", "_keno", None, 0.5) )
	#-# ハンサム			hansamu				Handsome			Transform Chin

	#############
	addOrReplaceBrow("真面目", "Serious",  find_all_morphs(morphs, "mayuge", "_sinken", [None,"_cl"], 1) )
	addOrReplaceBrow("困る", "Worried",  find_all_morphs(morphs, "mayuge", "_koma", [None, "_cl"], 1) )
	addOrReplaceBrow("上", "Eyebrow up",  [find_one_morph(morphs, "mayuge.mayu00_def_cl", -1.0)])
	addOrReplaceBrow("下", "Eyebrow down",  [find_one_morph(morphs, "mayuge.mayu00_def_cl", 1.0)])
	#############
	addOrReplaceOther("怒り", "Angry", [
		find_one_morph(morphs, "eye_face.f00_ikari_op", 0.75),
		find_one_morph(morphs, "eye_nose.nl00_ikari_op", 0.75),
		#find_one_morph(morphs, "eye_siroL.sL00_ikari_op", 0.75),
		#find_one_morph(morphs, "eye_siroR.sR00_ikari_op", 0.75),
		find_one_morph(morphs, "eye_line_u.elu00_ikari_op", 0.75),
		find_one_morph(morphs, "eye_line_l.ell00_ikari_op", 0.75),
		find_one_morph(morphs, "kuti_face.f00_ikari_cl", 1.0),
		find_one_morph(morphs, "mayuge.mayu00_oko_cl", 1.0),
		])
	addOrReplaceOther("哀しい", "[Face] Sad", [
		find_one_morph(morphs, "eye_line_u.elu00_setsunai_op", 0.80),
		find_one_morph(morphs, "Worried", 1.0),
		])
	## Think about renaming the items to have only the suffix in EN
	
	hotfix_generate_all_morphs(pmx, morphs, eyeOpenness)
	
	names = [
		# Talking
		"あ","い","う","え","お","ん",
		"ああ","いい","うう","ええ","おお",
		"あ２","い２","う２","え２","お２",
		##----
		"まばたき","笑い","ウィンク","ウィンク右","ウィンク２","ｳｨﾝｸ２右","じと目", # Eyes
		#"▲","ω","にやり","にやり２","口角上げ","口角下げ","怒り", # Mouth (Only existing)
		"▲","∧","□","ワ","ω","ω□","にやり","にやり２","口角上げ","口角下げ","怒り", # Mouth (all.. or not)
		"! あせり", "! 切ない", # Extra Mouth I guess... ?
		"真面目","困る","上","下", # Mayuge
		"哀しい", # Other
		]
	print("\n-- Add Vocals to combined group 'TrackVoice'...")
	frames = [find_morph(pmx, name, DEBUG) for name in names]
	frames = [[1,idx] for idx in frames if idx != -1]
	name = c_TrackVoiceName
	idx = find_disp(pmx, name, False)
	if idx != -1: pmx.frames[idx].items = frames
	else: pmx.frames.append(pmxstruct.PmxFrame(name, name, False, frames))
	
	### Just hide the Lines on these ones to make it look better by default
	try:
		pmx.materials[find_mat(pmx, "cf_m_face_00")].flaglist[4] = False
		pmx.materials[find_mat(pmx, "cf_m_eyeline_00_up")].flaglist[4] = False
		pmx.materials[find_mat(pmx, "cf_m_eyeline_down")].flaglist[4] = False
	except: pass
	
	### Translate all items in the name_en
	for morph in pmx.morphs:
		morph.name_en = translateItem(morph.name_en, True)
	
	######
	pass##
##############
### Assemble new Morphs
##############

def generateWink(pmx): ### FUNC: Split things 
	arr = [[],[]]
	if find_morph(pmx, "eye_face.f00_def_cl", False) == -1: return False
	eRIGHT = -1; eBOTH = 0; eLEFT = 1;
	addOrReplaceEye   = lambda jp,en,it: addOrReplace(pmx, jp, en, 2, it, morphtype=1)
	def splitLeftRight(_name):
		arr[0] = []; arr[1] = []
		m_idx = find_morph(pmx, _name, False)
		if m_idx == -1: return False
		vertices = [x for x in pmx.morphs[m_idx].items]
		left  = [] ## positive X
		right = [] ## negative X
		for item in vertices:
			v = pmx.verts[item.vert_idx].pos[0]
			
			##-- Add center vertices to both
			if abs(v) < 0.005: x = eBOTH
			else: x = eRIGHT if v < 0 else eLEFT
			
			if eRIGHT < x: left.append(item)
			if x < eLEFT:  right.append(item)
		arr[0] = left; arr[1] = right
		return True
	if splitLeftRight("eye_face.f00_def_cl"):
		name = "eye_face.f00_winkl02_op";addOrReplaceEye(name, name, arr[0])
		name = "eye_face.f00_winkr02_op";addOrReplaceEye(name, name, arr[1])
	if splitLeftRight("eye_line_u.elu00_def_cl"):
		name = "eye_line_u.elu00_winkl02_cl";addOrReplaceEye(name, name, arr[0])
		name = "eye_line_u.elu00_winkr02_cl";addOrReplaceEye(name, name, arr[1])
	if splitLeftRight("eye_line_l.ell00_def_cl"):
		name = "eye_line_l.ell00_winkl02_cl";addOrReplaceEye(name, name, arr[0])
		name = "eye_line_l.ell00_winkr02_cl";addOrReplaceEye(name, name, arr[1])
	
	return True

def hotfix_generate_all_morphs(pmx, morphs, eyeOpenness):
	addOrReplaceEye   = lambda jp,en,it: addOrReplace(pmx, jp, en, 2, it)
	addOrReplaceMouth = lambda jp,en,it: addOrReplace(pmx, jp, en, 3, it)
	addOrReplaceBrow  = lambda jp,en,it: addOrReplace(pmx, jp, en, 1, it)
	addOrReplaceOther = lambda jp,en,it: addOrReplace(pmx, jp, en, 4, it)
	arr = [x[0] for x in infixes][6:]
	#arr += [x[0] for x in infixes_2]
	def action(act, _name, _arr):
		if act == "O" and _arr[0] == ('', eyeOpenness): return
		if _arr is None or len(_arr) == 0: return
		if _arr[0] in [None, "", ('', 1)]: return
		if act == "E": addOrReplaceEye  (f"[E] {_name}", f"[E] {_name}", _arr)
		if act == "M": addOrReplaceMouth(f"[M] {_name}", f"[M] {_name}", _arr)
		if act == "B": addOrReplaceBrow (f"[B] {_name}", f"[B] {_name}", _arr)
		if act == "O": addOrReplaceOther(f"[O] {_name}", f"[O] {_name}", _arr)
	
	for infix in arr:
		action("E", infix, find_all_morphs(morphs, "eye", infix, [None,"_op"], eyeOpenness, exclude="_siro[LR]"))
		#action("O", infix, [ find_one_morph(morphs, f"eye_line_u.elu00{infix}_op", eyeOpenness) ])
		action("M", f"{infix}_op", find_all_morphs(morphs, "kuti", infix+"%", [None,"_op"], 1))
		action("M", f"{infix}_cl", find_all_morphs(morphs, "kuti", infix+"%", [None,"_cl"], 1))
		action("B", f"{infix}_op", find_all_morphs(morphs, "mayuge", infix+"%", [None,"_op"], 1))
		action("B", f"{infix}_cl", find_all_morphs(morphs, "mayuge", infix+"%", [None,"_cl"], 1))
	
	#t_NameSep = "== Eyeline only =="#("eyelineSep", "== Eyeline only ==")
	#if find_morph(pmx, t_NameSep, False) == -1:
	#	## Give the morph some content to avoid it getting removed
	#	pmx.morphs.append(pmxstruct.PmxMorph(t_NameSep, t_NameSep, 4, 2, [
	#		pmxstruct.PmxMorphItemBone(find_bone(pmx, "右腕", False), [0,0,0], [0,0,35]),
	#		pmxstruct.PmxMorphItemBone(find_bone(pmx, "左腕", False), [0,0,0], [0,0,-35]),
	#	]))
	#	for infix in arr: action("O", infix, [ find_one_morph(morphs, f"eye_line_u.elu00{infix}_op", eyeOpenness) ])
	######
	pass##

def combine_standards(pmx):
	rename_if_foundEN(pmx, "bounce",				"MMD-Pose")
	rename_if_foundEN(pmx, "unbounce",				"T-Pose")
	rename_if_foundEN(pmx, "cf_m_face_00",			"Face")
	rename_if_foundEN(pmx, "cf_m_body",				"Body")
	rename_if_foundEN(pmx, "cm_m_body",				"Body")
	rename_if_foundEN(pmx, "cf_m_mayuge_00",		"Eyebrows")
	rename_if_foundEN(pmx, "cf_m_noseline_00",		"Nose")
	if (find_morph(pmx, "cf_m_tooth*1", False) != -1):
		rename_if_foundEN(pmx, "cf_m_tooth",		"Canine")
		rename_if_foundEN(pmx, "cf_m_tooth*1",		"Teeth")
	else:
		rename_if_foundEN(pmx, "cf_m_tooth",		"Teeth")
	rename_if_foundEN(pmx, "cf_m_eyeline_00_up",	"Eyeline_Up")
	rename_if_foundEN(pmx, "cf_m_eyeline_down",		"Eyeline_Down")
	rename_if_foundEN(pmx, "cf_m_sirome_00",		"EyeL_White")
	rename_if_foundEN(pmx, "cf_m_sirome_00*1",		"EyeR_White")
	rename_if_foundEN(pmx, "cf_m_hitomi_00*1",		"EyeR_Iris")
	rename_if_foundEN(pmx, "cf_m_hitomi_00",		"EyeL_Iris")
	rename_if_foundEN(pmx, "cf_m_tang", 			"Tongue")
	
	## Make Face Morph with all these parts
	######
	pass##

def sort_morphs(pmx):
	""" Sort all morphs into groups and add separators """
	exported  = []; nameExp = "== Export Morphs =="
	vertices  = []; nameVrt = "== Vocal Components =="
	groups    = []; nameGr1 = "== Vocals =="
	groups2   = []; nameGr2 = "== Vocals 2 =="
	materials = []; nameMat = "== Material Morphs =="
	bones     = []; nameExt = "== Extras =="
	oldMorphs = {}; names = [nameExt, nameGr1, nameGr2, nameMat, nameVrt]
	
	#: idk why these cause a KeyError, but lets skip them for now
	errIdx = []
	if find_morph(pmx, nameVrt, False) != -1:
		errIdx.append(find_morph(pmx, nameExp, False))
		errIdx.append(find_morph(pmx, nameVrt, False))
		errIdx.append(find_morph(pmx, nameGr1, False))
		errIdx.append(find_morph(pmx, nameGr2, False))
		errIdx.append(find_morph(pmx, nameMat, False))
		errIdx.append(find_morph(pmx, nameExt, False))
		errIdx = [a for a in errIdx if a != -1]
	
	## Collect all
	for i,m in enumerate(pmx.morphs):
		if m.name_jp in names: continue
		oldMorphs[m.name_jp] = [i, -1]
		
		if (m.morphtype == 0): # groups
			if re.match("\[\w\]", m.name_jp): groups2.append(m)
			else: groups.append(m)
		elif (m.name_jp == "== Eyeline only =="): groups2.append(m)
		elif (m.name_jp == "hitomi-small"): bones.append(m)
		elif (m.morphtype == 1): # vertex
			if re.match("vr[mc]\.", m.name_jp): exported.append(m)
			else: vertices.append(m)
		elif (m.morphtype == 8): materials.append(m) # materials
		elif (m.morphtype == 9): groups.append(m) # flip
		else: bones.append(m) # bone, UV, impulse

	baseIdx = 0; newMorphs = []
	## Order: VRC, A E I O U Blink, Material, slots, Extras, Vocals, Groups, Components
	## List Export \\ Materials \\ Extras \\ Group
	def sorter(baseIdx, _list, _sep = None):
		if not _sep is None:
			newMorphs.append(make_separator(pmx, _sep))
			baseIdx += 1
		for i,m in enumerate(_list):
			newMorphs.append(m)
			oldMorphs[m.name_jp][1] = baseIdx + i
		baseIdx = len(newMorphs)
		return baseIdx
	baseIdx = sorter(baseIdx, exported)
	baseIdx = sorter(baseIdx, materials, nameMat)
	baseIdx = sorter(baseIdx, groups, nameGr1)
	baseIdx = sorter(baseIdx, bones, nameExt)
	baseIdx = sorter(baseIdx, groups2, nameGr2)
	baseIdx = sorter(baseIdx, vertices, nameVrt)
	
	morphMap = {a[0]: a[1] for a in oldMorphs.values() if a[1] != -1}
	for m in newMorphs:
		if m.morphtype in [0, 9]:
			for i in m.items: i.morph_idx = morphMap[i.morph_idx] #morphMap.get(i.morph_idx, i.morph_idx)
	pmx.morphs = newMorphs
	
	## Fix Display Frames
	for df in pmx.frames:
		for item in df.items:
			try:
				if item[0] and not item[1] in errIdx: item[1] = morphMap[item[1]]
			except KeyError as ke: util.throwIfDebug(DEBUG, f'{ke}')


##############
### Display Frames
##############

	idx = find_disp(pmx, name, False)
	if idx == -1: idx = len(pmx.frames); pmx.frames.append(pmxstruct.PmxFrame(name, name, False, []))
	if not _frames is None: pmx.frames[idx].items = _frames
	return idx;
find_or_replace_disp.__doc__ = """ Return index of the requested Frame -- Append a new empty one if not found """

def putAuxIntoGroup(pmx):
	showWarning = not _univrm()
	names = [
		"bounce", "unbounce","Move for Shoes","Move to Barefeet",
		"hitomiX-small", "hitomiY-small", "hitomiX-big", "hitomiY-big", 
		"hitomi-up", "hitomi-down", "hitomi-left", "hitomi-right",
		"hitomi-small",
		"Move Model downwards", "Move Body downwards",
		"chikubi_in", "chikubi_out", 
	]
	name = c_AuxMorphName
	print(f"-- Add misc Morphs to combined group '{name}'...")
	frames = [find_morph(pmx, name, showWarning) for name in names]
	frames += [find_morph(pmx, "OwO Morph", False)]
	frames = [[1,_idx] for _idx in frames if _idx != -1]
	find_or_replace_disp(pmx, name, frames)

def sort_morphs_into_frames(pmx): ## Intended for UniVRM models
	eyes = ["smile", "wink", "^blink", "eyelid", "look", "grin", "highlight"] + ["jitome", "tsurime", "tareme", "hitomi", "doukou"] + ["><", "=="]
	mouth = ["mouth", "tongue", "teeth"] + ["^kuchi", "^bero", "pero"]
	brows = ["^mayu"]
	
	eyes += ["^eye_face", "^eye_nose", "^eye_line_u", "^eye_line_l", "eye_siroL", "eye_siroR"]
	mouth += ["^kuti_face", "^kuti_nose", "kuti_ha", "kuti_sita", "kuti_yaeba"]
	
	names = [
		## Eyes (Move)
		["まばたき", "笑い", "ウィンク", "ウィンク右", "ウィンク２", "ｳｨﾝｸ２右"],
		## Eyes (Expression)
		["なごみ", "はぅ", "びっくり", "じと目", "ｷﾘｯ", "星目", "はぁと", "瞳小", "瞳大", "光下", "ハイライト消し"], 
		## Mouth (Talking)
		["あ", "い", "う", "え", "お", "ω□", "ワ", "∧", "▲"],
		## Mouth (Expression)
		["はんっ！", "にやり", "にっこり", "ぺろっ", "てへぺろ", "口角上げ", "口角下げ", "口横広げ"], 
		## Eyebrow
		["真面目", "困る", "にこり", "怒り", "上", "下"], 
		## Other
		["頬染め", "涙"], 
	]
	flat_names = util.flatten(names)
	rgE = util.matchList(eyes)
	rgM = util.matchList(mouth)
	rgB = util.matchList(brows)
	### Categorize the Morphs & translate any if needed
	for morph in pmx.morphs:
		name = morph.name_jp
		morph.name_en = util.translate_name(name, morph.name_en)
		if name in [flat_names]: continue
		morph.panel = 4
		if  rgE.search(name): morph.panel = 2
		if  rgM.search(name): morph.panel = 3
		if  rgB.search(name): morph.panel = 1
	
	### Assign any MMD Morphs correctly (separately because Talking is one letter)
	eyes  = names[0] + names[1]
	mouth = names[2] + names[3]
	brows = names[4]
	frames = [find_morph(pmx, name, True) for name in flat_names]
	
	for idx in frames:
		if idx == -1: continue
		morph = pmx.morphs[idx]
		name = morph.name_jp
		if name in eyes:    morph.panel = 2
		elif name in mouth: morph.panel = 3
		elif name in brows: morph.panel = 1
		else:               morph.panel = 4
	
	#####
	name = c_TrackVoiceName
	print(f"\n-- Add Vocals to combined group '{name}'...")
	frames = [[1,_idx] for _idx in frames if _idx != -1]
	find_or_replace_disp(pmx, name, frames)

def sort_bones_into_frames(pmx):
	used_bones = set()
	curSlot = "global_slot"
	for frame in pmx.frames:
		if frame.name_jp == cName_morebones: continue
		if frame.name_jp == cName_extraBones: continue
		if frame.name_jp.startswith("a_n_"): continue
		if frame.name_jp == curSlot: continue
		for item in frame.items:
			if not item[0]: used_bones.add(item[1])
	
	extra_bones = []
	slot_bones = {}
	
	child_map = kkrig.get_children_map(pmx, None, True, False)
	
	reSkip = re.compile(r"cf_(hit|t|pv)_|a_n_|k_f_|KKS_")
	# Vertex Bones and Any JP
	reKeep = re.compile(r"cf_s_|[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]+", re.U)
	
	
	for d,bone in enumerate(pmx.bones):
		if d in used_bones: continue
		name = bone.name_jp
		if reSkip.match(name):
			## Group by Slot-Parent
			if name.startswith("a_n_"):
				curSlot = name
				slot_bones[curSlot] = [d]
			continue
		## Add respective Assets to their slots
		if name.startswith("ca_slot"):
			arr = [d] + child_map[d]
			[used_bones.add(x) for x in arr]
			slot_bones[curSlot] += arr
			continue
		## Group all remaining Vertex Bones
		#if reKeep.match(name):
		if name.startswith("cf_s_"):
			extra_bones.append(d)
	
	## Create ExtraBones Frame
	name = cName_extraBones
	idx = find_or_replace_disp(pmx, name)
	pmx.frames[idx] = pmxstruct.PmxFrame(name_jp=name, name_en=name, is_special=False, items=[[0, x] for x in extra_bones])
	
	## Create Slot-Morphs Frame
	delIdx = []
	for k,v in slot_bones.items():
		idx = find_or_replace_disp(pmx, k)
		if len(v) < 2: 
			delIdx.append(idx)
			continue
		pmx.frames[idx] = pmxstruct.PmxFrame(name_jp=k, name_en=k, is_special=False, items=[[0, x] for x in v])
	for idx in reversed(delIdx): del pmx.frames[idx]
	
	## Move 'remaining bones' Frame to end and filter out thsoe already added elsewhere
	idx = find_disp(pmx, cName_morebones, False)
	if idx != -1:
		oldFrame = pmx.frames[idx]
		del pmx.frames[idx]
		oldFrame.items = list(filter(lambda x: x[1] not in used_bones, oldFrame.items))
		pmx.frames.append(oldFrame)



##############
### BoneMorph
##############

def make_bone_morph(pmx, name, items=[], override=False): return make_any_morph(pmx, name, items, override, 2)
def make_bone_item(pmx, name, pos, rot): return pmxstruct.PmxMorphItemBone(find_bone(pmx, name, False), pos, rot)
## =/BoneMorph,".+?",(".+?"),([\-\d\.]+,[\-\d\.]+,[\-\d\.]+),([\-\d\.]+,[\-\d\.]+,[\-\d\.]+)/ --> =/make_bone_item\(pmx, \1, [\2], [\3]\),/

def make_separator(pmx, name):
	item = make_bone_item(pmx, pmx.bones[0].name_jp, [0, -1, 0], [0, 0, 0])
	return make_bone_morph(None, name, [ item ], False)

def add_heels_morph(pmx):
	make_bone_morph(pmx, "Move for Shoes", [
		make_bone_item(pmx, "グルーブ", [0,0.18,0], [0,0,0]),
		make_bone_item(pmx, "左足ＩＫ", [0,-0.281,0], [0,0,0]),
		make_bone_item(pmx, "右足ＩＫ", [0,-0.281,0], [0,0,0]),
		make_bone_item(pmx, "cf_j_toes_L", [0,0,0], [21,0,0]),
		make_bone_item(pmx, "cf_j_toes_R", [0,0,0], [21,0,0]),
	])
	make_bone_morph(pmx, "Move to Barefeet", [
		make_bone_item(pmx, "グルーブ", [0,-0.18,0], [0,0,0]),
		make_bone_item(pmx, "左足ＩＫ", [0,0.281,0], [0,0,0]),
		make_bone_item(pmx, "右足ＩＫ", [0,0.281,0], [0,0,0]),
		make_bone_item(pmx, "cf_j_toes_L", [0,0,0], [-21,0,0]),
		make_bone_item(pmx, "cf_j_toes_R", [0,0,0], [-21,0,0]),
	])


def add_ground_morph(pmx):
	morph_name = "Adjust for Ground"
	bone_name = "ChestRigidRoot"
	delta = -1
	
	idx = find_bone(pmx, "右つま先ＩＫ", False)
	if idx != -1:
		bone   = pmx.bones[idx]
		pos_y  = bone.pos[1]
		tail_y = 0.10 if bone.tail_usebonelink else abs(bone.tail[1]) # could also use Y-Pos of Bone-Link but lets wait if it ever changes
		# Verify if this works consistently -- Expects that Toe IK points to a specific distance *below 0*, as opposed to a constant length
		# By default this makes the model be perfectly on ground if barefeet
		delta  = -2 * pos_y + tail_y # == (pos_y + (pos_y - tail_y)) * -1
	
	bone = kkrig.add_bone_default(pmx, bone_name)
	bone.parent_idx = 0 # [[ test ]] this one (instead of -1)
	
	util.set_parent_if_found(pmx, "左胸操作接続", bone_name, is_rigid=True)
	util.set_parent_if_found(pmx, "左胸操作衝突", bone_name, is_rigid=True)
	util.set_parent_if_found(pmx, "右胸操作接続", bone_name, is_rigid=True)
	util.set_parent_if_found(pmx, "右胸操作衝突", bone_name, is_rigid=True)

	make_bone_morph(pmx, morph_name, [
		make_bone_item(pmx, "センター",   [0, -delta, 0], [0, 0, 0]),
		make_bone_item(pmx, "左足ＩＫ",   [0, -delta, 0], [0, 0, 0]),
		make_bone_item(pmx, "右足ＩＫ",   [0, -delta, 0], [0, 0, 0]),
		make_bone_item(pmx, bone_name, [0, -delta, 0], [0, 0, 0]),
	])

##############
### VertexMorph
##############

def make_vert_morph(pmx, name, items=[], override=False): return make_any_morph(pmx, name, items, override, 2)
def make_vert_item(pmx, name, pos, rot): return pmxstruct.PmxMorphItemBone(find_bone(pmx, name, False), pos, rot)

##############
### More Morph Helpers
##############

def rename_if_foundEN(pmx, oldName, newName): return rename_if_found(pmx, oldName, newName, None)
def rename_if_foundJP(pmx, oldName, newName): return rename_if_found(pmx, oldName, None, newName)
def rename_if_found(pmx, oldName, newNameEN, newNameJP):
	if _univrm(): oldName = re.sub(r"\*", r"+", oldName)
	idx = find_morph(pmx, oldName, False)
	if idx != -1:
		m = pmx.morphs[idx]
		if newNameEN: m.name_en = newNameEN
		if newNameJP: m.name_jp = newNameJP

def make_any_morph(pmx, name, items=[], override=False, cat=0):
	if pmx is None: return pmxstruct.PmxMorph(name, name, 4, cat, items)
	morphIdx = find_morph(pmx, name, False)
	if morphIdx != -1:
		if not override: return
	else:
		morphIdx = len(pmx.morphs)
		pmx.morphs.append(None)
	if cat < 0 or cat > 6: cat = 0
	if not items: items = []
	pmx.morphs[morphIdx] = pmxstruct.PmxMorph(name, name, 4, cat, items)
	######
	pass##

	vert_len  = len(pmx.verts)
	mat_len   = len(pmx.materials)
	bone_len  = len(pmx.bones)
	morph_len = len(pmx.morphs)
	for morph in pmx.morphs:
		if morph.morphtype == 0:
			morph.items = [m for (idx,m) in enumerate(morph.items) if -1 < m.morph_idx < morph_len]
		elif morph.morphtype == 2:
			morph.items = [m for (idx,m) in enumerate(morph.items) if -1 < m.bone_idx < bone_len]
		elif morph.morphtype == 8:
			morph.items = [m for (idx,m) in enumerate(morph.items) if -1 < m.mat_idx < mat_len]
		elif morph.morphtype == 9: pass
		elif morph.morphtype == 10: pass
		else: #if morph.morphtype in [1, 3, 4, 5, 6, 7]:
			morph.items = [m for (idx,m) in enumerate(morph.items) if -1 < m.vert_idx < vert_len]


#########
#---- Expression ideas
# <（i）>			
# 胸ボーン							
# パンツZ								
# パンツY								
# パンツY2							
# 真面目			eyebrow_serius1		
# 困る			eyebrow_sad1		
# にこり			eyebrow_smile		
# 怒り			eyebrow_anger1		
# 上			eyebrow_up			
# 下			eyebrow_down		
# まばたき			eye_blink			Blink
# 笑い			eye_smile			Happy
# ウィンク			eye_wink_L			Wink (L)
# ウィンク右		eye_wink_R			Wink (R)
# ウィンク２		eye_wink2_L			Happy Wink (L)
# ｳｨﾝｸ２右		eye_wink2_R			Happy Wink (R)
# はぅ			eye_hau				>.<				// replace eye with texture
# なごみ			eye_nagomi			=.=				// replace eye with texture
# びっくり			eye_surprised		O.O				// morph eyelid
# じと目			eye_jito			-.- (p eyes)	// morph eyelid
# ぐるぐる目		eye_guruguru		@.@				// replace iris texture
# 絶望			eye_zetsubou		#.# (blank)		// replace iris texture
# ハート目		eye_heart							// add texture
# きらきら目		eye_star							// add texture
# 瞳小			eye_small							// shrink iris
# カメラ目線		eye_camera			???
# あ				A					
# い				I					
# う				U					
# え				E					
# お				O					
# ▲				mouth_triangle		
# ∧				mouth_∧				
# ω				mouth_w				
# えー			e-					"Ehh....?"
# 口角上げ		mouth_corner_up		
# 口角下げ		mouth_corner_down	
# 幅大			mouth_wide			
# 幅小			mouth_narrow		
# 青ざめ			ex_aozame			// add texture to forehead
# 涙			ex_tear				// add tears to corner of the eye
# 照れ			ex_tere				// add blush
# ムカッ			ex_muka				// add anger symbol to head
# 汗			ex_ase				// add "Ehhh...." Tear to head
# ホラー			Horror				
